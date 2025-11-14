#!/usr/bin/env python3
"""
Script to add a component to a Jira issue.
Uses the jira package from pycontribs/jira for Jira interaction.
"""

import os
import sys
from jira import JIRA


def main():
    # Get environment variables
    jira_base_url = os.environ.get('JIRA_BASE_URL')
    jira_user_email = os.environ.get('JIRA_USER_EMAIL')
    jira_api_token = os.environ.get('JIRA_API_TOKEN')
    issue_key = os.environ.get('ISSUE_KEY')
    component_name = os.environ.get('COMPONENT_NAME')
    jira_project_filter = os.environ.get('JIRA_PROJECT')  # Required project filter

    # Validate required variables
    if not all([jira_base_url, jira_user_email, jira_api_token, issue_key, component_name]):
        print("Error: Missing required environment variables")
        print(f"JIRA_BASE_URL: {'✓' if jira_base_url else '✗'}")
        print(f"JIRA_USER_EMAIL: {'✓' if jira_user_email else '✗'}")
        print(f"JIRA_API_TOKEN: {'✓' if jira_api_token else '✗'}")
        print(f"ISSUE_KEY: {'✓' if issue_key else '✗'}")
        print(f"COMPONENT_NAME: {'✓' if component_name else '✗'}")
        sys.exit(1)

    # Validate JIRA_PROJECT is configured (now required)
    if not jira_project_filter or jira_project_filter.strip() == '':
        print("⊘ Skipping: JIRA_PROJECT variable is not configured or is empty")
        print("Please configure the JIRA_PROJECT repository variable with one or more project keys")
        print("Example: JIRA_PROJECT=CA or JIRA_PROJECT=DEV,QA,PROD")

        # Write skip marker for workflow
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write('status=skipped\n')
            f.write('skip_reason=missing_project_filter\n')

        sys.exit(0)

    # Parse comma-separated project keys
    allowed_projects = [p.strip().upper() for p in jira_project_filter.split(',') if p.strip()]

    if not allowed_projects:
        print("⊘ Skipping: JIRA_PROJECT variable is configured but contains no valid project keys")
        print(f"Current value: '{jira_project_filter}'")

        # Write skip marker for workflow
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write('status=skipped\n')
            f.write('skip_reason=invalid_project_filter\n')

        sys.exit(0)

    # Display project filter configuration
    if len(allowed_projects) == 1:
        print(f"Project filter configured: {allowed_projects[0]}")
        print(f"Only issues from project '{allowed_projects[0]}' will have components added")
    else:
        print(f"Project filter configured: {', '.join(allowed_projects)}")
        print(f"Only issues from projects {allowed_projects} will have components added")

    try:
        # Connect to Jira
        print(f"Connecting to Jira at {jira_base_url}...")
        jira = JIRA(
            server=jira_base_url,
            basic_auth=(jira_user_email, jira_api_token)
        )
        print("Successfully connected to Jira")

        # Get the issue
        print(f"Fetching issue {issue_key}...")
        issue = jira.issue(issue_key)
        project_key = issue.fields.project.key
        print(f"Issue found in project: {project_key}")

        # Check if issue's project is in the allowed projects list
        if project_key.upper() not in allowed_projects:
            print(f"\n⊘ Skipping: Issue {issue_key} is from project '{project_key}'")
            print(f"Allowed projects: {', '.join(allowed_projects)}")
            print(f"Component will NOT be added to this issue")

            # Write skip marker for workflow
            with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
                f.write('status=skipped\n')
                f.write(f'skip_reason=project_not_allowed\n')

            sys.exit(0)  # Exit successfully without adding component
        else:
            print(f"✓ Project filter match: Issue belongs to '{project_key}' (allowed)")

        # Get all components in the project
        print(f"Checking if component '{component_name}' exists in project {project_key}...")
        project_components = jira.project_components(project_key)
        component_names = [comp.name for comp in project_components]

        # Create component if it doesn't exist
        if component_name not in component_names:
            print(f"Component '{component_name}' does not exist. Creating it...")
            new_component = jira.create_component(
                name=component_name,
                project=project_key,
                description=f"Component for {component_name} repository"
            )
            print(f"Component '{component_name}' created successfully (ID: {new_component.id})")
        else:
            print(f"Component '{component_name}' already exists in project")

        # Get existing components on the issue
        existing_components = [comp.name for comp in issue.fields.components]
        print(f"Existing components on issue: {existing_components}")

        # Add component to issue if not already present
        if component_name in existing_components:
            print(f"Component '{component_name}' is already added to issue {issue_key}")
        else:
            # Get the component object
            component_obj = None
            for comp in project_components:
                if comp.name == component_name:
                    component_obj = comp
                    break

            # If we just created the component, fetch it again
            if component_obj is None:
                project_components = jira.project_components(project_key)
                for comp in project_components:
                    if comp.name == component_name:
                        component_obj = comp
                        break

            # Update the issue with the new component
            all_components = existing_components + [component_name]
            component_dicts = [{'name': name} for name in all_components]

            print(f"Adding component '{component_name}' to issue {issue_key}...")
            issue.update(fields={'components': component_dicts})
            print(f"Successfully added component '{component_name}' to issue {issue_key}")

        print("\n✓ Component operation completed successfully")

        # Write success marker for workflow
        with open(os.environ.get('GITHUB_OUTPUT', '/dev/null'), 'a') as f:
            f.write('status=processed\n')

    except Exception as e:
        print(f"\n✗ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()