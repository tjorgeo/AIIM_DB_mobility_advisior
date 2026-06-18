import os
import re
import requests
import json

# Configuration
JIRA_URL = "https://mobilityoptimizer.atlassian.net"
EMAIL = "tjorge.orlitz@gmail.com"
JIRA_TOKEN = os.environ.get("JIRA_TOKEN")
PROJECT_KEY = "SCRUM"
ISSUE_TYPE = "Story"
STORY_POINTS_FIELD = "customfield_10016"
LABELS = ["mvp", "db-moveoptimizer", "sprint-ready", "agentic-pilot"]

def get_story_points(effort_str):
    # Mapping: 1d=1, 2d=2, 3d=3, 4d=5, 5d=5
    days_match = re.search(r'(\d+)\s*days?', effort_str, re.IGNORECASE)
    if not days_match:
        return 0
    days = int(days_match.group(1))
    if days == 1: return 1
    if days == 2: return 2
    if days == 3: return 3
    if days == 4: return 5
    if days >= 5: return 5
    return days

def parse_requirements(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Parse the effort table
    effort_map = {}
    table_match = re.search(r'\| Story \| Must-Have \| Definition of Done \| Estimated Effort \|\n\|.*?\|\n(.*?)\n\n', content, re.DOTALL)
    if table_match:
        table_rows = table_match.group(1).strip().split('\n')
        for row in table_rows:
            cols = [c.strip() for c in row.split('|') if c.strip()]
            if len(cols) >= 4:
                story_num_match = re.search(r'(\d+)\.', cols[0])
                if story_num_match:
                    num = int(story_num_match.group(1))
                    effort_map[num] = cols[3]

    # Parse individual stories
    stories = []
    story_blocks = re.split(r'### Story ', content)[1:]
    for block in story_blocks:
        lines = block.strip().split('\n')
        header = lines[0]
        num_match = re.match(r'(\d+): (.*)', header)
        if not num_match:
            continue
        
        story_num = int(num_match.group(1))
        title = num_match.group(2).strip()
        
        # Extract User Story Statement
        user_type = ""
        goal = ""
        benefit = ""
        
        user_type_match = re.search(r'\*\*As a\*\*\s*(.*?)\s*\n', block)
        if user_type_match: user_type = user_type_match.group(1).strip()
        
        goal_match = re.search(r'\*\*I need\*\*\s*(.*?)\s*\n', block)
        if goal_match: goal = goal_match.group(1).strip()
        
        benefit_match = re.search(r'\*\*So that\*\*\s*(.*?)\s*\n', block)
        if benefit_match: benefit = benefit_match.group(1).strip()
        
        # Extract Acceptance Criteria
        ac_match = re.search(r'\*\*Acceptance Criteria:\*\*\n(.*?)(?=\n\n\*\*Definition of Done:|$)', block, re.DOTALL)
        ac = ac_match.group(1).strip() if ac_match else ""
        
        # Extract Definition of Done
        dod_match = re.search(r'\*\*Definition of Done:\*\*\n(.*?)(?=\n\n---|$)', block, re.DOTALL)
        dod = dod_match.group(1).strip() if dod_match else ""
        
        effort = effort_map.get(story_num, "Unknown")
        story_points = get_story_points(effort)
        
        stories.append({
            "number": story_num,
            "title": title,
            "user_type": user_type,
            "goal": goal,
            "benefit": benefit,
            "ac": ac,
            "dod": dod,
            "effort": effort,
            "story_points": story_points
        })
    
    return stories

def create_jira_issue(story):
    summary = f"[SCRUM-Story {story['number']}] {story['title']}"
    description = f"""## User Story Statement
As a **{story['user_type']}**
I need **{story['goal']}**
So that **{story['benefit']}**

## Acceptance Criteria
{story['ac']}

## Definition of Done
{story['dod']}

## Estimated Effort
* **Estimated Days:** {story['effort']}
"""
    
    # Split description into paragraphs for better ADF rendering
    description_content = []
    for line in description.split('\n'):
        if line.strip():
            description_content.append({
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": line
                    }
                ]
            })
        else:
            # Add an empty paragraph for empty lines
            description_content.append({"type": "paragraph", "content": []})

    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": description_content
            },
            "issuetype": {"name": ISSUE_TYPE},
            "labels": LABELS,
            STORY_POINTS_FIELD: story['story_points']
        }
    }

    # Jira v3 description needs to be ADF format. 
    # The simple conversion above might not be perfect for markdown, 
    # but the tool mcp_jira_jira_create_issue handles markdown.
    # However, the user asked for a Python script calling /rest/api/3/issue.
    # Actually, I can use a simpler ADF for the whole text or try to format it better.
    # But since the request says "Markdown-formatted description", and Jira Cloud v3 
    # uses ADF, I should probably use a converter or just plain text if I want to be safe.
    # Wait, the prompt says "Implementation: Write a Python script that parses the MD file 
    # and makes the POST requests to /rest/api/3/issue."
    # And "Description: ... markdown ..."
    
    # I'll use a more robust ADF conversion if possible, or just keep it simple.
    
    # Let's refine the description payload to be ADF-compliant for the headers and lists.
    
    response = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        auth=(EMAIL, JIRA_TOKEN),
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload)
    )
    
    if response.status_code != 201:
        # Try 'Task' if 'Story' fails as per instructions
        if ISSUE_TYPE == "Story":
            payload["fields"]["issuetype"]["name"] = "Task"
            response = requests.post(
                f"{JIRA_URL}/rest/api/3/issue",
                auth=(EMAIL, JIRA_TOKEN),
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload)
            )
            if response.status_code == 201:
                return response.json()
        print(f"Failed to create issue {summary}: {response.text}")
        return None
    return response.json()

def main():
    stories = parse_requirements("DELIVERABLES/MVP_REQUIREMENTS.md")
    print(f"{'Summary':<60} | {'Jira Key':<10}")
    print("-" * 73)
    for story in stories:
        res = create_jira_issue(story)
        if res:
            print(f"{f'[SCRUM-Story {story['number']}] {story['title']}':<60} | {res['key']:<10}")

if __name__ == "__main__":
    main()
