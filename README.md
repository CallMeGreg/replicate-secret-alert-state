# Overview

This script ([main.py](./main.py)) helps deduplicate GitHub secret scanning alerts that have been created by custom patterns at different levels (repository, organization, enterprise) in the same GitHub instance.

> [!NOTE]
> If you are looking to migrate the state of alerts across different GitHub instances, check out [this repo](https://github.com/CallMeGreg/migrate-secret-alert-state).

# How it works

The script takes in either a CSV file with a list of organizations, or a single organization specified as an argument, that you would like to target. For each organization, the script iterates through each repo looking for secret scanning alerts that have a pattern with a specific, customizeable prefix (e.g. `ent-`). For each alert found, the script will:
1. Find the corresponding alert with the same pattern (minus the prefix) and with the same secret value.
2. Check that the corresponding alert is closed.
3. Set the state, resolution reason, and resolution comment of the alert with the prefix to match the state of the corresponding alert.

# Pre-requisites
- Python 3
- Python `requests` library (install using `pip install requests`)
- A GitHub Personal Access Token (PAT) for an account with access to all secret scanning alerts, with the following scope:
  - `repo` (Full control of private repositories)
- (optional) A CSV file with the list of organizations to target. The CSV file should NOT have a header. Alternatively, you can specify a single organization as a command line argument. See [example.csv](./example.csv) for an example.


# Assumptions

- The script assumes that the alerts are created with a specific pattern (e.g. `ent-`) at the repo, org, or enterprise level. You can modify the `--prefix` argument to match your own pattern.
- The PAT used should have sufficient permissions to read and update secret scanning alerts in the specified organizations.
- The actor closing the prefixed alerts will be the user associated with the PAT (although the comment will contain the actor who closed the original alert).
- GitHub Advanced Security, and secret scanning, are enabled for all target repositories, otherwise those repositories will be skipped.

# Usage

Set your GitHub PAT as an environment variable:

```bash
export GITHUB_PAT=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Run `main.py` with the following arguments:

```bash
python3 main.py --prefix="ent-" 
```