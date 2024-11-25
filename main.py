import requests
import logging
import time
import os
import math
import argparse

# Set constants
GITHUB_API_URL = 'https://api.github.com'
GENERIC_SLEEP_TIME_SECONDS = 1

def is_secret_scanning_enabled(url, pat):
    # Make a request to the GitHub API to check if GHAS is enabled
    headers = {'Authorization': f'Bearer {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
    # API refernce: https://docs.github.com/en/enterprise-cloud@latest/rest/repos/repos?apiVersion=2022-11-28#get-a-repository
    response = requests.get(url, headers=headers)

    # Ensure the request was successful
    if response.status_code != 200:
        logging.error(f"Failed to fetch repository data: {response.status_code}")
        return False

    # Check the 'secret_scanning' status field in the response
    repo_info = response.json()
    ss_enabled = 'enabled' in repo_info['security_and_analysis']['secret_scanning']['status']
    return ss_enabled

def get_secret_scanning_alerts_from_repo(url, pat, page, alerts):
    while url:
        logging.debug(f"Fetching secret scanning alerts (page {page} from {url})")
        headers = {'Authorization': f'Bearer {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
        params = {'per_page': 100}
        # API reference: https://docs.github.com/en/enterprise-cloud@latest/rest/secret-scanning/secret-scanning?apiVersion=2022-11-28#list-secret-scanning-alerts-for-a-repository
        response = requests.get(url, headers=headers, params=params)

        # Handle rate limits
        if response.status_code == 403 or response.status_code == 429:
            logging.warning(f"Rate limit encountered: {response.status_code}")
            handle_rate_limits(response)

        # Ensure the request was successful
        elif response.status_code != 200:
            logging.error(f"Failed to fetch secret scanning alerts: {response.status_code}")
            return alerts

        # Paginate through the results
        else:
            # Add the alerts to the list
            alerts.extend(response.json())

            # Check if there is a next page
            link_header = response.headers.get('Link')
            if link_header:
                links = link_header.split(', ')
                url = None
                for link in links:
                    if 'rel="next"' in link:
                        url = link[link.index('<')+1:link.index('>')]
                        page += 1
            else:
                url = None

    return alerts

def get_repos_from_org(url, pat, page):
    headers = {'Authorization': f'Bearer {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
    repos = []
    while True:
        response = requests.get(url, headers=headers, params={'page': page, 'per_page': 100})

        if response.status_code == 200:
            repos.extend(response.json())
            if 'next' in response.links:
                page += 1
            else:
                break
        elif response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
            reset_time = int(response.headers['X-RateLimit-Reset'])
            sleep_time = reset_time - time.time() + 1
            logging.warning(f"Rate limit exceeded. Sleeping for {sleep_time} seconds.")
            time.sleep(sleep_time)
        else:
            logging.error(f"Failed to fetch repositories: {response.status_code}")
            break
    return repos

def handle_rate_limits(response):
    # Log x-ratelimit-remaining and sleep if it's low
    rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
    rate_limit_reset = response.headers.get('X-RateLimit-Reset')
    logging.debug(f"Rate limit remaining: {rate_limit_remaining}")
    
    # Check for primary rate limit
    if int(rate_limit_remaining) == 0:
        current_time = math.floor(time.time())
        reset_time = int(rate_limit_reset) - int(current_time) + 5
        if reset_time > 0:
            logging.warning(f"Primary rate limit reached ({rate_limit_remaining} requests remaining). Sleeping for {reset_time} second(s) until rate limit is reset...")
            time.sleep(reset_time)
    
    # Check secondary rate limit
    elif response.headers.get('retry-after'):
        retry_after = int(response.headers.get('retry-after')) + 5
        logging.warning(f"Secondary rate limit reached. Sleeping for {retry_after} second(s) until rate limit is reset...")
        time.sleep(int(retry_after))
    
    # Sleep for generic time
    else:
        logging.warning(f"Unknown rate limit reached. Sleeping for {GENERIC_SLEEP_TIME_SECONDS} second(s)...")
        time.sleep(GENERIC_SLEEP_TIME_SECONDS)

def update_secret_scanning_alert(url, pat, state, resolution, resolution_comment):
    # Update the secret scanning alert with the given state and resolution
    headers = {'Authorization': f'Bearer {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
    data = {'state': state, 'resolution': resolution, 'resolution_comment': resolution_comment}
    # API reference: https://docs.github.com/en/enterprise-cloud@latest/rest/secret-scanning/secret-scanning?apiVersion=2022-11-28#update-a-secret-scanning-alert
    response = requests.patch(url, headers=headers, json=data)
    while True:
        # Handle rate limits
        if response.status_code == 403 or response.status_code == 429:
            logging.warning(f"Rate limit encountered: {response.status_code}")
            handle_rate_limits(response)

        # Ensure the request was successful
        elif response.status_code != 200:
            logging.error(f"Failed to update secret scanning alert: {response.status_code}")
            return False
        
        # Return success
        else:
            logging.debug(f"Successfully updated secret scanning alert: {url}")
            return True

# Convert string input parameters to boolean
def str2bool(value):
        if isinstance(value, bool):
            return value
        if value.lower() in ('true', '1'):
            return True
        elif value.lower() in ('false', '0'):
            return False
        else:
            raise ValueError(f"Invalid boolean value: {value}")
       
def main():
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Fetch environment variables
    github_pat = os.getenv('GITHUB_PAT')
    if not github_pat:
        logging.error("Please set the GITHUB_PAT environment variable")
        exit(1)

    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Replicate secret scanning alert state between identical patterns')
    parser.add_argument('--api-url', type=str, default=GITHUB_API_URL, help='The base URL for your GitHub API (e.g. https://api.your-github-domain.com)')
    parser.add_argument('--prefix', type=str, required=True, help='The prefix used to denote the pattern name for the new alerts')
    parser.add_argument('--dry-run', type=str2bool, default=True, help='Dry run mode')
    org_group = parser.add_mutually_exclusive_group(required=True)
    org_group.add_argument('--org-list', type=str, help='CSV file (with no header) containing the list of organizations to check')
    org_group.add_argument('--org-name', type=str, help='Name of the organization to check')
    args = parser.parse_args()

    # Set counters for summary and dry run mode
    matched_alert_count = 0 # count of alerts that were matched between the two patterns
    matched_closed_alert_count = 0 # count of alerts that were closed in the original pattern and open in the new pattern
    org_list = []

    if args.org_name:
        # --org-name was picked
        org_list = [args.org_name]
    elif args.org_list:
        # --org-list was picked
        with open(args.org_list, 'r') as file:
            org_list = file.readlines()

    # Iterate through the list of organizations
    for org in org_list:
        org = org.strip()
        logging.info(f"Checking organization: {org}")

        # Get the list of repositories in the organization
        repos = get_repos_from_org(f"{args.api_url}/orgs/{org}/repos", github_pat, 1)
        print(len(repos))
        if not repos:
            continue

        # Iterate through the repositories
        for repo in repos:
            logging.info(f"Checking repository: {repo['full_name']}")

            # Check if secret scanning is enabled
            ss_enabled = is_secret_scanning_enabled(f"{args.api_url}/repos/{org}/{repo['name']}", github_pat)
            if not ss_enabled:
                logging.warning(f"Secret scanning not enabled for {repo['full_name']}, skipping...")
                continue

            # Get the secret scanning alerts from the repository
            alerts = get_secret_scanning_alerts_from_repo(f'{args.api_url}/repos/{org}/{repo["name"]}/secret-scanning/alerts', github_pat, 1, [])
            logging.info(f"Found {len(alerts)} secret scanning alerts")

            # Iterate through the alerts
            for alert in alerts:
                # Check if the alert is part of the original pattern
                if alert['secret_type_display_name'].startswith(args.prefix):
                    # Find matching alert with both: pattern without the prefix & same secret value
                    secret_value = alert['secret']
                    pattern_name_without_prefix = alert['secret_type_display_name'][len(args.prefix):]
                    for alert_wo_prefix in alerts:
                        if alert_wo_prefix['secret_type_display_name'] == pattern_name_without_prefix and alert_wo_prefix['secret'] == secret_value and alert_wo_prefix['number'] != alert['number']:
                            matched_alert_count += 1
                            logging.info(f"Matched alert: {alert['number']} matches with {alert_wo_prefix['number']}")
                            # Check if the matched alert is closed
                            if alert_wo_prefix['state'] == 'resolved':
                                matched_closed_alert_count += 1
                                logging.info(f"State of matched alert (alert {alert_wo_prefix['number']}) is resolved.")
                                if not args.dry_run:
                                    logging.info(f"Updating alert {alert['number']} based on alert {alert_wo_prefix['number']}'s resolution...")
                                    new_comment = f"{alert_wo_prefix['resolved_by']['login']} closed alert at {alert_wo_prefix['resolved_at']} with the comment: {alert_wo_prefix['resolution_comment']}"
                                    new_comment = new_comment[:280] # max comment length is 280 characters
                                    update_secret_scanning_alert(alert['url'], github_pat, alert_wo_prefix['state'], alert_wo_prefix['resolution'], new_comment)

    # Print summary
    print(f"\nAlerts matched between the two patterns: {matched_alert_count} ")
    if args.dry_run:
        print(f"Count of alerts that would have been closed: {matched_closed_alert_count}")
    else:
        print(f"Count of alerts that were closed: {matched_closed_alert_count}")

if __name__ == '__main__':
    main()