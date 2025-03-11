import requests
import json

# 🔑 Replace with your actual Notion API key and Page ID
NOTION_API_KEY = "your_secret_key_here"
PAGE_ID = "your_page_id_here"

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def create_notion_database():
    """Creates a Notion Database for job tracking."""
    data = {
        "parent": {"type": "page_id", "page_id": PAGE_ID},
        "title": [{"type": "text", "text": {"content": "Job Tracker"}}],
        "properties": {
            "Job Title": {"title": {}},
            "Company": {"rich_text": {}},
            "Location": {"rich_text": {}},
            "Experience": {"rich_text": {}},
            "Education": {"rich_text": {}},
            "Technical Skills": {"multi_select": {}},
            "Soft Skills": {"multi_select": {}},
            "Job URL": {"url": {}}
        }
    }

    response = requests.post("https://api.notion.com/v1/databases", headers=headers, json=data)
    
    if response.status_code == 200:
        database_id = response.json().get("id")
        print("✅ Database Created Successfully:", database_id)
        return database_id
    else:
        print("❌ Failed to create database:", response.text)
        return None

database_id = create_notion_database()
