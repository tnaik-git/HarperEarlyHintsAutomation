import json
from urllib.parse import urljoin
from helpers import dbg


# ------------------------------------------------------
# Load the Harper rule JSON template
# ------------------------------------------------------
def load_harper_rule(path="data/harper_redirect_earlyhints_rule.json", verbose=False):
    dbg(verbose, f"Loading Harper Redirect + Early Hints rule from {path}")
    with open(path, "r") as f:
        return json.load(f)


# ------------------------------------------------------
# Inject EdgeWorker ID into the rule JSON
# ------------------------------------------------------
def inject_edgeworker_id(rule, ew_id, verbose=False):
    dbg(verbose, f"Injecting EdgeWorker ID {ew_id} into Harper rule")

    def recurse(node):
        if isinstance(node, dict):
            for key, val in node.items():
                if key == "edgeWorkerId":
                    node[key] = str(ew_id)
                else:
                    recurse(val)
        elif isinstance(node, list):
            for child in node:
                recurse(child)

    recurse(rule)
    return rule


# ------------------------------------------------------
# Inject ONLY required PMUSER variables
# ------------------------------------------------------
REQUIRED_VARIABLES = [
    "PMUSER_103_HINTS",
    "PMUSER_103_HINTS_ENABLED"
]

def inject_required_variables(rule_tree, verbose=False):
    dbg(verbose, "Ensuring required PMUSER variables exist...")

    rules = rule_tree["rules"]

    if "variables" not in rules:
        rules["variables"] = []

    existing_vars = {v["name"] for v in rules["variables"]}

    for var in REQUIRED_VARIABLES:
        if var not in existing_vars:
            dbg(verbose, f"Creating missing PMUSER variable: {var}")
            rules["variables"].append({
                "name": var,
                "value": "",
                "description": ""
            })

    return rule_tree


# ------------------------------------------------------
# GET PROPERTY RULE TREE
# ------------------------------------------------------
def get_property_rules(session, baseurl, propertyId, propertyVersion,
                       accountSwitchKey, verbose=False):

    dbg(verbose, f"Fetching rule tree for {propertyId} version {propertyVersion}")

    path = f"/papi/v1/properties/{propertyId}/versions/{propertyVersion}/rules"
    params = {}
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    url = urljoin(baseurl, path)
    dbg(verbose, f"GET {url}")

    resp = session.get(url, params=params, headers={"Accept": "application/json"})

    if resp.status_code != 200:
        raise Exception(f"Failed to fetch rule tree: {resp.text}")

    return resp.json()


# ------------------------------------------------------
# CREATE NEW VERSION
# ------------------------------------------------------
def create_new_property_version(session, baseurl, propertyId, oldVersion,
                                accountSwitchKey, verbose=False):

    dbg(verbose, f"Creating new property version from {oldVersion}")

    path = f"/papi/v1/properties/{propertyId}/versions"
    params = {}

    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    url = urljoin(baseurl, path)

    payload = {"createFromVersion": oldVersion}

    resp = session.post(url, params=params,
                        headers={"Content-Type": "application/json"},
                        data=json.dumps(payload))

    if resp.status_code not in (200, 201):
        raise Exception(f"Failed to create new version: {resp.text}")

    version_link = resp.json().get("versionLink", "")
    new_version = int(version_link.split("/")[-1].split("?")[0])

    dbg(verbose, f"Created new version = {new_version}")
    return new_version


# ------------------------------------------------------
# UPDATE PROPERTY RULE TREE
# ------------------------------------------------------
def update_property_rules(session, baseurl, propertyId, newVersion, rule_tree,
                          accountSwitchKey, verbose=False):

    dbg(verbose, f"Uploading updated rule tree to version {newVersion}")

    path = f"/papi/v1/properties/{propertyId}/versions/{newVersion}/rules"
    params = {}
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    url = urljoin(baseurl, path)

    resp = session.put(url,
                       params=params,
                       headers={"Content-Type": "application/json"},
                       data=json.dumps(rule_tree))

    if resp.status_code != 200:
        raise Exception(f"Failed to update rule tree: {resp.text}")

    dbg(verbose, "Rule tree updated.")
    return resp.json()


# ------------------------------------------------------
# ACTIVATE NEW VERSION (respects activationMode)
# ------------------------------------------------------
def activate_property(session, baseurl, propertyId, version,
                      email, activationMode, accountSwitchKey, verbose=False):

    mode = activationMode.lower()

    if mode == "saveonly":
        print("[INFO] Activation skipped (saveonly mode).")
        return {"activation": "skipped"}

    network = "STAGING" if mode == "staging" else "PRODUCTION"

    dbg(verbose, f"Activating version {version} on {network}")

    path = f"/papi/v1/properties/{propertyId}/activations"
    params = {}

    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    url = urljoin(baseurl, path)

    payload = {
        "propertyVersion": int(version),
        "network": network,
        "notifyEmails": [email],
        "activationType": "ACTIVATE",
        "note": "Automated Harper Redirect + Early Hints injection",
        "acknowledgeAllWarnings": True
    }

    dbg(verbose, f"Activation payload: {payload}")

    resp = session.post(url, params=params,
                        headers={"Content-Type": "application/json"},
                        json=payload)

    if resp.status_code not in (200, 201):
        raise Exception(f"Activation failed: {resp.text}")

    print(f"[SUCCESS] Activation submitted → {network}")
    return resp.json()


# ------------------------------------------------------
# MAIN WORKFLOW
# ------------------------------------------------------
def run_harper_redirect_earlyhints_workflow(
    session,
    baseurl,
    config,
    ew_id,
    propertyId,
    propertyVersion,
    activationMode,
    accountSwitchKey,
    verbose=False
):
    print("\n=== HARPER REDIRECT + EARLY HINTS WORKFLOW START ===")

    email = config["activationEmails"]
    results = {}

    # 1) Fetch rule tree
    rule_tree = get_property_rules(
        session, baseurl, propertyId, propertyVersion,
        accountSwitchKey, verbose
    )

    # 2) Load template
    harper_rule = load_harper_rule(verbose=verbose)

    # 3) Inject EW ID
    harper_rule = inject_edgeworker_id(harper_rule, ew_id, verbose)

    # 4) Ensure PMUSER vars exist
    rule_tree = inject_required_variables(rule_tree, verbose)

    # 5) Insert Harper rule
    dbg(verbose, "Inserting Harper rule into rule tree…")

    rules_node = rule_tree.get("rules")
    children = rules_node.setdefault("children", [])

    cond_orig_idx = adv_idx = None

    for i, child in enumerate(children):
        behaviors = child.get("behaviors", [])

        if any(b.get("name") == "allowConditionalOrigins" for b in behaviors):
            cond_orig_idx = i
        if any(b.get("name") in ("advanced", "advancedOverride") for b in behaviors):
            adv_idx = i

    indices = [x for x in (adv_idx, cond_orig_idx) if x is not None]
    insert_index = min(indices) if indices else len(children)

    children.insert(insert_index, harper_rule)

    # 6) Create new version
    new_version = create_new_property_version(
        session, baseurl,
        propertyId, propertyVersion,
        accountSwitchKey, verbose
    )
    results["newVersion"] = new_version

    # 7) Upload rule updates
    update_resp = update_property_rules(
        session, baseurl,
        propertyId, new_version,
        rule_tree,
        accountSwitchKey, verbose
    )
    results["updateResponse"] = update_resp

    # 8) Activate
    activation_resp = activate_property(
        session, baseurl,
        propertyId, new_version,
        email,
        activationMode,
        accountSwitchKey,
        verbose
    )
    results["activation"] = activation_resp

    print("\n=== HARPER REDIRECT + EARLY HINTS WORKFLOW COMPLETE ===")
    return results
