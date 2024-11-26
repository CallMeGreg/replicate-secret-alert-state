# Overview

This script ([main.py](./main.py)) helps deduplicate GitHub secret scanning alerts that have been created by identical custom patterns at different levels (repository, organization, enterprise) in the same GitHub instance.

> [!NOTE]
> If you are looking to migrate the state of alerts across different GitHub instances, check out [this repository](https://github.com/CallMeGreg/migrate-secret-alert-state).

# How it works

The script takes in either a CSV file with a list of organizations, or a single organization specified as an argument, that you would like to target. For each organization, the script iterates through each repository looking for secret scanning alerts that have a pattern with a specific, customizeable prefix (e.g. `ent-`). For each alert found, the script will:
1. Find the corresponding alert with the same pattern (minus the prefix) and with the same secret value.
2. Check that the corresponding alert is closed.
3. Set the state, resolution reason, and resolution comment of the alert with the prefix to match the state of the corresponding alert.

# Pre-requisites
- Python 3.12+
- Python dependencies (install using `pip install -r requirements.txt`)
- A GitHub Personal Access Token (PAT) for an account with write access to all target secret scanning alerts, with the following scope:
  - `repo` (Full control of private repositories)
- (optional) A CSV file with the list of organizations to target. The CSV file should NOT have a header. Alternatively, you can specify a single organization as a command line argument. See [example.csv](./example.csv) for an example.


# Assumptions

- The script assumes that the alerts are created with a specific pattern prefix (e.g. `ent-`) at the repository, organization, or enterprise level. You can modify the `--prefix` argument to match your own pattern.
- The PAT should have sufficient permissions to read and update secret scanning alerts in the specified organizations.
- The actor closing the prefixed alerts will be the user associated with the PAT (although the comment will contain the actor who closed the original alert).
- GitHub Advanced Security, and secret scanning, are enabled for all target repositories, otherwise those repositories will be skipped.

# Usage

## Setup

Set your GitHub PAT as an environment variable:

```bash
export GITHUB_PAT=ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

## Dry run mode

By default, the script will run in dry-run mode. This will log any alert mapping that were identified without making any changes to the alerts, and list the total number of mapped alerts in addition to the total number of alerts that _would have been updated_. To run the script in dry-run mode, use the following command:

```bash
python main.py --prefix "ent-" --org-name "callmegreg-demo-org"
```

Instead of specifying one organization, you can also provide a CSV file with a list of organizations to target:

```bash
python main.py --prefix "ent-" --org-list /path/to/your/org-list.csv
```

> [!NOTE]
> `--org-name` and `--org-list` are mutually exclusive. Exactly one of the two options must be provided.

For GHES instances, you can specify the API URL using the `--api-url` argument:

```bash
python main.py --prefix "ent-" --org-list /path/to/your/org-list.csv --api-url "https://HOSTNAME/api/v3"
```

## Active mode

When you're ready to close duplicate alerts, you can disable dry-run mode by using the following command:

```bash
python main.py --prefix "ent-" --org-list /path/to/your/org-list.csv --api-url "https://HOSTNAME/api/v3" --dry-run false
```