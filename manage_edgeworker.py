import os
import re
import json
import tarfile
import logging
import requests
from urllib.parse import urljoin

from helpers import dbg

logger = logging.getLogger("edgeworker")
logger.setLevel(logging.INFO)


# =========================================================
# UPDATE main.js USING requirements.json
# =========================================================
def update_main_js(requirements_json, main_js_file, verbose):
    dbg(verbose, f"Updating main.js → {main_js_file}")
    logger.info(f"[STEP] Updating main.js using {requirements_json}")

    with open(requirements_json, "r") as f:
        req = json.load(f)

    internal_hostname = req["propertyManager"]["internalHarperHostname"]["internalHostname"]
    harper_token = req["edgeworker"]["harper_token"]

    new_subrequest_base = f"https://{internal_hostname}"

    dbg(verbose, f"New HARPPER_TOKEN = {harper_token}")
    dbg(verbose, f"New SUBREQUEST_BASE_URL = {new_subrequest_base}")

    with open(main_js_file, "r") as f:
        content = f.read()

    content = re.sub(
        r"const HARPPER_TOKEN\s*=\s*'.*?';",
        f"const HARPPER_TOKEN = '{harper_token}';",
        content
    )

    content = re.sub(
        r"const SUBREQUEST_BASE_URL\s*=\s*'.*?';",
        f"const SUBREQUEST_BASE_URL = '{new_subrequest_base}';",
        content
    )

    with open(main_js_file, "w") as f:
        f.write(content)

    logger.info("[SUCCESS] Updated HARPPER_TOKEN + SUBREQUEST_BASE_URL in main.js")
    dbg(verbose, "main.js update completed.")


# =========================================================
# CREATE TGZ BUNDLE
# =========================================================
def create_bundle(source_folder, output_tgz, verbose):
    dbg(verbose, f"Creating bundle → {output_tgz}")
    logger.info(f"[STEP] Creating EdgeWorker bundle → {output_tgz}")

    if os.path.exists(output_tgz):
        dbg(verbose, f"Removing old bundle: {output_tgz}")
        os.remove(output_tgz)

    main_js_path = os.path.join(source_folder, "main.js")
    bundle_json_path = os.path.join(source_folder, "bundle.json")

    if not os.path.exists(main_js_path):
        raise FileNotFoundError(f"main.js not found at {main_js_path}")
    if not os.path.exists(bundle_json_path):
        raise FileNotFoundError(f"bundle.json not found at {bundle_json_path}")

    with tarfile.open(output_tgz, "w:gz") as tgz:
        tgz.add(main_js_path, arcname="main.js")
        tgz.add(bundle_json_path, arcname="bundle.json")

    logger.info(f"[SUCCESS] Bundle created: {output_tgz}")
    dbg(verbose, "Bundle creation completed.")


# =========================================================
# CREATE EDGEWORKER ID
# =========================================================
def create_edgeworker_id(session, baseurl, name, groupId, resourceTierId, description,
                         accountSwitchKey, verbose):
    logger.info(f"[STEP] Creating EdgeWorker ID → {name}")

    path = "/edgeworkers/v1/ids"
    url = urljoin(baseurl, path)

    params = {}
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = {
        "name": name,
        "groupId": groupId,
        "resourceTierId": resourceTierId,
        "description": description
    }

    dbg(verbose, f"EdgeWorker ID Creation Payload = {payload}")
    dbg(verbose, f"POST {url} params={params}")

    result = session.post(
        url,
        params=params,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json=payload
    )

    dbg(verbose, f"Response Status: {result.status_code}")
    dbg(verbose, f"Response Body: {result.text}")

    if result.status_code not in (200, 201):
        raise Exception(result.text)

    ew_id = result.json().get("edgeWorkerId")
    logger.info(f"[SUCCESS] EdgeWorker ID created → {ew_id}")
    return ew_id


# =========================================================
# UPLOAD EDGEWORKER VERSION
# =========================================================
def upload_edgeworker_version(session, baseurl, ew_id, tgz_file, accountSwitchKey, verbose):
    dbg(verbose, f"Uploading .tgz for EW ID = {ew_id}")
    logger.info(f"[STEP] Uploading version for EdgeWorker ID {ew_id}")

    if not os.path.exists(tgz_file):
        raise FileNotFoundError(f"Bundle not found: {tgz_file}")

    path = f"/edgeworkers/v1/ids/{ew_id}/versions"
    url = urljoin(baseurl, path)

    params = {}
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    with open(tgz_file, "rb") as f:
        payload = f.read()

    dbg(verbose, f"Uploading bundle size = {len(payload)} bytes")

    result = session.post(
        url,
        params=params,
        headers={"Content-Type": "application/gzip", "Accept": "application/json"},
        data=payload
    )

    dbg(verbose, f"Response Status: {result.status_code}")
    dbg(verbose, f"Response Body: {result.text}")

    if result.status_code not in (200, 201):
        logger.error(f"[ERROR] Failed to upload EdgeWorker version → {result.text}")
        raise Exception(result.text)

    version = result.json().get("version")
    logger.info(f"[SUCCESS] Version uploaded: {version}")
    dbg(verbose, f"Uploaded version = {version}")

    return version


# =========================================================
# ACTIVATE EDGEWORKER
# =========================================================
def activate_edgeworker(session, baseurl, ew_id, version, network, accountSwitchKey, verbose):
    dbg(verbose, f"Activating EW ID={ew_id} version={version} on {network}")
    logger.info(f"[STEP] Activating EW {ew_id} version {version} on {network}")

    path = f"/edgeworkers/v1/ids/{ew_id}/activations"
    url = urljoin(baseurl, path)

    params = {}
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = {
        "network": network.upper(),
        "version": version
    }

    dbg(verbose, f"Activation Payload = {payload}")
    dbg(verbose, f"POST {url} params={params}")

    result = session.post(
        url,
        params=params,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json=payload
    )

    dbg(verbose, f"Activation Response Status: {result.status_code}")
    dbg(verbose, f"Activation Response Body: {result.text}")

    if result.status_code not in (200, 201):
        logger.error(f"[ERROR] EdgeWorker activation failed → {result.text}")
        raise Exception(result.text)

    logger.info("[SUCCESS] Activation submitted successfully.")
    return result.json()


# =========================================================
# FETCH EDGEWORKER FILES FROM GITHUB
# =========================================================
def fetch_from_github(gh_config, edgeworker_folder, verbose):
    repo   = gh_config.get("repo", "")
    branch = gh_config.get("branch", "main")
    token  = gh_config.get("token", "")

    if not repo:
        raise ValueError("edgeworker.github.repo is required when GitHub source is enabled.")

    base_url = f"https://raw.githubusercontent.com/{repo}/{branch}"
    headers  = {"Accept": "application/vnd.github.v3.raw"}
    if token:
        headers["Authorization"] = f"token {token}"

    files_to_fetch = {
        "main.js":     gh_config.get("main_js_path", "main.js"),
        "bundle.json": gh_config.get("bundle_json_path", "bundle.json"),
    }

    os.makedirs(edgeworker_folder, exist_ok=True)

    for local_name, remote_path in files_to_fetch.items():
        url = f"{base_url}/{remote_path}"
        print(f"[INFO] Fetching {local_name} from GitHub → {repo}/{branch}/{remote_path}")
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code == 404:
            raise FileNotFoundError(f"GitHub file not found: {url}")
        if resp.status_code == 401:
            raise PermissionError("GitHub 401 — set edgeworker.github.token for private repos.")
        if resp.status_code != 200:
            raise Exception(f"GitHub fetch failed ({resp.status_code}): {resp.text}")

        dest = os.path.join(edgeworker_folder, local_name)
        with open(dest, "w") as f:
            f.write(resp.text)
        print(f"[SUCCESS] Saved {local_name} → {dest}")

    logger.info("[SUCCESS] GitHub source files downloaded.")


# =========================================================
# RUN WORKFLOW
# =========================================================
def run_edgeworker_workflow(session, baseurl, config, activationMode, accountSwitchKey, verbose):
    print("\n=== EDGEWORKER WORKFLOW START ===")

    ew_info = config["edgeworker"]

    # Paths
    requirements_json = "requirements.json"
    edgeworker_folder = "data/edgeworker"
    main_js    = os.path.join(edgeworker_folder, "main.js")
    bundle_path = os.path.join(edgeworker_folder, "edgeworker_bundle.tgz")

    # groupId = "grp_xxx" → EdgeWorkers require numeric
    groupId_raw = config["groupId"]
    groupId = int(groupId_raw.replace("grp_", ""))
    dbg(verbose, f"groupId from config = {groupId_raw}")
    dbg(verbose, f"Numeric groupId for EdgeWorker = {groupId}")

    results = {}

    # -------------------------------------------------------
    # STEP 0 – optionally pull source files from GitHub
    # -------------------------------------------------------
    gh_config  = ew_info.get("github", {})
    use_github = gh_config.get("enabled", False)

    if use_github:
        print("[INFO] GitHub source enabled — fetching EdgeWorker files from repo...")
        fetch_from_github(gh_config, edgeworker_folder, verbose)
        print("[INFO] GitHub fetch complete. Proceeding with bundle creation.\n")
    else:
        print("[INFO] Using local EdgeWorker source files.")

    # -------------------------------------------------------
    # STEP 1 – inject token + hostname into main.js
    # -------------------------------------------------------
    update_main_js(requirements_json, main_js, verbose)

    # -------------------------------------------------------
    # STEP 2 – create .tgz bundle
    # -------------------------------------------------------
    create_bundle(edgeworker_folder, bundle_path, verbose)

    # -------------------------------------------------------
    # STEP 3 – create EdgeWorker ID
    # -------------------------------------------------------
    ew_id = create_edgeworker_id(
        session=session,
        baseurl=baseurl,
        name=ew_info["name"],
        groupId=groupId,
        resourceTierId=ew_info["resourceTierId"],
        description=ew_info["description"],
        accountSwitchKey=accountSwitchKey,
        verbose=verbose
    )
    results["edgeWorkerId"] = ew_id

    # -------------------------------------------------------
    # STEP 4 – upload version
    # -------------------------------------------------------
    version = upload_edgeworker_version(
        session=session,
        baseurl=baseurl,
        ew_id=ew_id,
        tgz_file=bundle_path,
        accountSwitchKey=accountSwitchKey,
        verbose=verbose
    )
    results["version"] = version

    # -------------------------------------------------------
    # STEP 5 – activate (based on CLI activationMode)
    # -------------------------------------------------------
    mode = activationMode.lower()

    if mode == "saveonly":
        print("[INFO] EdgeWorker activation skipped (saveonly mode).")
        results["activation"] = "skipped (saveonly)"
    elif mode in ("staging", "production"):
        print(f"[INFO] Activating EdgeWorker to {mode.upper()}")
        activation_result = activate_edgeworker(
            session=session,
            baseurl=baseurl,
            ew_id=ew_id,
            version=version,
            network=mode,
            accountSwitchKey=accountSwitchKey,
            verbose=verbose
        )
        results["activation"] = activation_result
    else:
        print(f"[WARNING] Unknown activationMode '{activationMode}' — skipping activation.")
        results["activation"] = f"skipped (unknown activationMode '{activationMode}')"

    print("\n=== EDGEWORKER WORKFLOW COMPLETED ===\n")
    return results