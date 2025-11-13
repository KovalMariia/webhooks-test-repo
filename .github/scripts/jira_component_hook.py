import json
import os
import re
import sys
import subprocess
from base64 import b64encode

import requests

JIRA_BASE_URL = os.environ["JIRA_BASE_URL"].rstrip("/")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
REPO_NAME = os.environ["REPO_NAME"]
GITHUB_EVENT_NAME = os.environ["GITHUB_EVENT_NAME"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
PR_NUMBER = os.environ.get("PR_NUMBER")
OWNER = os.environ.get("OWNER")
REPO = os.environ.get("REPO")

# Classic Jira issue key regex like ABC-123
ISSUE_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

def gh_api(url):
    """Call GitHub REST API if token present."""
    if not GITHUB_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
               "Accept": "application/vnd.github+json"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    return None

def extract_issue_keys():
    texts = []

    # Read the GitHub Actions event payload
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    payload = {}
    if event_path and os.path.exists(event_path):
        with open(event_path, "r") as f:
            payload = json.load(f)

    if GITHUB_EVENT_NAME == "push":
        # Commit messages are in payload.commits[*].message; branch name in ref
        for c in payload.get("commits", []):
            if "message" in c:
                texts.append(c["message"])
        ref = payload.get("ref") or ""
        texts.append(ref)  # sometimes branch names contain the key

        # Fallback: read last commit message from git
        try:
            msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"]).decode("utf-8", "ignore")
            texts.append(msg)
        except Exception:
            pass

    elif GITHUB_EVENT_NAME == "pull_request":
        pr = payload.get("pull_request", {})
        # PR title/body often include the key; branch name can too
        texts.append(pr.get("title", ""))
        texts.append(pr.get("body", ""))
        head = pr.get("head", {})
        texts.append(head.get("ref", ""))

        # Optionally fetch all PR commit messages via GitHub API
        if PR_NUMBER and OWNER and REPO and GITHUB_TOKEN:
            commits = gh_api(f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/commits")
            if isinstance(commits, list):
                for c in commits:
                    msg = c.get("commit", {}).get("message")
                    if msg:
                        texts.append(msg)

    # Extract keys
    keys = set()
    for t in texts:
        if not t:
            continue
        for m in ISSUE_KEY_RE.findall(t):
            keys.add(m)

    return sorted(keys)

def jira_headers():
    token = b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def jira_get_issue_project(issue_key):
    """Return (projectKey, projectId) for the issue."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}?fields=project"
    r = requests.get(url, headers=jira_headers())
    r.raise_for_status()
    project = r.json()["fields"]["project"]
    return project["key"], project["id"]

def jira_list_components(project_key):
    """List components in a project and return dict{name: {id,...}}."""
    url = f"{JIRA_BASE_URL}/rest/api/3/project/{project_key}/components"
    r = requests.get(url, headers=jira_headers())
    r.raise_for_status()
    out = {}
    for comp in r.json():
        out[comp["name"]] = comp
    return out

def jira_create_component(project_key, name):
    """Create a component (returns component dict)."""
    url = f"{JIRA_BASE_URL}/rest/api/3/component"
    body = {"name": name, "project": project_key}
    if JIRA_COMPONENT_LEAD:
        body["leadAccountId"] = JIRA_COMPONENT_LEAD
    r = requests.post(url, headers=jira_headers(), data=json.dumps(body))
    # 409 if already exists (rare race); treat as ok
    if r.status_code == 409:
        comps = jira_list_components(project_key)
        return comps.get(name)
    r.raise_for_status()
    return r.json()

def jira_add_component_to_issue(issue_key, component_id):
    """Add (not replace) a component to the issue."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    body = {
        "update": {
            "components": [
                {"add": {"id": str(component_id)}}
            ]
        }
    }
    r = requests.put(url, headers=jira_headers(), data=json.dumps(body))
    # 204 is success; 400 if field not on screen/context
    if r.status_code not in (200, 204):
        r.raise_for_status()

def main():
    issue_keys = extract_issue_keys()
    if not issue_keys:
        print("No Jira issue keys found. Nothing to do.")
        return

    # For each issue, ensure component exists in that issue's project, then add it
    for key in issue_keys:
        try:
            project_key, _ = jira_get_issue_project(key)
            comps = jira_list_components(project_key)
            if REPO_NAME in comps:
                comp = comps[REPO_NAME]
            else:
                comp = jira_create_component(project_key, REPO_NAME)

            jira_add_component_to_issue(key, comp["id"])
            print(f"[OK] {key} + component '{REPO_NAME}'")
        except requests.HTTPError as e:
            # Fail softly per-issue; keep going
            print(f"[WARN] {key}: {e} - response: {getattr(e, 'response', None) and e.response.text}")
        except Exception as e:
            print(f"[WARN] {key}: {e}")

if __name__ == "__main__":
    main()
