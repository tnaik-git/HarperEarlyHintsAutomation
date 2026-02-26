# Harper EarlyHints & Redirect Automation

Automation framework for deploying the full Harper EarlyHints + Redirect stack across Akamai GTM, Property Manager (internal + customer-facing), and EdgeWorkers.

This tool streamlines all required Akamai workflows into a **single Python-based automation pipeline**, including:

- GTM Domain creation  
- GTM Datacenters (create or reuse)  
- GTM Property creation + liveness test configuration  
- Internal PM config creation  
- EdgeWorker packaging, upload, and activation  
- Customer-facing PM rule injection (Harper EarlyHints + Redirect logic)  
- Unified activation logic (`staging`, `production`, or `saveonly`)  
- Optional verbose logging  
- Optional accountSwitchKey support  


---

# 1. Prerequisites

### ✔ Python 3.8+
### ✔ Akamai EdgeGrid credentials

Ensure your `~/.edgerc` contains:

```
[default]
host = akab-xxxxxxx.luna.akamaiapis.net
client_token = ...
client_secret = ...
access_token = ...
```

### Install dependencies

```
pip install requests akamai-edgegrid
```

---

# 2. Project Structure and - [Architecture Overview]

```
[Architecture Overview](ARCHITECTURE.md)

harperEarlyAutomation/
│
├── main.py
├── helpers.py
├── manage_gtm.py
├── manage_edgeworker.py
├── manage_property_manager.py
├── manage_customer_property.py
├── requirements.json
├── result.json
│
└── data/
     ├── datacenters.csv
     ├── harper_redirect_earlyhints_rule.json
     └── edgeworker/
          ├── main.js
          ├── bundle.json
```
---

# 3. Configuration (requirements.json)

You must provide (or the tool will prompt for) required fields.

Example:

```json
{
  "activationEmails": "tnaik@akamai.com",
  "changesBasedOnVersion#": 174,

  "accountId": "act_1-6JHGX",
  "contractId": "ctr_1-1NC95D",
  "groupId": "grp_65552",

  "datacenterDetails": "data/datacenters.csv",
  "gtmPropertyName": "test2-gtm",
  "gtmDomain": "tnaik1.com.hdb.akadns.net",
  "livenessHostHeader": "pb-prod-gtm.harperdbcloud.com",
  "livenessTestObject": "/status",

  "propertyManager": {
    "productId": "prd_SPM",
    "ruleFormat": "latest",
    "customerFacingHostname": {
      "propertyId": "prp_476348",
      "propertyName": "tnaik-ion-standard",
      "propertyVersion": 174,
      "propertyHostnames": [
        "mcy-rd-prod-gtm.tnaik.com",
        "mcy-rd-prod-gtm2.tnaik.com"
      ]
    },
    "internalHarperHostname": {
      "internalPmConfigName": "13internal-harper-xxx.test.com",
      "internalHostname": "internal-harper-xxx.test.com",
      "edgeHostname": "ion-standard.tnaik.com.edgekey.net",
      "originHostname": "test2-gtm.tnaik1.com.hdb.akadns.net",
      "forwardCustomHeader": "pb-prod-gtm.harperdbcloud.com"
    }
  },

  "edgeworker": {
    "name": "Harper-Earlyhints",
    "description": "harperEarlyhints",
    "resourceTierId": 200,
    "tgz": "examples/versions-post.tgz",
    "harper_token": "xxxxxxx"
  }
}
```

---

# 4. Running the Automation

### Basic usage:

```
python3 main.py --activation-network staging
```

### Full CLI options:

```
python3 main.py --activation-network <staging|production|saveonly> \
                --account-switch-key <optional-ask> \
                --verbose
```

---

# 5. What the Script Does

Each run executes these components **in order**:

###  GTM Workflow
- Detect if GTM domain exists
- Create domain (unless contractAccessProblem → manual prompt)
- Load datacenters from CSV
- Create datacenters or reuse existing ones
- Create/Update GTM property
- Wait for propagation

### Internal PM Workflow
- Create CP Code  
- Create internal PM config  
- Add Edge Hostname  
- Update origin behavior  
- Remove “enhancedDebug” and “Offload origin” children  
- Update CP Code in “Traffic reporting”  
- Upload new version  
- Activate if staging/production  

### EdgeWorker Workflow
- Update main.js by injecting Harper token + hostname  
- Create .tgz bundle  
- Create EdgeWorker ID  
- Upload version  
- Activate (unless saveonly)  

### Customer-Facing PM Workflow
- Fetch rule tree for customer-facing property  
- Inject Harper Redirect + EarlyHints rule  
- Insert Harper rule before Conditional Origins / Advanced Override  
- Create new version  
- Upload updated rule tree  
- Activate depending on activationNetwork  

---

# 6. Output (result.json)

Each run appends an object:

```json
[
  {
    "timestamp": "2025-12-05T03:12:00Z",
    "gtm": { },
    "propertyManager": { },
    "edgeworker": { },
    "harperRule": { }
  }
]
```

---

# 7. Verbose Logging

Enable detailed output:

```
--verbose
```

Shows:
- API URLs  
- Payloads  
- Responses  
- Logic paths  

---

# Troubleshooting

### 403 on GTM Domain Creation
You may need to manually create the GTM domain. The script will prompt you.

### Datacenter Already Exists
The script will ask:

```
Reuse existing datacenter Winterfell? (yes/no)
```

### Missing fields
The script interactively updates requirements.json.

---

# Summary

This automation fully deploys:

- GTM Domain + Datacenters  
- GTM Property  
- Internal PM Config  
- EdgeWorker  
- Customer PM Rule Tree  

All orchestrated to deliver the **Harper EarlyHints + Redirect** solution in one execution.

