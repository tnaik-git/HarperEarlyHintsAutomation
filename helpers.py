import json
import os
import datetime
from akamai.edgegrid import EdgeRc, EdgeGridAuth
import requests


# ============================================================
# VERBOSE DEBUG LOGGER
# ============================================================
def dbg(session, msg):
    """Print debug messages only if verbose mode is enabled."""
    if isinstance(session, dict) and session.get("verbose"):
        print(f"[DEBUG] {msg}")


# ============================================================
# Load requirements.json
# ============================================================
def load_requirements():
    """
    Loads the requirements.json file.
    This file contains ONLY user-provided project inputs.
    """
    filename = "requirements.json"

    if not os.path.exists(filename):
        raise Exception(
            f"{filename} not found. Please create it with required fields."
        )

    with open(filename, "r") as f:
        return json.load(f)


# ============================================================
# write_result.json (used by main)
# ============================================================
def write_result(data: dict):
    """
    Writes result.json (overwrites each run).
    main.py constructs the overall results dictionary.
    """
    data["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"

    with open("result.json", "w") as f:
        json.dump(data, f, indent=4)


# ============================================================
# EdgeGrid session initialization
# ============================================================
def init_edgegrid_session(config):
    """
    Creates an EdgeGrid-authenticated session from ~/.edgerc.
    Returns:
        session (requests.Session)
        baseurl (e.g., https://akab-xxx.luna.akamaiapis.net)
    """
    # Load ~/.edgerc credentials
    edgerc = EdgeRc(os.path.expanduser("~/.edgerc"))
    section = "default"

    host = edgerc.get(section, "host")     # e.g., akab-xxxx.luna.akamaiapis.net
    baseurl = f"https://{host}"

    # Prepare EdgeGrid session
    session = requests.Session()
    session.auth = EdgeGridAuth.from_edgerc(edgerc, section)
    session.headers.update({"Content-Type": "application/json"})

    return session, baseurl


# ============================================================
# Timestamp helper
# ============================================================
def now_utc():
    return datetime.datetime.utcnow().isoformat() + "Z"


# ============================================================
# Find propertyId from propertyName using PAPI list-properties
# ============================================================
def find_property_id_by_name(session, baseurl, propertyName, contractId, groupId, accountSwitchKey):
    """
    Performs PAPI GET /papi/v1/properties to resolve propertyId
    from a human-readable propertyName.

    session: requests.Session (EdgeGrid auth)
    baseurl: e.g., https://akab-xxx.luna.akamaiapis.net
    accountSwitchKey: optional, only appended if provided
    """

    print(f"[STEP] Looking up propertyId for propertyName = {propertyName}")

    # Clean contract and group IDs to ensure correct formatting
    contractId_clean = contractId.replace("ctr_", "")
    groupId_clean = groupId.replace("grp_", "")

    suffix = f"&accountSwitchKey={accountSwitchKey}" if accountSwitchKey else ""

    path = (
        f"/papi/v1/properties"
        f"?contractId=ctr_{contractId_clean}"
        f"&groupId=grp_{groupId_clean}"
        f"{suffix}"
    )

    url = baseurl + path
    dbg({"verbose": True}, f"GET {url}")

    result = session.get(url, headers={"Accept": "application/json"})
    dbg({"verbose": True}, f"Response Status = {result.status_code}")

    if result.status_code != 200:
        raise Exception(f"Failed to fetch PAPI properties: {result.text}")

    data = result.json()
    items = data.get("properties", {}).get("items", [])

    for item in items:
        if item.get("propertyName") == propertyName:
            prop_id = item.get("propertyId")
            print(f"[INFO] Found propertyId = {prop_id} for {propertyName}")
            return prop_id

    raise Exception(f"[ERROR] Property '{propertyName}' not found under contract/group.")
