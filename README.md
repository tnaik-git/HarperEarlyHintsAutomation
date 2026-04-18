# 🌐 Harper EarlyHints & Redirect Automation

Automation framework for deploying the full Harper EarlyHints + Redirect stack across Akamai GTM, Property Manager (internal + customer-facing), and EdgeWorkers.

This tool streamlines all required Akamai workflows into a **single Python-based automation pipeline**, including:

- GTM Domain creation  
- GTM Datacenters (create or reuse)  
- GTM Property creation + liveness test configuration  
- Internal PM config creation  
- EdgeWorker packaging, upload, and activation  
- EdgeWorker source from **local files or GitHub repository**
- Customer-facing PM rule injection (Harper EarlyHints + Redirect logic)  
- Unified activation logic (`staging`, `production`, or `saveonly`)  
- Skip flags to resume partial runs without re-running completed steps
- Optional verbose logging  
- Optional accountSwitchKey support  

---

# 🚀 1. Prerequisites

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

### ✔ Install dependencies

```
pip install requests akamai-edgegrid
```

---

# 📁 2. Project Structure

```
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

# 🧩 3. Configuration (requirements.json)

Full example with all supported fields:

```json
{
  "activationEmails": "you@example.com",

  "accountId": "act_1-XXXXX",
  "contractId": "ctr_1-XXXXX",
  "groupId": "grp_XXXXX",

  "skipGtm": false,
  "existingGtmDomain": "",

  "skipPm": false,
  "existingInternalPropertyId": "",

  "skipEdgeworker": false,

  "datacenterDetails": "data/datacenters.csv",
  "gtmPropertyName": "my-gtm-property",
  "gtmDomain": "example.com.hdb.akadns.net",
  "livenessHostHeader": "mcy-pb-prod-gtm.harperdbcloud.com",
  "livenessTestObject": "/status",

  "propertyManager": {
    "productId": "prd_SPM",
    "ruleFormat": "latest",
    "customerFacingHostname": {
      "propertyName": "my-customer-property",
      "propertyVersion": 1,
      "propertyHostnames": [
        "www.example.com"
      ]
    },
    "internalHarperHostname": {
      "internalPmConfigName": "internal-harper-xxx.test.com",
      "internalHostname": "internal-harper-xxx.test.com",
      "edgeHostname": "ion-standard.example.com.edgekey.net",
      "originHostname": "origin.example.com.hdb.akadns.net",
      "forwardCustomHeader": "origin.harperdbcloud.com"
    }
  },

  "edgeworker": {
    "name": "Harper-Earlyhints",
    "description": "harperEarlyhints",
    "resourceTierId": 200,
    "harper_token": "YOUR_AUTH_TOKEN_HERE",
    "github": {
      "enabled": false,
      "repo": "akamai/edgeworkers-examples",
      "branch": "master",
      "main_js_path": "edgecompute/examples/103-early-hints/basic/main.js",
      "bundle_json_path": "edgecompute/examples/103-early-hints/basic/bundle.json",
      "token": ""
    }
  }
}
```

---

# 🛠 4. CLI Flags

| Flag | Description |
|---|---|
| `--activation-network` | **Required.** `staging`, `production`, or `saveonly` |
| `--account-switch-key` | Optional Akamai accountSwitchKey |
| `--verbose` | Enable detailed debug logging |
| `--skip-gtm` | Skip GTM workflow, reuse existing domain |
| `--skip-pm` | Skip internal Property Manager workflow |
| `--skip-edgeworker` | Skip EdgeWorker creation, reuse existing EW ID |
| `--github-bundle` | Pull `main.js` + `bundle.json` from GitHub instead of local files |

---

# ▶️ 5. Running the Automation

### Full run — everything from scratch:
```bash
python3 main.py --activation-network staging \
  --account-switch-key <your-key>
```

### Save only — no activation:
```bash
python3 main.py --activation-network saveonly \
  --account-switch-key <your-key>
```

### Skip GTM — reuse existing domain:
```bash
python3 main.py --activation-network staging \
  --account-switch-key <your-key> \
  --skip-gtm
```

### Skip GTM + PM — only run EdgeWorker + Harper rule:
```bash
python3 main.py --activation-network staging \
  --account-switch-key <your-key> \
  --skip-gtm \
  --skip-pm
```

### Skip everything except Harper rule injection:
```bash
python3 main.py --activation-network saveonly \
  --account-switch-key <your-key> \
  --skip-gtm \
  --skip-pm \
  --skip-edgeworker
```
> Requires `edgeworker.existingEdgeWorkerId` set in `requirements.json`.

### Pull EdgeWorker bundle from GitHub:
```bash
python3 main.py --activation-network saveonly \
  --account-switch-key <your-key> \
  --skip-gtm \
  --skip-pm \
  --github-bundle
```

### Full run with GitHub bundle + verbose logging:
```bash
python3 main.py --activation-network staging \
  --account-switch-key <your-key> \
  --github-bundle \
  --verbose
```

### Production deploy with GitHub bundle:
```bash
python3 main.py --activation-network production \
  --account-switch-key <your-key> \
  --skip-gtm \
  --skip-pm \
  --github-bundle
```

---

# 🔄 6. What the Script Does

Each run executes these components **in order**:

### 1️⃣ GTM Workflow _(skippable with `--skip-gtm`)_
- Detect if GTM domain exists
- Create domain (unless contractAccessProblem → manual prompt)
- Load datacenters from CSV
- Create datacenters or reuse existing ones
- Create/Update GTM property
- Wait for propagation

### 2️⃣ Internal PM Workflow _(skippable with `--skip-pm`)_
- Create CP Code  
- Create internal PM config  
- Add Edge Hostname  
- Update origin behavior  
- Remove "enhancedDebug" and "Offload origin" children  
- Update CP Code in "Traffic reporting"  
- Upload new version  
- Activate if staging/production  

### 3️⃣ EdgeWorker Workflow _(skippable with `--skip-edgeworker`)_
- **[Optional]** Fetch `main.js` + `bundle.json` from GitHub (`--github-bundle`)
- Inject Harper token + internal hostname into `main.js`
- Create `.tgz` bundle
- Create new EdgeWorker ID
- Upload version
- Activate (unless saveonly)

### 4️⃣ Customer-Facing PM Workflow _(always runs if EW ID is available)_
- Fetch rule tree for customer-facing property  
- Load Harper Redirect + EarlyHints rule template
- Inject new EdgeWorker ID into rule
- Insert Harper rule before Conditional Origins / Advanced Override  
- Create new property version  
- Upload updated rule tree  
- Activate depending on `--activation-network`

---

# 🐙 7. GitHub Bundle Source

Instead of using local `data/edgeworker/main.js` and `bundle.json`, you can pull directly from a GitHub repository.

**Configure in `requirements.json`:**
```json
"edgeworker": {
  "github": {
    "enabled": false,
    "repo": "akamai/edgeworkers-examples",
    "branch": "master",
    "main_js_path": "edgecompute/examples/103-early-hints/basic/main.js",
    "bundle_json_path": "edgecompute/examples/103-early-hints/basic/bundle.json",
    "token": ""
  }
}
```

- Leave `enabled: false` and use `--github-bundle` CLI flag to enable per run
- Or set `enabled: true` to always pull from GitHub
- `token` is only needed for private repositories

---

# 📄 8. Output (result.json)

Written after every run:

```json
{
  "timestamp": "2026-04-02T12:00:00Z",
  "customerFacingPropertyId": "prp_XXXXXX",
  "customerFacingPropertyVersion": 1,
  "gtm": { },
  "propertyManager": { },
  "edgeworker": {
    "edgeWorkerId": 106819,
    "version": "1.0",
    "activation": "skipped (saveonly)"
  },
  "harperRule": {
    "newVersion": 9,
    "activation": { }
  }
}
```

---

# 🧪 9. Verbose Logging

Enable detailed output with `--verbose`:

- API URLs and query params
- Request payloads
- Response bodies
- Logic paths and variable values

---

# ❗ 10. Troubleshooting

### 403 on GTM Domain Creation
You may not have API permission to create GTM domains. The script will print manual instructions. Create the domain in Akamai Control Center then rerun with `--skip-gtm`.

### Property name already in use
A previous run already created the internal PM property. Use `--skip-pm` to skip creation and reuse it.

### EW ID limit reached (EW3002)
Your account has hit the Akamai EdgeWorker ID cap. Delete unused EdgeWorker IDs in Akamai Control Center, then rerun.

### Datacenter already exists
The script will prompt:
```
Reuse existing datacenter '<name>'? (yes/no)
```

### GitHub fetch fails (404)
Check that `repo`, `branch`, and file paths in `requirements.json` are correct. For private repos, set `token`.

---

# 🎉 Summary

This automation fully deploys:

- GTM Domain + Datacenters  
- GTM Property  
- Internal PM Config  
- EdgeWorker (from local files or GitHub)
- Customer PM Rule Tree with Harper EarlyHints + Redirect

All orchestrated to deliver the **Harper EarlyHints + Redirect** solution in one execution, with full flexibility to skip completed steps on reruns.