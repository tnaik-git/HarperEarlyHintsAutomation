import sys
import argparse

from helpers import (
    load_requirements,
    write_result,
    init_edgegrid_session,
    find_property_id_by_name,
    dbg
)

from manage_gtm import run_gtm_workflow
from manage_property_manager import run_pm_workflow
from manage_edgeworker import run_edgeworker_workflow
from manage_customer_property import run_harper_redirect_earlyhints_workflow



# ============================================================
# MAIN
# ============================================================
def main():

    # ---------------------------------------------
    # CLI ARGUMENTS
    # ---------------------------------------------
    parser = argparse.ArgumentParser(description="Harper Early Automation")

    parser.add_argument(
        "--activation-network",
        required=True,
        choices=["staging", "production", "saveonly"],
        help="Activation network for all workflows"
    )

    parser.add_argument(
        "--account-switch-key",
        required=False,
        help="Optional Akamai accountSwitchKey"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    args = parser.parse_args()

    activationMode = args.activation_network.lower()
    accountSwitchKey = args.account_switch_key
    verbose = args.verbose

    print("\n=== Harper Early Automation ===\n")

    # ---------------------------------------------
    # Load requirements
    # ---------------------------------------------
    try:
        config = load_requirements()
        print("[INFO] requirements.json loaded.\n")
    except Exception as e:
        print(f"[ERROR] Could not load requirements.json: {e}")
        sys.exit(1)

    # ---------------------------------------------
    # Initialize EdgeGrid session
    # ---------------------------------------------
    try:
        session, baseurl = init_edgegrid_session(config)
        dbg({"verbose": verbose}, f"Baseurl = {baseurl}")
        print("[INFO] EdgeGrid session initialized.\n")
    except Exception as e:
        print(f"[ERROR] Could not initialize session: {e}")
        sys.exit(1)

    # ---------------------------------------------
    # Resolve Customer-Facing Hostname Property ID
    # ---------------------------------------------
    cf = config["propertyManager"]["customerFacingHostname"]
    propertyName = cf["propertyName"]
    propertyVersion = cf["propertyVersion"]

    contractId = config["contractId"]
    groupId = config["groupId"]

    print("[STEP] Resolving propertyId for customer-facing hostname…")

    try:
        prop_id = find_property_id_by_name(
            session,
            baseurl,
            propertyName,
            contractId,
            groupId,
            accountSwitchKey
        )
    except Exception as e:
        print(f"[ERROR] Unable to resolve propertyId: {e}")
        sys.exit(1)

    print(f"[INFO] Found propertyId = {prop_id}\n")

    results = {
        "customerFacingPropertyId": prop_id,
        "customerFacingPropertyVersion": propertyVersion
    }

    # ============================================================
    # 1. GTM WORKFLOW
    # ============================================================
    try:
        print("[STEP] Running GTM workflow…")
        #gtm_output = run_gtm_workflow(session, baseurl, config, activationMode, accountSwitchKey, verbose)
        #results["gtm"] = gtm_output
        print("[SUCCESS] GTM workflow completed.\n")
    except Exception as e:
        print(f"[ERROR] GTM workflow failed: {e}")
        results["gtm_error"] = str(e)

    # ============================================================
    # 2. PROPERTY MANAGER WORKFLOW (Internal PMconfig to handle Harper traffic)
    # ============================================================
    try:
        print("[STEP] Running Property Manager workflow…")
        pm_output = run_pm_workflow(session, baseurl, config, activationMode, accountSwitchKey, verbose)
        results["propertyManager"] = pm_output
        print("[SUCCESS] PM workflow completed.\n")
    except Exception as e:
        print(f"[ERROR] Property Manager workflow failed: {e}")
        results["pm_error"] = str(e)

    # ============================================================
    # 3. EDGEWORKER WORKFLOW
    # ============================================================
    try:
        print("[STEP] Running EdgeWorker workflow…")
        ew_output = run_edgeworker_workflow(session, baseurl, config, activationMode, accountSwitchKey, verbose)
        results["edgeworker"] = ew_output
        ew_id = ew_output.get("edgeWorkerId")
        print(f"[SUCCESS] EdgeWorker workflow completed. EW ID = {ew_id}\n")
    except Exception as e:
        print(f"[ERROR] EdgeWorker workflow failed: {e}")
        results["edgeworker_error"] = str(e)
        ew_id = None

    # ============================================================
    # 4. CUSTOMER PROPERTY WORKFLOW (Harper Redirect + Early Hints)
    # ============================================================
    if ew_id:
        try:
            print("[STEP] Running Harper Redirect + Early Hints workflow…")

            harper_output = run_harper_redirect_earlyhints_workflow(
                session=session,
                baseurl=baseurl,
                config=config,
                ew_id=ew_id,
                propertyId=prop_id,            # FIXED NAME
                propertyVersion=propertyVersion,
                activationMode=activationMode,
                accountSwitchKey=accountSwitchKey,
                verbose=verbose                   # NEW REQUIRED ARG
            )

            results["harperRule"] = harper_output
            print("[SUCCESS] Harper rule update workflow completed.\n")

        except Exception as e:
            print(f"[ERROR] Harper workflow failed: {e}")
            results["harperRule_error"] = str(e)

    else:
        print("[ERROR] Cannot run Customer Property workflow — EdgeWorker did not return ew_id.")

    # ============================================================
    # Write result.json
    # ============================================================
    try:
        write_result(results)
        print("[SUCCESS] Results written to result.json\n")
    except Exception as e:
        print(f"[ERROR] Unable to write result.json: {e}")

    print("=== Automation Complete ===\n")



# ============================================================
# Program Entry
# ============================================================
if __name__ == "__main__":
    main()
