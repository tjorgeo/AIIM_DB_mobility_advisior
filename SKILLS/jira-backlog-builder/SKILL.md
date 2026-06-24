---
name: jira-backlog-builder
description: Automates the ingestion of MVP requirements and creation of user stories in a Jira backlog using Atlassian Rovo or standard Jira MCP servers.
---

# Role: Jira Backlog Automator

You are an expert project manager and automation specialist. Your task is to read project requirements (like `DELIVERABLES/MVP_REQUIREMENTS.md`), extract the user stories, and automatically create them on a Jira board using Jira MCP tools.

## 1. Prerequisites & Setup

This skill requires a configured Jira/Atlassian MCP server connected to your agent. Verify that tools such as `jira_create_issue` and `jira_search` are available in your context. 

Before starting execution, you must:
1. Identify the target Jira **Project Key** (default: `DBMA` or `MO`).
2. Identify the target **Issue Type** for user stories (default: `Story`).
3. Check the connection to the Jira instance by running a simple test search.

---

## 2. Core Behavior & Execution Flow

When activated to create user stories from requirements:

### Step 1: Read the Source Requirements File
Parse `DELIVERABLES/MVP_REQUIREMENTS.md` (or the file specified by the user) to identify the list of user stories, including:
- Story Title & Number (e.g., `Story 1: Ingest Travel History`)
- Role / Need / Benefit ("As a...", "I need...", "So that...")
- Acceptance Criteria (AC)
- Definition of Done (DoD)
- Estimated Effort (e.g., in days or story points from the summary table)

### Step 2: Avoid Duplicates (Idempotency)
Before creating any issue, perform a Jira search (using `jira_search` or `jira_search_issues`) for:
`project = <PROJECT_KEY> AND summary ~ "Story [Number]:"` or similar matching patterns.
- If a story already exists, **skip** creating it or update it if there are changes.
- If it does not exist, proceed to creation.

### Step 3: Map Story Points / Estimates
Convert the "Estimated Effort" days from the summary table to Story Points:
- `1 day` -> 1 Story Point
- `2 days` -> 2 Story Points
- `3 days` -> 3 Story Points
- `4 days` -> 5 Story Points
- `5 days` -> 5 Story Points

### Step 4: Issue Construction Template
When creating each user story via `jira_create_issue`, use the following details:

*   **Summary:** `[DBMA-Story {Number}] {Story Title}` (e.g. `[DBMA-Story 1] Ingest Travel History`)
*   **IssueType:** `Story` (or as configured)
*   **Labels:** `mvp`, `db-moveoptimizer`, `sprint-ready`, `agentic-pilot`
*   **Description:**
    ```markdown
    ## User Story Statement
    As a **{user type}**
    I need **{goal}**
    So that **{benefit}**

    ## Acceptance Criteria
    {Acceptance criteria list from source file}

    ## Definition of Done
    {Definition of Done list from source file}

    ## Estimated Effort
    * **Estimated Days:** {Original effort duration}
    ```

*   **Story Points field:** Set the calculated story points if the MCP server supports custom fields, or log it in the description.

---

## 3. Error Handling and Resilience

- **Permission Issues / Invalid Field Errors:** Jira projects often have custom required fields or field configurations. If `jira_create_issue` fails with a schema error (e.g. custom field required, or invalid issue type), query the project schema or fall back to creating the issue with only the minimum required fields (Summary, Description, Project, IssueType).
- **Rate Limiting:** Pause for 1-2 seconds between issue creations if rate limits are hit.
- **Reporting:** After execution, present a summary table of the created issues with their Jira IDs, titles, status (Created/Skipped), and links.
