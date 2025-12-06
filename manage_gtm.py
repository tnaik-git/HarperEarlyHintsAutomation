import time
import json
import csv
import sys
from datetime import datetime
from urllib.parse import urljoin
from helpers import dbg


# ============================================================
# Pretty Print for Verbose Mode
# ============================================================
def pp(session_verbose, label, obj):
    if session_verbose.get("verbose"):
        print(f"\n=== {label} ===")
        print(json.dumps(obj, indent=2))


# ============================================================
# LOAD DATACENTERS FROM CSV
# ============================================================
def load_datacenters_from_csv(csv_path, session_verbose):
    print("\n>>> ENTER: load_datacenters_from_csv()")

    datacenters = []
    now = datetime.now()

    prefix = f"{now.year % 100:02d}{now.month:02d}"  # YYMM prefix
    print(f"[INFO] Temporary ID prefix: {prefix}")

    seq = 1

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            servers = [s.strip() for s in row["servers"].split(";") if s.strip()]
            tmp_id = f"{prefix}{seq:02d}"
            seq += 1

            dc = {
                "tmpId": tmp_id,
                "nickname": row["nickname"],
                "city": row["city"],
                "stateOrProvince": row["stateOrProvince"],
                "country": row["country"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "servers": servers
            }

            print(f"[INFO] CSV DC Loaded tmpId={tmp_id}, nickname={dc['nickname']}")
            datacenters.append(dc)

    print("<<< EXIT: load_datacenters_from_csv()")
    return datacenters


# ============================================================
# CHECK IF GTM DOMAIN EXISTS
# ============================================================
def get_gtm_domain(session, baseurl, domain, accountSwitchKey):
    params = {}
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    url = f"{baseurl}/config-gtm/v1/domains/{domain}"

    resp = session.get(url, params=params)

    if resp.status_code == 200:
        print(f"[INFO] GTM domain already exists: {domain}")
        return resp.json()

    print(f"[INFO] GTM domain does NOT exist yet: {domain}")
    return None


# ============================================================
# CREATE GTM DOMAIN (Minimal payload)
# ============================================================
def create_gtm_domain(session, baseurl, config, accountSwitchKey, verbose):
    print("\n>>> ENTER: create_gtm_domain()")

    domain = config["gtmDomain"]
    contractId = config["contractId"]
    groupId = config["groupId"]
    groupId_clean = groupId.replace("grp_", "")  # GTM requires numeric gid

    url = f"{baseurl}/config-gtm/v1/domains"

    params = {
        "contractId": contractId,
        "gid": groupId_clean
    }

    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = {
        "defaultErrorPenalty": 75,
        "defaultTimeoutPenalty": 25,
        "loadFeedback": True,
        "type": "basic",                      # FINAL TYPE
        "cnameCoalescingEnabled": False,
        "signAndServe": False,
        "name": domain                        # MUST BE INSIDE PAYLOAD
    }

    session_verbose = {"verbose": verbose}
    pp(session_verbose, "GTM DOMAIN PAYLOAD", payload)

    headers = {
        "accept": "application/vnd.config-gtm.v1.6+json",
        "content-type": "application/vnd.config-gtm.v1.6+json"
    }

    print(f"[INFO] Creating GTM Domain: {domain}")

    resp = session.post(url, params=params, json=payload, headers=headers)

    print("[INFO] Status:", resp.status_code)
    dbg(session_verbose, f"[DEBUG] Response: {resp.text}")

    if resp.status_code not in (200, 201):
        raise Exception(f"Failed to create GTM domain: {resp.text}")

    print("[SUCCESS] GTM domain created.")
    print("<<< EXIT: create_gtm_domain()")

    return resp.json()


# ============================================================
# MANUALLY HANDLE 403 DOMAIN CREATION PERMISSIONS
# ============================================================
def handle_domain_forbidden(domain):
    print("\n⛔  ERROR: Akamai has rejected GTM Domain creation for:")
    print(f"    ➤ {domain}\n")
    print("This means your contract/group/accountSwitchKey does NOT have")
    print("permission to CREATE new GTM domains via API.\n")
    print("===============================================================")
    print("   ACTION REQUIRED (Manual Step)")
    print("===============================================================")
    print("1. Log into Akamai Control Center:")
    print("   https://control.akamai.com\n")
    print("2. Go to:  Traffic Management  →  Domains")
    print("3. CREATE a new GTM Domain with the name:")
    print(f"   ➤ {domain}\n")
    print("4. After saving the domain, rerun this script.\n")
    print("Automation cannot continue without the GTM domain.")
    print("Exiting now.\n")
    sys.exit(1)


# ============================================================
# CREATE GTM DATACENTER
# ============================================================
def create_gtm_datacenter(session, baseurl, domain, dc, contractId, groupId, accountSwitchKey, session_verbose):
    print("\n>>> ENTER: create_gtm_datacenter()")

    nickname = dc["nickname"]

    # ============================================================
    # STEP 1 — LIST EXISTING DATACENTERS
    # ============================================================
    list_url = f"{baseurl}/config-gtm/v1/domains/{domain}/datacenters"

    list_params = {}
    if accountSwitchKey:
        list_params["accountSwitchKey"] = accountSwitchKey

    # Correct media type for listing datacenters
    list_headers = {
        "accept": "application/vnd.config-gtm.v1.6+json"
    }

    resp = session.get(list_url, params=list_params, headers=list_headers)
    resp.raise_for_status()

    items = resp.json().get("items", [])

    # Search for existing DC with same nickname
    existing = next((x for x in items if x.get("nickname") == nickname), None)

    if existing:
        dc_id = existing["datacenterId"]
        print(f"\n[INFO] Datacenter '{nickname}' already exists with ID={dc_id}.")
        ans = input(f"Reuse existing datacenter '{nickname}' (ID={dc_id})? (yes/no): ").strip().lower()

        if ans not in ("yes", "y"):
            print("\n[ABORT] User chose not to reuse existing datacenter.")
            sys.exit(1)

        print(f"[INFO] Reusing existing datacenter ID={dc_id}")
        print("<<< EXIT: create_gtm_datacenter()")

        return {
            "datacenterId": dc_id,
            "servers": dc["servers"]
        }

    # ============================================================
    # STEP 2 — CREATE NEW DATACENTER
    # ============================================================
    print(f"[INFO] Creating new datacenter '{nickname}'")

    create_url = f"{baseurl}/config-gtm/v1/domains/{domain}/datacenters"

    create_params = {
        "contractId": contractId,
        "gid": groupId.replace("grp_", "")
    }
    if accountSwitchKey:
        create_params["accountSwitchKey"] = accountSwitchKey

    payload = {
        "city": dc["city"],
        "country": dc["country"],
        "stateOrProvince": dc["stateOrProvince"],
        "latitude": dc["latitude"],
        "longitude": dc["longitude"],
        "nickname": nickname
    }

    pp(session_verbose, "POST Datacenter Payload", payload)

    create_headers = {
        "Content-Type": "application/json",
        "accept": "application/vnd.config-gtm.v1.7+json"
    }

    create_resp = session.post(create_url, params=create_params, json=payload, headers=create_headers)

    print("[INFO] Status:", create_resp.status_code)
    dbg(session_verbose, f"[DEBUG] Response: {create_resp.text}")

    create_resp.raise_for_status()

    new_id = create_resp.json()["resource"]["datacenterId"]

    print(f"[SUCCESS] New datacenter created: ID={new_id}")
    print("<<< EXIT: create_gtm_datacenter()")

    return {
        "datacenterId": new_id,
        "servers": dc["servers"]
    }


# ============================================================
# WAIT FOR PROPAGATION
# ============================================================
def wait_for_gtm_propagation(session, baseurl, domain, accountSwitchKey):
    print("\n>>> ENTER: wait_for_gtm_propagation()")

    params = {}
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    url = f"{baseurl}/config-gtm/v1/domains/{domain}/status/current"

    for attempt in range(20):
        resp = session.get(url, params=params)
        status = resp.json().get("propagationStatus")

        print(f"[STATUS] Propagation: {status}")

        if status == "COMPLETE":
            print("[SUCCESS] GTM propagation complete.")
            return True

        time.sleep(5)

    print("[TIMEOUT] Propagation did not complete; continuing anyway.")
    return False


# ============================================================
# CREATE GTM PROPERTY
# ============================================================
def create_gtm_property(session, baseurl, domain, config, datacenters, contractId, groupId, accountSwitchKey, session_verbose):
    print("\n>>> ENTER: create_gtm_property()")

    groupId_clean = groupId.replace("grp_", "")

    liveness_host = config["livenessHostHeader"]
    weight_each = int(100 / len(datacenters))

    payload = {
        "dynamicTTL": 60,
        "handoutMode": "normal",
        "ipv6": False,
        "scoreAggregationType": "worst",

        "livenessTests": [
            {
                "hostHeader": liveness_host,
                "name": "Liveness",
                "testObject": config["livenessTestObject"],
                "testObjectPort": 443,
                "testObjectProtocol": "HTTPS",
                "testInterval": 60,
                "testTimeout": 10,
                "httpHeaders": [{"name": "Host", "value": liveness_host}],
                "httpMethod": "GET"
            }
        ],

        "trafficTargets": [
            {
                "datacenterId": dc["datacenterId"],
                "enabled": True,
                "servers": dc["servers"],
                "weight": weight_each
            }
            for dc in datacenters
        ],

        "type": config.get("propertyType", "performance"),
        "name": config["gtmPropertyName"],
        "handoutLimit": 1
    }

    pp(session_verbose, "PROPERTY PAYLOAD", payload)

    params = {
        "contractId": contractId,
        "gid": groupId_clean
    }

    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    url = f"{baseurl}/config-gtm/v1/domains/{domain}/properties/{config['gtmPropertyName']}"

    headers = {
        "accept": "application/vnd.config-gtm.v1.7+json",
        "content-type": "application/vnd.config-gtm.v1.6+json"
    }

    print("[INFO] Sending GTM Property PUT...")

    resp = session.put(url, params=params, json=payload, headers=headers)

    print("[INFO] Status:", resp.status_code)
    dbg(session_verbose, f"[DEBUG] Response: {resp.text}")

    resp.raise_for_status()

    print("<<< EXIT: create_gtm_property()")

    return resp.json()


# ============================================================
# MAIN WORKFLOW
# ============================================================
def run_gtm_workflow(session, baseurl, config, activationMode, accountSwitchKey, verbose):
    print("\n>>> ENTER: run_gtm_workflow()")

    session_verbose = {"verbose": verbose}

    domain = config["gtmDomain"]
    contractId = config["contractId"]
    groupId = config["groupId"]

    # ============================================================
    # Step 0 — Check/Create GTM Domain
    # ============================================================
    domain_details = get_gtm_domain(session, baseurl, domain, accountSwitchKey)

    if not domain_details:
        print(f"[INFO] Domain '{domain}' does not exist — attempting create...")

        try:
            domain_details = create_gtm_domain(
                session, baseurl, config,
                accountSwitchKey, verbose
            )
        except Exception as e:
            if "contractAccessProblem" in str(e):
                handle_domain_forbidden(domain)
            else:
                print(f"[ERROR] Unexpected GTM domain creation error: {e}")
                sys.exit(1)

    # ============================================================
    # Step 1 — Load CSV Datacenters
    # ============================================================
    csv_dcs = load_datacenters_from_csv(config["datacenterDetails"], session_verbose)

    # ============================================================
    # Step 2 — Create DCs
    # ============================================================
    created_dcs = []
    for dc in csv_dcs:
        created = create_gtm_datacenter(
            session, baseurl, domain, dc,
            contractId, groupId, accountSwitchKey,
            session_verbose
        )
        created_dcs.append(created)

    # ============================================================
    # Step 3 — Wait for propagation
    # ============================================================
    wait_for_gtm_propagation(session, baseurl, domain, accountSwitchKey)

    # ============================================================
    # Step 4 — Create GTM Property
    # ============================================================
    gtm_result = create_gtm_property(
        session, baseurl, domain, config,
        created_dcs, contractId, groupId, accountSwitchKey,
        session_verbose
    )

    print("<<< EXIT: run_gtm_workflow()")

    return {
        "domain": domain_details,
        "datacentersCreated": len(created_dcs),
        "gtmProperty": gtm_result,
        "propagationWait": True
    }
