import json
import requests
import sys
from helpers import dbg


# ===================================================================
#  CP CODE CREATION
# ===================================================================
def create_cpcode(session, baseurl, cpcode_name, contractId, groupId, accountSwitchKey, verbose):
    dbg(verbose, f"ENTER create_cpcode(cpcode={cpcode_name})")

    url = f"{baseurl}/papi/v1/cpcodes"

    params = {
        "contractId": contractId,
        "groupId": groupId,
        "PAPI-Use-Prefixes": "true"
    }
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = {
        "cpcodeName": cpcode_name,
        "productId": "prd_SPM"
    }

    dbg(verbose, f"POST {url}")
    dbg(verbose, f"Payload: {payload}")

    resp = session.post(url, params=params, json=payload)

    if resp.status_code != 201:
        raise Exception(f"CP Code creation failed: {resp.text}")

    link = resp.json().get("cpcodeLink")
    cpcodeId = link.split("/cpcodes/")[1].split("?")[0]

    print(f"[SUCCESS] Created CP Code {cpcodeId}")
    return cpcodeId, cpcode_name



# ===================================================================
#  CREATE PROPERTY
# ===================================================================
def create_property(session, baseurl, propertyName, contractId, groupId, accountSwitchKey, verbose):
    dbg(verbose, f"ENTER create_property({propertyName})")

    url = f"{baseurl}/papi/v1/properties"

    params = {
        "contractId": contractId,
        "groupId": groupId,
        "PAPI-Use-Prefixes": "true"
    }
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = {
        "productId": "prd_SPM",
        "propertyName": propertyName,
        "ruleFormat": "latest"
    }

    resp = session.post(url, params=params, json=payload)

    if resp.status_code not in (200, 201):
        raise Exception(f"Property creation failed: {resp.text}")

    propertyId = resp.json()["propertyLink"].split("/properties/")[1].split("?")[0]

    print(f"[SUCCESS] Created PM property {propertyId}")
    return propertyId, 1



# ===================================================================
#  ADD INTERNAL HOSTNAME
# ===================================================================
def add_internal_hostname(session, baseurl, propertyId, version,
                          cname_from, edge_hostname,
                          contractId, groupId, accountSwitchKey, verbose):

    dbg(verbose, f"ENTER add_internal_hostname({cname_from})")

    url = f"{baseurl}/papi/v1/properties/{propertyId}/versions/{version}/hostnames"

    params = {
        "contractId": contractId,
        "groupId": groupId,
        "validateHostnames": "true",
        "PAPI-Use-Prefixes": "true"
    }
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = [{
        "certProvisioningType": "DEFAULT",
        "cnameFrom": cname_from,
        "cnameTo": edge_hostname,
        "cnameType": "EDGE_HOSTNAME"
    }]

    resp = session.put(url, params=params, json=payload)

    if resp.status_code not in (200, 201):
        raise Exception(f"Failed adding hostname: {resp.text}")

    print("[SUCCESS] Internal hostname added.")



# ===================================================================
#  DOWNLOAD RULE TREE
# ===================================================================
def get_rule_tree(session, baseurl, propertyId, version,
                  contractId, groupId, accountSwitchKey, verbose):

    dbg(verbose, "ENTER get_rule_tree()")

    url = f"{baseurl}/papi/v1/properties/{propertyId}/versions/{version}/rules"

    params = {
        "contractId": contractId,
        "groupId": groupId,
        "PAPI-Use-Prefixes": "true"
    }
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    resp = session.get(url, params=params)

    if resp.status_code != 200:
        raise Exception(f"Failed to fetch rule tree: {resp.text}")

    data = resp.json()
    return data["rules"], data["etag"]



# ===================================================================
#  UPDATE ORIGIN
# ===================================================================
def update_origin_behavior1(rules, origin_hostname, custom_forward_header, verbose):
    dbg(verbose, "ENTER update_origin_behavior()")

    for b in rules.get("behaviors", []):
        if b["name"] == "origin":
            b["options"]["hostname"] = origin_hostname
            b["options"]["forwardHostHeader"] = "CUSTOM"
            b["options"]["customForwardHostHeader"] = custom_forward_header

    print("[SUCCESS] Updated origin behavior.")

def update_origin_behavior(rules, origin_hostname, custom_forward_header, verbose):
    dbg(verbose, "ENTER update_origin_behavior()")

    for b in rules.get("behaviors", []):
        if b["name"] == "origin":

            opts = b["options"]

            # KEEP THESE EXACTLY AS REQUESTED
            opts["hostname"] = origin_hostname
            opts["forwardHostHeader"] = "CUSTOM"
            opts["customForwardHostHeader"] = custom_forward_header

            # === UPDATE ALL OTHER SETTINGS TO MATCH THE REQUIRED TEMPLATE ===
            opts["cacheKeyHostname"] = "REQUEST_HOST_HEADER"
            opts["compress"] = True
            opts["enableTrueClientIp"] = True
            opts["httpPort"] = 80
            opts["httpsPort"] = 443
            opts["minTlsVersion"] = "DYNAMIC"
            opts["originCertificate"] = ""
            opts["originSni"] = True
            opts["originType"] = "CUSTOMER"
            opts["ports"] = ""
            opts["tlsVersionTitle"] = ""
            opts["trueClientIpClientSetting"] = False
            opts["trueClientIpHeader"] = "True-Client-IP"
            opts["verificationMode"] = "CUSTOM"
            opts["ipVersion"] = "IPV4"

            # Valid CN values
            opts["customValidCnValues"] = [
                "{{Origin Hostname}}",
                "{{Forward Host Header}}"
            ]

            # Certificate policy
            opts["originCertsToHonor"] = "STANDARD_CERTIFICATE_AUTHORITIES"
            opts["standardCertificateAuthorities"] = [
                "akamai-permissive",
                "THIRD_PARTY_AMAZON"
            ]

            # REMOVE fields that should not exist
            for bad_field in [
                "customCertificates",
                "customCertificateAuthorities"
            ]:
                if bad_field in opts:
                    del opts[bad_field]

    print("[SUCCESS] Updated origin behavior.")



# ===================================================================
#  REMOVE CHILDREN UNDER “Offload origin”
# ===================================================================
def remove_offload_origin_children(rules, verbose):
    dbg(verbose, "ENTER remove_offload_origin_children()")

    for child in rules.get("children", []):
        if child["name"] == "Offload origin":
            child["children"] = []

    print("[SUCCESS] Removed Offload origin children.")



# ===================================================================
# REMOVE enhancedDebug
# ===================================================================
def remove_enhanced_debug(rules, verbose):
    dbg(verbose, "ENTER remove_enhanced_debug()")

    rules["behaviors"] = [b for b in rules.get("behaviors", [])
                          if b.get("name") != "enhancedDebug"]

    print("[SUCCESS] Removed enhancedDebug.")



# ===================================================================
# UPDATE CP CODE
# ===================================================================
def update_cpcode_in_traffic_reporting(rules, cpcodeId, cpcodeName, verbose):
    dbg(verbose, "ENTER update_cpcode_in_traffic_reporting()")

    for parent in rules.get("children", []):
        if parent["name"] == "Augment insights":
            for child in parent.get("children", []):
                if child["name"] == "Traffic reporting":
                    child["behaviors"] = [{
                        "name": "cpCode",
                        "options": {
                            "enableDefaultContentProviderCode": False,
                            "value": {
                                "id": int(cpcodeId.replace("cpc_", "")),
                                "name": cpcodeName
                            }
                        }
                    }]

    print("[SUCCESS] Updated CP Code.")



# ===================================================================
# UPLOAD RULE TREE
# ===================================================================
def upload_rules(session, baseurl, propertyId,
                 contractId, groupId, rules, accountSwitchKey, verbose):

    dbg(verbose, "ENTER upload_rules()")

    url = f"{baseurl}/papi/v1/properties/{propertyId}/versions/1/rules"

    params = {
        "contractId": contractId,
        "groupId": groupId,
        "validateRules": "false",
        "PAPI-Use-Prefixes": "true"
    }
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = {"rules": rules}

    resp = session.put(url, params=params, json=payload)

    if resp.status_code not in (200, 201):
        raise Exception(f"Rule upload failed: {resp.text}")

    print("[SUCCESS] Uploaded rule tree.")
    return 1



# ===================================================================
# ACTIVATE PROPERTY VERSION
# ===================================================================
def activate_property_version(session, baseurl, propertyId, version,
                              contractId, groupId, network, emails, accountSwitchKey, verbose):

    dbg(verbose, f"ENTER activate_property_version({network})")

    url = f"{baseurl}/papi/v1/properties/{propertyId}/activations"

    params = {
        "contractId": contractId,
        "groupId": groupId,
        "PAPI-Use-Prefixes": "true"
    }
    if accountSwitchKey:
        params["accountSwitchKey"] = accountSwitchKey

    payload = {
        "propertyVersion": int(version),
        "network": network.upper(),
        "note": "Internal config activation via automation",
        "notifyEmails": emails if isinstance(emails, list) else [emails],
        "acknowledgeWarnings": []
    }

    resp = session.post(url, params=params, json=payload)

    if resp.status_code not in (200, 201):
        raise Exception(f"Activation failed: {resp.text}")

    print(f"[SUCCESS] Activation submitted for {network}.")



# ===================================================================
# MASTER WORKFLOW
# ===================================================================
def run_pm_workflow(session, baseurl, config, activationMode, accountSwitchKey, verbose):
    print("\n>>> ENTER: run_pm_workflow()")

    try:
        pm_cfg = config["propertyManager"]
        cfg = pm_cfg["internalHarperHostname"]

        contractId = config["contractId"]
        groupId = config["groupId"]

        internal_pm_name = cfg["internalPmConfigName"]
        internal_hostname = cfg["internalHostname"]
        edge_hostname = cfg["edgeHostname"]
        origin_hostname = cfg["originHostname"]
        forward_header = cfg["forwardCustomHeader"]

        print(f"[INFO] Creating Internal Config: {internal_pm_name}")

        # ========================================================
        # CREATE CP CODE
        # ========================================================
        cpcodeId, cpcodeName = create_cpcode(
            session, baseurl, internal_hostname,
            contractId, groupId, accountSwitchKey, verbose
        )

        # ========================================================
        # CREATE PM PROPERTY
        # ========================================================
        propertyId, version = create_property(
            session, baseurl,
            internal_pm_name,
            contractId, groupId, accountSwitchKey, verbose
        )

        # ========================================================
        # ADD INTERNAL HOSTNAME
        # ========================================================
        add_internal_hostname(
            session, baseurl,
            propertyId, version,
            internal_hostname, edge_hostname,
            contractId, groupId, accountSwitchKey, verbose
        )

        # ========================================================
        # GET RULE TREE
        # ========================================================
        rules, etag = get_rule_tree(
            session, baseurl,
            propertyId, version,
            contractId, groupId, accountSwitchKey, verbose
        )

        # ========================================================
        # UPDATE RULE LOGIC
        # ========================================================
        update_origin_behavior(rules, origin_hostname, forward_header, verbose)
        remove_offload_origin_children(rules, verbose)
        remove_enhanced_debug(rules, verbose)
        update_cpcode_in_traffic_reporting(rules, cpcodeId, cpcodeName, verbose)

        # ========================================================
        # UPLOAD UPDATED RULE TREE
        # ========================================================
        new_version = upload_rules(
            session, baseurl, propertyId,
            contractId, groupId, rules,
            accountSwitchKey, verbose
        )

        print(f"[SUCCESS] Internal property updated → version {new_version}")

        # ========================================================
        # ACTIVATION (based on CLI)
        # ========================================================
        if activationMode.lower() == "saveonly":
            print("[INFO] Activation skipped (saveonly mode).")
        else:
            emails = config["activationEmails"]

            activate_property_version(
                session, baseurl,
                propertyId, new_version,
                contractId, groupId,
                activationMode,
                emails,
                accountSwitchKey,
                verbose
            )

    except Exception as e:
        print(f"[ERROR] PM workflow failed: {e}")
        raise

    print("<<< EXIT: run_pm_workflow()")
