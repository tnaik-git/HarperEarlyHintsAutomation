# Harper EarlyHints Automation

A small automation tool to deploy Harper EarlyHints + Redirect across Akamai GTM, Property Manager, and EdgeWorkers.

Summary
- Automates GTM domain/property setup, internal and customer Property Manager changes, and EdgeWorker packaging/activation.
- Designed to run as a single Python script with a JSON configuration file.

Prerequisites
- Python 3.8+
- Akamai EdgeGrid credentials configured in ~/.edgerc
- Install dependencies: pip install requests akamai-edgegrid

Quick start
1. Fill out requirements.json with your account, property, datacenter, and EdgeWorker details.
2. Run:
   python3 main.py --activation-network staging
3. Use --verbose for more details:
   python3 main.py --activation-network staging --verbose

What it does (high level)
- Creates or reuses GTM domain/datacenters and GTM property
- Creates internal Property Manager config and updates origins/hostnames
- Builds and uploads EdgeWorker bundle and activates it
- Injects Harper Redirect + EarlyHints rule into customer-facing property
- Activates changes for staging or production (or saves only)

Output
- Appends run results to result.json with gtm, propertyManager, edgeworker, and harperRule sections.

Need help?
If you want this README committed to the repo, tell me to push it and I will create the commit for you.
