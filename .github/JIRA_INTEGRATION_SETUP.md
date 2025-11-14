# Jira Integration Setup Guide

This guide explains how to configure the GitHub-Jira integration workflow.

## Overview

This workflow automatically:
- Extracts Jira issue keys from PR titles
- Filters issues by configured project(s) (required)
- Creates and adds components to Jira issues
- Uses the **repository name** as the component name
- Supports multiple projects with comma-separated values

The integration is written in Python and uses the official [pycontribs/jira](https://github.com/pycontribs/jira) library.

## Required GitHub Secrets

You need to add the following secrets to your GitHub repository:

### 1. `JIRA_USER_EMAIL`
The email address of the Jira user account that will perform the API operations.

**Example:** `your-email@company.com`

### 2. `JIRA_API_TOKEN`
A Jira API token for authentication.

**How to create:**
1. Log in to Jira
2. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
3. Click "Create API token"
4. Give it a name (e.g., "GitHub Actions")
5. Copy the token value

## Required Repository Variables

### `JIRA_BASE_URL`
Your Jira instance base URL (without trailing slash).

**Type:** Repository Variable

**Example:** `https://your-company.atlassian.net`

### `JIRA_PROJECT`
Project key(s) to filter which issues get components added. **This variable is required.**

**Type:** Repository Variable (not a secret)

**Format:** Single project key or comma-separated list of project keys

**Examples:**
- Single project: `DEV`
- Multiple projects: `DEV,AQA,OPS`
- Multiple projects with spaces: `DEV, AQA, OPS` (spaces are trimmed automatically)

**How it works:**
- Only issues from the specified project(s) will have components added
- Issues from other projects will be skipped (workflow succeeds but no component is added)
- If not configured or empty, the workflow will skip with a message
- Project keys are case-insensitive (both `dev` and `DEV` work)

**Example scenarios:**

✅ **With `JIRA_PROJECT=DEV`:**
- PR title: `DEV-123 Add feature` → Component added
- PR title: `OPS-456 Fix bug` → Skipped (different project)

✅ **With `JIRA_PROJECT=DEV,AQA,OPS`:**
- PR title: `DEV-123 Add feature` → Component added
- PR title: `AQA-456 Fix bug` → Component added
- PR title: `OPS-789 Update config` → Component added
- PR title: `SA-321 Other task` → Skipped (not in allowed list)

❌ **Without `JIRA_PROJECT` (not configured):**
- All PRs → Skipped with message to configure the variable

## How to Configure GitHub Secrets and Variables

### Adding Secrets (for sensitive data)

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click the **Secrets** tab (should be selected by default)
4. Click **New repository secret**
5. Add each secret with its name and value:
   - `JIRA_USER_EMAIL`
   - `JIRA_API_TOKEN`

### Adding Variables (for non-sensitive configuration)

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click the **Variables** tab
4. Click **New repository variable**
5. Add the following variables (both required):
   - **Name:** `JIRA_BASE_URL` | **Value:** `https://your-company.atlassian.net`
   - **Name:** `JIRA_PROJECT` | **Value:** `DEV` (single project) or `DEV,AQA,OPS` (multiple projects)

**Why use Variables instead of Secrets?**
- Variables are designed for non-sensitive configuration data
- They're visible in workflow logs (useful for debugging)
- Secrets are encrypted and hidden in logs (necessary for credentials only)
- Base URLs and project keys are not sensitive information

**IMPORTANT:** The `JIRA_PROJECT` variable is required. If it's not configured or empty, the workflow will skip all PRs with a message asking you to configure it.

## Workflow Behavior

The workflow triggers when a pull request is **created** (not updated or reopened).

### What it does:

1. **Extracts Jira issue key** from the PR title (format: `DEV-123 Description`)
2. **Validates JIRA_PROJECT variable** (required)
   - If not configured or empty → skip with message
3. **Logs into Jira** using the provided credentials
4. **Checks if issue's project is allowed**
   - If issue's project is in the allowed list (`JIRA_PROJECT`) → continue
   - If issue's project is NOT in the allowed list → skip (exit gracefully)
5. **Creates the component** in the Jira project if it doesn't exist
6. **Adds the component** to the Jira issue

### PR Title Format

Your pull request title **must** start with the Jira issue key:

✅ **Valid:**
- `DEV-123 Add user authentication`
- `PROJ-456 Fix navigation bug`

❌ **Invalid:**
- `Add user authentication DEV-123`
- `Fix bug` (no issue key)

### Component Name

The workflow automatically uses the **repository name** as the component name in Jira.

For example, if your repository is named `gtm-app`, the workflow will:
- Create a component named `gtm-app` in the Jira project (if it doesn't exist)
- Add this component to the issue

### Example Workflow Run

```
Repository: gtm-app
PR Title: DEV-123 Implement user login feature
↓
Extracted Issue Key: DEV-123
↓
Component "gtm-app" created (if needed)
↓
Component "gtm-app" added to DEV-123 ✓
```

## Customization

### Change when the workflow runs

Edit `.github/workflows/jira-integration.yml`:

```yaml
on:
  pull_request:
    types: [opened, reopened, synchronize]  # Add more trigger types
```

### Use different component names

By default, the workflow uses `${{ github.event.repository.name }}` as the component name.

To use a different component name, edit `.github/workflows/jira-integration.yml` and change:

```yaml
COMPONENT_NAME: ${{ github.event.repository.name }}
```

To one of:
```yaml
COMPONENT_NAME: "Custom Name"  # Hardcoded name
COMPONENT_NAME: ${{ secrets.JIRA_COMPONENT_NAME }}  # From secrets
COMPONENT_NAME: ${{ github.event.pull_request.head.ref }}  # From branch name
```

### Add transition/status changes

Use the `atlassian/gajira-transition` action to move the issue to a different status:

```yaml
- name: Transition Issue
  uses: atlassian/gajira-transition@v3
  with:
    issue: ${{ steps.extract-issue.outputs.issue-key }}
    transition: "In Progress"
```

## Technical Implementation

### Python Script

The component creation and addition logic is implemented in `.github/scripts/add_jira_component.py`.

The script uses the [pycontribs/jira](https://github.com/pycontribs/jira) library to:
1. Validate that `JIRA_PROJECT` is configured (required)
2. Parse comma-separated project keys from `JIRA_PROJECT`
3. Connect to Jira using basic authentication
4. Fetch the issue and determine its project
5. Check if issue's project is in the allowed projects list
6. Check if the component exists in the project
7. Create the component if it doesn't exist
8. Add the component to the issue (preserving existing components)

**Key features:**
- **Required project filtering** via `JIRA_PROJECT` environment variable
- **Multi-project support** with comma-separated values (e.g., `DEV,AQA,OPS`)
- Case-insensitive project matching
- Handles component deduplication automatically
- Provides detailed logging for debugging
- Gracefully handles errors with descriptive messages
- Outputs workflow status (`processed` or `skipped`) and skip reasons for conditional steps

### Workflow Actions

The workflow uses these GitHub Actions:
- `actions/checkout@v4` - Checks out the repository code
- `actions/setup-python@v5` - Sets up Python 3.11
- `atlassian/gajira-login@v3` - Authenticates with Jira

## Troubleshooting

### "No Jira issue key found in PR title"
- Ensure your PR title starts with the issue key (e.g., `DEV-123`)
- The pattern matches: `[A-Z]+-[0-9]+`

### "Failed to create component"
- Check that the user has permission to create components in the project
- Verify the component name doesn't contain special characters
- Ensure the repository name is a valid Jira component name

### "Failed to update issue"
- Verify the issue exists and is accessible by the user
- Check that the user has edit permissions on the issue
- Ensure the API token is valid and not expired

### Python script errors
- Check the workflow logs for detailed error messages
- Verify all required environment variables are set
- Ensure the `jira` package is installed correctly (should happen automatically)

### Component not added (workflow shows "Skipped")

The workflow can skip for several reasons. Check the workflow summary in the Actions tab to see the specific skip reason:

**1. JIRA_PROJECT variable not configured**
- The `JIRA_PROJECT` variable is required but not set
- **Solution:** Configure the `JIRA_PROJECT` variable in Settings → Secrets and variables → Actions → Variables
- **Example:** Set `JIRA_PROJECT=DEV` or `JIRA_PROJECT=DEV,AQA`

**2. Issue's project not in allowed list**
- Example: `JIRA_PROJECT=DEV` but PR title is `OPS-123 Fix bug`
- The workflow completes successfully but doesn't add the component
- **Solutions:**
  - Add the project to `JIRA_PROJECT`: Change `DEV` to `DEV,OPS`
  - Update the `JIRA_PROJECT` variable to include your issue's project
  - Use the correct project key in your PR title

**3. JIRA_PROJECT contains no valid project keys**
- The variable is set but empty or contains only whitespace
- **Solution:** Set a valid project key like `DEV` or `DEV,AQA`

## Security Notes

- Never commit API tokens or credentials to the repository
- Use GitHub secrets to store sensitive information
- Consider using a dedicated Jira service account for automation
- Regularly rotate API tokens