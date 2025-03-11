from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from collections import Counter
import re
import time
import json
import logging
from typing import Dict, List, Tuple, Optional
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
import platform
import sys
from datetime import datetime
import requests
import pyperclip
import webbrowser
import streamlit as st
import pandas as pd
from PIL import Image
import base64
from io import BytesIO

# LangChain components
from langchain_google_genai import GoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import StructuredOutputParser, ResponseSchema

# Detect environment
IS_STREAMLIT_CLOUD = os.environ.get('STREAMLIT_SHARING_MODE') == 'streamlit_sharing'
IS_WINDOWS = platform.system() == 'Windows'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set environment-specific configurations
if IS_STREAMLIT_CLOUD:
    logger.info("Running in Streamlit Cloud environment")
    # Ensure proper paths for Chrome in cloud environment
    os.environ['PYTHONPATH'] = '/app'
    if 'CHROMEDRIVER_PATH' not in os.environ:
        os.environ['CHROMEDRIVER_PATH'] = '/usr/local/bin/chromedriver'

class NotionClient:
    def __init__(self, token, database_id=None, page_id=None):
        self.token = token
        self.database_id = database_id
        self.page_id = page_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # If database_id is not provided but page_id is, create a database
        if not database_id and page_id:
            self.database_id = self.create_job_database(page_id)
            logger.info(f"Created new job tracking database with ID: {self.database_id}")
    
    def create_job_database(self, parent_page_id):
        """Create a new job tracking database in the specified page"""
        url = "https://api.notion.com/v1/databases"
        
        # Database schema for job tracking with enhanced referral tracking
        data = {
            "parent": {
                "type": "page_id",
                "page_id": parent_page_id
            },
            "title": [
                {
                    "type": "text",
                    "text": {
                        "content": "Job Application Tracker"
                    }
                }
            ],
            "properties": {
                "Job Title": {
                    "title": {}
                },
                "Company": {
                    "rich_text": {}
                },
                "Location": {
                    "rich_text": {}
                },
                "Job URL": {
                    "url": {}
                },
                "Job ID": {
                    "rich_text": {}
                },
                "Date Applied": {
                    "date": {}
                },
                "Status": {
                    "select": {
                        "options": [
                            {"name": "Not Applied", "color": "gray"},
                            {"name": "Applied", "color": "blue"},
                            {"name": "Interview Scheduled", "color": "yellow"},
                            {"name": "Interview Completed", "color": "orange"},
                            {"name": "Offer Received", "color": "green"},
                            {"name": "Rejected", "color": "red"},
                            {"name": "Not Interested", "color": "purple"}
                        ]
                    }
                },
                "Technical Skills": {
                    "multi_select": {
                        "options": []
                    }
                },
                "Soft Skills": {
                    "multi_select": {
                        "options": []
                    }
                },
                "Experience Required": {
                    "rich_text": {}
                },
                "Education": {
                    "rich_text": {}
                },
                "Salary": {
                    "rich_text": {}
                },
                "Job Type": {
                    "select": {
                        "options": [
                            {"name": "Full-time", "color": "blue"},
                            {"name": "Part-time", "color": "green"},
                            {"name": "Contract", "color": "orange"},
                            {"name": "Internship", "color": "purple"},
                            {"name": "Freelance", "color": "yellow"}
                        ]
                    }
                },
                "Industry": {
                    "rich_text": {}
                },
                "Referral Status": {
                    "select": {
                        "options": [
                            {"name": "Not Started", "color": "gray"},
                            {"name": "Searching Connections", "color": "blue"},
                            {"name": "Requests Sent", "color": "yellow"},
                            {"name": "Referral Received", "color": "green"},
                            {"name": "No Connections Found", "color": "red"}
                        ]
                    }
                },
                "Referral Connections": {
                    "rich_text": {}
                },
                "Connection Messages Sent": {
                    "number": {}
                },
                "Responses Received": {
                    "number": {}
                },
                "Connection Message Template": {
                    "rich_text": {}
                },
                "InMail Message Template": {
                    "rich_text": {}
                },
                "Notes": {
                    "rich_text": {}
                }
            }
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 200:
            logger.error(f"Error creating Notion database: {response.text}")
            raise Exception(f"Failed to create Notion database: {response.status_code}")
        
        return response.json()["id"]
    
    def get_job_entries(self):
        """Get all job entries from the database"""
        if not self.database_id:
            raise ValueError("No database ID available")
            
        url = f"https://api.notion.com/v1/databases/{self.database_id}/query"
        response = requests.post(url, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Error querying Notion database: {response.text}")
            raise Exception(f"Failed to query Notion database: {response.status_code}")
        
        return response.json()["results"]
    
    def get_job_entry(self, page_id):
        """Get a specific job entry from the database"""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Error getting Notion page: {response.text}")
            raise Exception(f"Failed to get Notion page: {response.status_code}")
        
        return response.json()
    
    def update_job_entry(self, page_id, properties):
        """Update a job entry in the database"""
        url = f"https://api.notion.com/v1/pages/{page_id}"
        
        data = {
            "properties": properties
        }
        
        response = requests.patch(url, headers=self.headers, json=data)
        
        if response.status_code != 200:
            logger.error(f"Error updating Notion page: {response.text}")
            raise Exception(f"Failed to update Notion page: {response.status_code}")
        
        return response.json()
        
    def add_job_to_database(self, job_data):
        """Add a job entry to the Notion database with improved error handling"""
        if not self.database_id:
            raise ValueError("No database ID available. Please create a database first.")
        
        url = "https://api.notion.com/v1/pages"
        
        # Validate database schema first
        is_valid, message = self.validate_database_schema()
        if not is_valid:
            # Try to update schema
            success, update_msg = self.update_database_schema()
            if not success:
                raise ValueError(f"Database schema is invalid and could not be updated: {update_msg}")
        
        # Format the data according to Notion API requirements
        properties = {}
        
        # Get database schema to check available properties
        schema_url = f"https://api.notion.com/v1/databases/{self.database_id}"
        schema_response = requests.get(schema_url, headers=self.headers)
        
        if schema_response.status_code != 200:
            raise ValueError(f"Failed to get database schema: {schema_response.status_code}")
        
        available_properties = schema_response.json().get("properties", {}).keys()
        
        # Add properties only if they exist in the database
        if "Job Title" in available_properties:
            properties["Job Title"] = {
                "title": [
                    {
                        "text": {
                            "content": job_data.get("job_title", "Untitled Job")
                        }
                    }
                ]
            }
        
        if "Company" in available_properties:
            properties["Company"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data.get("company", "Unknown")
                        }
                    }
                ]
            }
        
        if "Location" in available_properties:
            properties["Location"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data.get("location", "Remote/Unknown")
                        }
                    }
                ]
            }
        
        if "Job URL" in available_properties:
            properties["Job URL"] = {
                "url": job_data.get("job_url", "")
            }
        
        if "Date Applied" in available_properties:
            properties["Date Applied"] = {
                "date": {
                    "start": datetime.now().strftime("%Y-%m-%d")
                }
            }
        
        if "Status" in available_properties:
            properties["Status"] = {
                "select": {
                    "name": "Not Applied"
                }
            }
        
        if "Job Type" in available_properties:
            properties["Job Type"] = {
                "select": {
                    "name": job_data.get("job_type", "Full-time") if job_data.get("job_type") != "Not specified" else "Full-time"
                }
            }
        
        if "Industry" in available_properties:
            properties["Industry"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data.get("industry", "Not specified")
                        }
                    }
                ]
            }
        
        if "Referral Status" in available_properties:
            properties["Referral Status"] = {
                "select": {
                    "name": "Not Started"
                }
            }
        
        if "Connection Messages Sent" in available_properties:
            properties["Connection Messages Sent"] = {
                "number": 0
            }
        
        if "Responses Received" in available_properties:
            properties["Responses Received"] = {
                "number": 0
            }
        
        # Add job ID if available
        job_id = job_data.get("job_id", "")
        if job_id and "Job ID" in available_properties:
            properties["Job ID"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_id
                        }
                    }
                ]
            }
        
        # Add technical skills if available
        if job_data.get("technical_skills") and "Technical Skills" in available_properties:
            # Limit to 10 skills to avoid Notion API limits
            skills = job_data["technical_skills"][:10]
            properties["Technical Skills"] = {
                "multi_select": [{"name": skill} for skill in skills]
            }
            
        # Add soft skills if available
        if job_data.get("soft_skills") and "Soft Skills" in available_properties:
            # Limit to 10 skills to avoid Notion API limits
            skills = job_data["soft_skills"][:10]
            properties["Soft Skills"] = {
                "multi_select": [{"name": skill} for skill in skills]
            }
            
        # Add experience required if available
        if job_data.get("required_experience") and "Experience Required" in available_properties:
            properties["Experience Required"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data["required_experience"]
                        }
                    }
                ]
            }
        
        # Add education if available
        if job_data.get("education_requirements") and "Education" in available_properties:
            properties["Education"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": ", ".join(job_data["education_requirements"][:5])
                        }
                    }
                ]
            }
        
        # Add salary if available
        if job_data.get("salary") and "Salary" in available_properties:
            properties["Salary"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data["salary"]
                        }
                    }
                ]
            }
        
        # Add message templates if available
        if job_data.get("connection_message_template") and "Connection Message Template" in available_properties:
            properties["Connection Message Template"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data["connection_message_template"]
                        }
                    }
                ]
            }
        
        if job_data.get("inmail_message_template") and "InMail Message Template" in available_properties:
            properties["InMail Message Template"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data["inmail_message_template"]
                        }
                    }
                ]
            }
        
        data = {
            "parent": {"database_id": self.database_id},
            "properties": properties
        }
        
        # Add job description as page content if available
        if job_data.get("job_description"):
            description = job_data["job_description"]
            max_length = 2000  # Notion API has limits on text block size
            
            children = [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "Job Description"}}]
                    }
                }
            ]
            
            # Split description into chunks if needed
            for i in range(0, len(description), max_length):
                chunk = description[i:i+max_length]
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}]
                    }
                })
            
            data["children"] = children
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 200:
            logger.error(f"Error adding job to Notion: {response.text}")
            raise Exception(f"Failed to add job to Notion: {response.status_code}")
        
        return response.json()

    def validate_database_schema(self):
        """Validate if the database has all required properties"""
        if not self.database_id:
            return False, "No database ID available"
        
        try:
            # Get database schema
            url = f"https://api.notion.com/v1/databases/{self.database_id}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                return False, f"Failed to get database schema: {response.status_code}"
            
            database = response.json()
            properties = database.get("properties", {})
            
            # Required properties for our application
            required_properties = [
                "Job Title", "Company", "Location", "Job URL", "Job ID", 
                "Date Applied", "Status", "Technical Skills", "Soft Skills",
                "Experience Required", "Education", "Salary", "Job Type",
                "Industry", "Referral Status", "Referral Connections",
                "Connection Messages Sent", "Responses Received",
                "Connection Message Template", "InMail Message Template", "Notes"
            ]
            
            missing_properties = []
            for prop in required_properties:
                if prop not in properties:
                    missing_properties.append(prop)
            
            if missing_properties:
                return False, f"Missing properties: {', '.join(missing_properties)}"
            
            return True, "Database schema is valid"
            
        except Exception as e:
            return False, f"Error validating database schema: {str(e)}"

    def update_database_schema(self):
        """Update an existing database with missing properties"""
        if not self.database_id:
            return False, "No database ID available"
        
        try:
            # Get current schema
            url = f"https://api.notion.com/v1/databases/{self.database_id}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                return False, f"Failed to get database schema: {response.status_code}"
            
            database = response.json()
            current_properties = database.get("properties", {})
            
            # Define properties to add
            new_properties = {}
            
            # Check and add missing properties
            if "Job ID" not in current_properties:
                new_properties["Job ID"] = {"rich_text": {}}
            
            if "Date Applied" not in current_properties:
                new_properties["Date Applied"] = {"date": {}}
            
            if "Status" not in current_properties:
                new_properties["Status"] = {
                    "select": {
                        "options": [
                            {"name": "Not Applied", "color": "gray"},
                            {"name": "Applied", "color": "blue"},
                            {"name": "Interview Scheduled", "color": "yellow"},
                            {"name": "Interview Completed", "color": "orange"},
                            {"name": "Offer Received", "color": "green"},
                            {"name": "Rejected", "color": "red"},
                            {"name": "Not Interested", "color": "purple"}
                        ]
                    }
                }
            
            if "Technical Skills" not in current_properties:
                new_properties["Technical Skills"] = {"multi_select": {"options": []}}
            
            if "Soft Skills" not in current_properties:
                new_properties["Soft Skills"] = {"multi_select": {"options": []}}
            
            if "Experience Required" not in current_properties:
                new_properties["Experience Required"] = {"rich_text": {}}
            
            if "Education" not in current_properties:
                new_properties["Education"] = {"rich_text": {}}
            
            if "Salary" not in current_properties:
                new_properties["Salary"] = {"rich_text": {}}
            
            if "Job Type" not in current_properties:
                new_properties["Job Type"] = {
                    "select": {
                        "options": [
                            {"name": "Full-time", "color": "blue"},
                            {"name": "Part-time", "color": "green"},
                            {"name": "Contract", "color": "orange"},
                            {"name": "Internship", "color": "purple"},
                            {"name": "Freelance", "color": "yellow"}
                        ]
                    }
                }
            
            if "Industry" not in current_properties:
                new_properties["Industry"] = {"rich_text": {}}
            
            if "Referral Status" not in current_properties:
                new_properties["Referral Status"] = {
                    "select": {
                        "options": [
                            {"name": "Not Started", "color": "gray"},
                            {"name": "Searching Connections", "color": "blue"},
                            {"name": "Requests Sent", "color": "yellow"},
                            {"name": "Referral Received", "color": "green"},
                            {"name": "No Connections Found", "color": "red"}
                        ]
                    }
                }
            
            if "Referral Connections" not in current_properties:
                new_properties["Referral Connections"] = {"rich_text": {}}
            
            if "Connection Messages Sent" not in current_properties:
                new_properties["Connection Messages Sent"] = {"number": {}}
            
            if "Responses Received" not in current_properties:
                new_properties["Responses Received"] = {"number": {}}
            
            if "Connection Message Template" not in current_properties:
                new_properties["Connection Message Template"] = {"rich_text": {}}
            
            if "InMail Message Template" not in current_properties:
                new_properties["InMail Message Template"] = {"rich_text": {}}
            
            if "Notes" not in current_properties:
                new_properties["Notes"] = {"rich_text": {}}
            
            # If no properties to add, return success
            if not new_properties:
                return True, "Database schema is already up to date"
            
            # Update database
            update_url = f"https://api.notion.com/v1/databases/{self.database_id}"
            update_data = {
                "properties": new_properties
            }
            
            update_response = requests.patch(update_url, headers=self.headers, json=update_data)
            
            if update_response.status_code != 200:
                return False, f"Failed to update database schema: {update_response.text}"
            
            return True, f"Added {len(new_properties)} missing properties to database"
            
        except Exception as e:
            return False, f"Error updating database schema: {str(e)}"

class LinkedInHelper:
    def __init__(self, gemini_api_key: str):
        self.setup_llm(gemini_api_key)
    
    def setup_llm(self, api_key: str):
        self.llm = GoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=api_key,
            temperature=0.2,
            max_output_tokens=2000
        )
    
    def generate_connection_message(self, job_data: Dict) -> str:
        """Generate a personalized connection message for LinkedIn with [NAME] placeholder"""
        try:
            prompt = PromptTemplate(
                template="""Create a personalized LinkedIn connection message to ask for a referral for the following job:

                Job Title: {job_title}
                Company: {company}
                Job ID: {job_id}
                Job URL: {job_url}

                The message should:
                1. Be professional and courteous
                2. Briefly mention interest in the role
                3. Ask for a referral
                4. Offer to provide more information
                5. Be under 300 characters (LinkedIn's connection request limit)
                6. Include [NAME] as a placeholder for the recipient's name
                7. Do NOT include a placeholder for the sender's name

                ONLY return the message text, nothing else.
                """,
                input_variables=["job_title", "company", "job_id", "job_url"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            result = chain.invoke({
                "job_title": job_data.get("job_title", "the position"),
                "company": job_data.get("company", "your company"),
                "job_id": job_data.get("job_id", ""),
                "job_url": job_data.get("job_url", "")
            })
            
            # Clean and return the response
            message = result['text'].strip()
            
            # Ensure it's under 300 characters for LinkedIn connection requests
            if len(message) > 300:
                message = message[:297] + "..."
                
            return message

        except Exception as e:
            logger.error(f"Error generating connection message: {str(e)}")
            # Return a default message
            return f"Hi [NAME], I'm interested in the {job_data.get('job_title', 'position')} at {job_data.get('company', 'your company')}. Would you be open to referring me for this role? Thanks!"
    
    def generate_inmail_message(self, job_data: Dict) -> str:
        """Generate a more detailed InMail or message for LinkedIn with [NAME] placeholder"""
        try:
            prompt = PromptTemplate(
                template="""Create a detailed LinkedIn message to ask for a referral for the following job:

                Job Title: {job_title}
                Company: {company}
                Job ID: {job_id}
                Job URL: {job_url}
                Technical Skills: {technical_skills}
                Experience: {experience}

                The message should:
                1. Be professional and personalized
                2. Start with "Hi [NAME]," as a placeholder for the recipient's name
                3. Briefly introduce yourself and your interest in the role
                4. Mention 2-3 relevant skills that match the job
                5. Politely ask for a referral
                6. Include the job link and ID
                7. Offer to share resume/portfolio
                8. Thank them for their time
                9. End with "Best regards," (no sender name)
                10. Be under 1000 characters

                ONLY return the message text, nothing else.
                """,
                input_variables=["job_title", "company", "job_id", "job_url", "technical_skills", "experience"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            result = chain.invoke({
                "job_title": job_data.get("job_title", "the position"),
                "company": job_data.get("company", "your company"),
                "job_id": job_data.get("job_id", ""),
                "job_url": job_data.get("job_url", ""),
                "technical_skills": ", ".join(job_data.get("technical_skills", [])[:5]),
                "experience": job_data.get("required_experience", "")
            })
            
            # Clean and return the response
            return result['text'].strip()

        except Exception as e:
            logger.error(f"Error generating InMail message: {str(e)}")
            # Return a default message
            job_title = job_data.get("job_title", "the position")
            company = job_data.get("company", "the company")
            
            return f"""Hi [NAME],

I hope this message finds you well. I'm interested in the {job_title} role at {company} and noticed you work there.

Would you be open to referring me for this position? I'd be happy to share my resume and discuss how my background aligns with the role.

Job link: {job_data.get("job_url", "")}
Job ID: {job_data.get("job_id", "Not available")}

Thank you for considering my request.

Best regards"""
    
    def search_company_employees(self, company: str, job_title: str) -> None:
        """Open LinkedIn search for employees at the company with similar roles"""
        search_query = f"{company} {job_title}"
        encoded_query = search_query.replace(" ", "%20")
        linkedin_url = f"https://www.linkedin.com/search/results/people/?keywords={encoded_query}&origin=GLOBAL_SEARCH_HEADER"
        
        # Open the URL in the default browser
        webbrowser.open(linkedin_url)
        return linkedin_url

class EnhancedJobScraper:
    def __init__(self, gemini_api_key: str, notion_client=None):
        self.setup_chrome_options()
        self.setup_llm(gemini_api_key)
        self.setup_output_parsers()
        self.notion_client = notion_client
        self.linkedin_helper = LinkedInHelper(gemini_api_key)
        
    def setup_chrome_options(self):
        """Configure Chrome options for reliable scraping in cloud environments"""
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--enable-javascript")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Add binary location for Streamlit Cloud
        if IS_STREAMLIT_CLOUD:
            # For Streamlit Cloud deployment
            self.chrome_options.binary_location = "/usr/bin/chromium-browser"
            self.chrome_options.add_argument("--disable-extensions")
            self.chrome_options.add_argument("--disable-setuid-sandbox")
            self.chrome_options.add_argument("--single-process")
            self.chrome_options.add_argument("--ignore-certificate-errors")
        
    def setup_llm(self, api_key: str):
        self.llm = GoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=api_key,
            temperature=0.2,
            max_output_tokens=2000
        )
        
    def setup_output_parsers(self):
        response_schemas = [
            ResponseSchema(name="technical_skills", type="List[str]", description="Technical skills required"),
            ResponseSchema(name="soft_skills", type="List[str]", description="Soft skills required"),
            ResponseSchema(name="certifications", type="List[str]", description="Required certifications"),
            ResponseSchema(name="experience", type="str", description="Years of experience required"),
            ResponseSchema(name="education", type="List[str]", description="Education requirements"),
            ResponseSchema(name="keywords", type="List[str]", description="Important keywords from the job description")
        ]
        self.output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
        
    def scrape_website(self, url: str) -> Dict:
        """Scrape job description from URL with improved error handling"""
        job_data = {
            "job_url": url,
            "job_description": "",
            "job_title": "",
            "company": "",
            "location": "",
            "job_id": "",
            "salary_range": "",
            "employment_type": "",
            "experience_level": ""
        }
        
        # First try with Selenium
        try:
            logger.info(f"Starting to scrape URL: {url}")
            
            # Setup webdriver with compatibility for both local and cloud environments
            try:
                # For Streamlit Cloud
                if IS_STREAMLIT_CLOUD:
                    try:
                        # Try using the system chromedriver
                        driver = webdriver.Chrome(options=self.chrome_options)
                    except Exception as cloud_e:
                        logger.error(f"Error with default Chrome setup in cloud: {str(cloud_e)}")
                        # Fallback to specified chromedriver path
                        chrome_driver_path = os.environ.get("CHROMEDRIVER_PATH", "/usr/local/bin/chromedriver")
                        driver = webdriver.Chrome(executable_path=chrome_driver_path, options=self.chrome_options)
                else:
                    # For local development with automatic ChromeDriver management
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=self.chrome_options)
            except Exception as e:
                logger.error(f"Error setting up Chrome driver: {str(e)}")
                # If all Selenium methods fail, fall back to requests
                return self._fallback_scrape_with_requests(url, job_data)
            
            try:
                driver.get(url)
                logger.info("Page loaded successfully")

                # Wait for body to be present
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Wait additional time for dynamic content
                time.sleep(3)
                
                # Get page source and parse with BeautifulSoup
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Extract job title, company, and location
                job_data = {
                    "job_url": url,
                    "job_description": "",
                    "job_title": "",
                    "company": "",
                    "location": "",
                    "job_id": ""
                }
                
                # Try to extract job ID from URL or page content
                job_id_patterns = [
                    r'(?:jobId|job_id|jobid|job-id)=([a-zA-Z0-9_-]+)',
                    r'(?:jobs?|positions?)/([a-zA-Z0-9_-]+)(?:/|$)',
                    r'(?:req|requisition|posting)(?:_|-)?(?:id|num|number)=?([a-zA-Z0-9_-]+)',
                ]
                
                # Check URL for job ID
                for pattern in job_id_patterns:
                    match = re.search(pattern, url, re.IGNORECASE)
                    if match:
                        job_data["job_id"] = match.group(1)
                        break
                
                # If not found in URL, look in page content
                if not job_data["job_id"]:
                    # Look for common job ID labels in the page
                    id_labels = [
                        "Job ID", "Job #", "Requisition ID", "Req ID", "Position ID", 
                        "Posting ID", "Job Reference", "Reference Code"
                    ]
                    
                    for label in id_labels:
                        elements = soup.find_all(string=re.compile(f"{label}[: ]"))
                        if elements:
                            # Try to extract the ID that follows the label
                            for element in elements:
                                text = element.parent.get_text()
                                match = re.search(f"{label}[: ]*([a-zA-Z0-9_-]+)", text, re.IGNORECASE)
                                if match:
                                    job_data["job_id"] = match.group(1)
                                    break
                        
                        if job_data["job_id"]:
                            break
                
                # Try to extract job title
                title_selectors = [
                    "h1", 
                    "h1[class*='title']", 
                    "h2[class*='title']", 
                    "div[class*='title']",
                    "[class*='job-title']",
                    "[class*='jobtitle']"
                ]
                
                for selector in title_selectors:
                    elements = soup.select(selector)
                    if elements:
                        job_data["job_title"] = elements[0].get_text(strip=True)
                        break
                
                # Try to extract company name
                company_selectors = [
                    "[class*='company']",
                    "[class*='employer']",
                    "[class*='organization']",
                    "a[data-automation='jobCompany']"
                ]
                
                for selector in company_selectors:
                    elements = soup.select(selector)
                    if elements:
                        job_data["company"] = elements[0].get_text(strip=True)
                        break
                
                # Try to extract location
                location_selectors = [
                    "[class*='location']",
                    "[class*='address']",
                    "[class*='region']",
                    "[data-automation='jobLocation']"
                ]
                
                for selector in location_selectors:
                    elements = soup.select(selector)
                    if elements:
                        job_data["location"] = elements[0].get_text(strip=True)
                        break
                
                # Try different methods to find job description
                job_description = ""
                
                # Method 1: Look for common job description containers
                selectors = [
                    "div[class*='job-description']",
                    "div[class*='description']",
                    "div[class*='details']",
                    "#job-description",
                    "[class*='posting']",
                    "article"
                ]
                
                for selector in selectors:
                    elements = soup.select(selector)
                    if elements:
                        job_description = max([elem.get_text(strip=True) for elem in elements], key=len)
                        if len(job_description) > 100:  # Minimum length check
                            break
                
                # Method 2: Find largest text block if no description found
                if not job_description:
                    text_blocks = [p.get_text(strip=True) for p in soup.find_all(['p', 'div', 'section'])]
                    if text_blocks:
                        job_description = max(text_blocks, key=len)
                
                if not job_description:
                    raise ValueError("Could not find job description content")
                
                # Clean the text
                job_description = re.sub(r'\s+', ' ', job_description).strip()
                job_data["job_description"] = job_description
                
                logger.info(f"Successfully extracted job description ({len(job_description)} characters)")
                
                return job_data
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Error scraping website: {str(e)}")
            raise ValueError(f"Failed to extract job content: {str(e)}")
    
    def analyze_job_description(self, job_data: Dict) -> Dict:
        """Analyze job description text and extract structured information"""
        try:
            prompt = PromptTemplate(
                template="""Analyze this job description and extract key information in EXACTLY this format:

                Job Title: {job_title}
                Company: {company}
                Location: {location}
                Job Description:
                {job_description}

                STRICT OUTPUT FORMAT (Return ONLY this JSON object):
                {{
                    "job_title": "Extracted or improved job title",
                    "company": "Extracted or confirmed company name",
                    "location": "Extracted or confirmed location",
                    "salary": "Any salary information found or 'Not specified'",
                    "technical_skills": ["skill1", "skill2"],
                    "soft_skills": ["skill1", "skill2"],
                    "required_experience": "X years",
                    "education_requirements": ["requirement1", "requirement2"],
                    "job_type": "Full-time/Part-time/Contract/etc.",
                    "industry": "Industry of the job",
                    "key_responsibilities": ["responsibility1", "responsibility2"],
                    "benefits": ["benefit1", "benefit2"],
                    "application_deadline": "Date if mentioned or 'Not specified'",
                    "notes": "Any other important information"
                }}

                STRICT RULES:
                1. Return ONLY the JSON object, no other text
                2. ALL keys must be present in the response
                3. If information is not available, use "Not specified" for string fields and empty arrays for list fields
                4. Improve the job title, company, and location if the provided values are empty or incomplete
                5. Extract any salary information if available
                6. technical_skills: List all technical skills mentioned (programming languages, tools, platforms, etc.)
                7. soft_skills: List all soft skills and competencies mentioned
                8. Do not include any explanatory text or markdown
                """,
                input_variables=["job_title", "company", "location", "job_description"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            result = chain.invoke({
                "job_title": job_data.get("job_title", ""),
                "company": job_data.get("company", ""),
                "location": job_data.get("location", ""),
                "job_description": job_data.get("job_description", "")
            })
            
            # Clean and parse the response
            response_text = result['text'].strip()
            # Remove any markdown code block indicators
            response_text = response_text.replace('```json', '').replace('```', '')
            
            # Find the JSON object
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                response_text = response_text[start_idx:end_idx]
            
            # Parse and validate response
            response = json.loads(response_text)
            
            # Ensure all required keys exist
            required_keys = {
                "job_title",
                "company",
                "location",
                "salary",
                "technical_skills",
                "soft_skills",
                "required_experience",
                "education_requirements",
                "job_type",
                "industry",
                "key_responsibilities",
                "benefits",
                "application_deadline",
                "notes"
            }
            
            # Initialize default structure
            default_structure = {
                "job_title": job_data.get("job_title", "Untitled Job"),
                "company": job_data.get("company", "Unknown"),
                "location": job_data.get("location", "Remote/Unknown"),
                "salary": "Not specified",
                "technical_skills": [],
                "soft_skills": [],
                "required_experience": "Not specified",
                "education_requirements": [],
                "job_type": "Not specified",
                "industry": "Not specified",
                "key_responsibilities": [],
                "benefits": [],
                "application_deadline": "Not specified",
                "notes": ""
            }
            
            # Merge response with default structure
            for key in required_keys:
                if key not in response:
                    response[key] = default_structure[key]
                    logger.warning(f"Missing key '{key}' in response, using default value")
            
            # Validate types
            list_keys = ["technical_skills", "soft_skills", "education_requirements", 
                         "key_responsibilities", "benefits"]
            for key in list_keys:
                if not isinstance(response[key], list):
                    response[key] = list(response[key]) if response[key] else []
            
            # Add the original job URL and description to the response
            response["job_url"] = job_data.get("job_url", "")
            response["job_description"] = job_data.get("job_description", "")
            response["job_id"] = job_data.get("job_id", "")
            
            # Generate message templates
            connection_message = self.linkedin_helper.generate_connection_message(response)
            inmail_message = self.linkedin_helper.generate_inmail_message(response)
            
            response["connection_message_template"] = connection_message
            response["inmail_message_template"] = inmail_message
            
            return response

        except Exception as e:
            logger.error(f"Error analyzing job description: {str(e)}")
            logger.error(f"Raw response: {result['text'] if 'result' in locals() else 'No response'}")
            # Return default structure on error
            return {
                "job_title": job_data.get("job_title", "Untitled Job"),
                "company": job_data.get("company", "Unknown"),
                "location": job_data.get("location", "Remote/Unknown"),
                "salary": "Not specified",
                "technical_skills": [],
                "soft_skills": [],
                "required_experience": "Not specified",
                "education_requirements": [],
                "job_type": "Not specified",
                "industry": "Not specified",
                "key_responsibilities": [],
                "benefits": [],
                "application_deadline": "Not specified",
                "notes": "",
                "job_url": job_data.get("job_url", ""),
                "job_description": job_data.get("job_description", ""),
                "job_id": job_data.get("job_id", ""),
                "connection_message_template": f"Hi [NAME], I'm interested in the {job_data.get('job_title', 'position')} at {job_data.get('company', 'your company')}. Would you be open to referring me for this role? Thanks!",
                "inmail_message_template": f"Hi [NAME],\n\nI hope this message finds you well. I'm interested in the {job_data.get('job_title', 'position')} role at {job_data.get('company', 'your company')} and noticed you work there.\n\nWould you be open to referring me for this position?\n\nThank you for considering my request.\n\nBest regards"
            }
    
    def process_job_url(self, url: str) -> Dict:
        """Process a job URL: scrape, analyze, and save to Notion"""
        # Scrape the job posting
        job_data = self.scrape_website(url)
        
        # Analyze the job description
        analyzed_data = self.analyze_job_description(job_data)
        
        # Save to Notion if client is available
        if self.notion_client:
            notion_page = self.notion_client.add_job_to_database(analyzed_data)
            analyzed_data["notion_page_id"] = notion_page.get("id")
            logger.info(f"Job added to Notion database: {analyzed_data['job_title']}")
        
        return analyzed_data
    
    def manage_referrals(self, job_data: Dict) -> Dict:
        """Manage referrals for a job posting and return updated data"""
        if not job_data.get("company"):
            return {"error": "Company information is missing. Cannot search for referrals."}
        
        # Generate connection messages if not already present
        if not job_data.get("connection_message_template"):
            job_data["connection_message_template"] = self.linkedin_helper.generate_connection_message(job_data)
        
        if not job_data.get("inmail_message_template"):
            job_data["inmail_message_template"] = self.linkedin_helper.generate_inmail_message(job_data)
        
        # Search for company employees on LinkedIn
        linkedin_search_url = self.linkedin_helper.search_company_employees(
            job_data.get("company", ""), 
            job_data.get("job_title", "")
        )
        
        job_data["linkedin_search_url"] = linkedin_search_url
        
        return job_data

    def _fallback_scrape_with_requests(self, url: str, job_data: Dict) -> Dict:
        """Fallback method to scrape job data using requests when Selenium fails"""
        logger.info("Using requests fallback method for scraping")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract job ID from URL or page content
            job_id_patterns = [
                r'jobId=([^&]+)',
                r'job[_-]id=([^&]+)',
                r'jobs/([^/\?]+)',
                r'job/([^/\?]+)',
                r'careers/([^/\?]+)',
                r'positions/([^/\?]+)'
            ]
            
            for pattern in job_id_patterns:
                match = re.search(pattern, url)
                if match:
                    job_data["job_id"] = match.group(1)
                    break
            
            # Try to extract job title
            title_selectors = [
                "h1", 
                "h1[class*='title']", 
                "h2[class*='title']", 
                "div[class*='title']",
                "[class*='job-title']",
                "[class*='jobtitle']"
            ]
            
            for selector in title_selectors:
                elements = soup.select(selector)
                if elements:
                    job_data["job_title"] = elements[0].get_text(strip=True)
                    break
            
            # Try to extract company name
            company_selectors = [
                "[class*='company']",
                "[class*='employer']",
                "[class*='organization']",
                "a[data-automation='jobCompany']"
            ]
            
            for selector in company_selectors:
                elements = soup.select(selector)
                if elements:
                    job_data["company"] = elements[0].get_text(strip=True)
                    break
            
            # Try to extract location
            location_selectors = [
                "[class*='location']",
                "[class*='address']",
                "[class*='region']",
                "[data-automation='jobLocation']"
            ]
            
            for selector in location_selectors:
                elements = soup.select(selector)
                if elements:
                    job_data["location"] = elements[0].get_text(strip=True)
                    break
            
            # Extract job description
            description_selectors = [
                "[class*='description']",
                "[class*='details']",
                "[class*='content']",
                "div[id*='description']",
                "div[id*='details']",
                "div[id*='job-details']",
                "div[class*='job-details']",
                "article"
            ]
            
            for selector in description_selectors:
                elements = soup.select(selector)
                if elements:
                    job_data["job_description"] = elements[0].get_text(strip=True)
                    break
            
            # If we still don't have a job description, use the body content
            if not job_data["job_description"] and soup.body:
                job_data["job_description"] = soup.body.get_text(strip=True)
            
            logger.info("Successfully scraped job data using requests fallback")
            return job_data
            
        except Exception as e:
            logger.error(f"Error in requests fallback scraping: {str(e)}")
            job_data["job_description"] = f"Failed to scrape job description. Please copy and paste the job description manually. Error: {str(e)}"
            return job_data

def run_streamlit_app():
    st.set_page_config(
        page_title="Job Application Tracker",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #0D47A1;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 5px solid #1E88E5;
    }
    .info-box {
        background-color: #e3f2fd;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 5px solid #2196F3;
    }
    .error-msg {
        background-color: #ffebee;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 5px solid #f44336;
    }
    .skill-tag {
        display: inline-block;
        background-color: #e1f5fe;
        color: #0277bd;
        padding: 0.25rem 0.5rem;
        margin: 0.25rem;
        border-radius: 15px;
        font-size: 0.85rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if "api_keys_set" not in st.session_state:
        st.session_state.api_keys_set = False
    
    if "job_scraper" not in st.session_state:
        st.session_state.job_scraper = None
    
    if "notion_client" not in st.session_state:
        st.session_state.notion_client = None
    
    if "current_job" not in st.session_state:
        st.session_state.current_job = None
    
    if "saved_jobs" not in st.session_state:
        st.session_state.saved_jobs = []
    
    if "use_default_credentials" not in st.session_state:
        st.session_state.use_default_credentials = False
    
    # Default credentials
    DEFAULT_GEMINI_API_KEY = "AIzaSyCkb4a_yq_Iviefm_FJHQr40ukm7BqlLww"
    DEFAULT_NOTION_API_KEY = "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"
    DEFAULT_DATABASE_ID = "1b32f69c-d22c-811b-9a38-dd14fcfb7de4"
    DEFAULT_PAGE_ID = "1b32f69cd22c80909a03f7f0b16e89ad"
    DEFAULT_PASSWORD = "Nihal6565"
    
    # Sidebar navigation
    with st.sidebar:
        st.title("Job Tracker")
        
        # Define the page variable here
        page = st.radio(
            "Navigation",
            ["Process New Job", "Manage Current Job", "View Saved Jobs"]
        )
        
        st.markdown("---")
        
        st.markdown("## ⚙️ Configuration")
        
        # Option to use default credentials
        use_default = st.checkbox("Use Default Credentials", value=st.session_state.use_default_credentials)
        
        if use_default:
            if st.session_state.use_default_credentials:
                st.success("Using default credentials")
                if st.button("Clear Default Credentials"):
                    st.session_state.use_default_credentials = False
                    st.rerun()
            else:
                password = st.text_input("Enter password to use default credentials:", type="password")
                if st.button("Validate Password"):
                    if password == DEFAULT_PASSWORD:
                        st.session_state.use_default_credentials = True
                        
                        # Set default credentials
                        gemini_api_key = DEFAULT_GEMINI_API_KEY
                        notion_api_key = DEFAULT_NOTION_API_KEY
                        notion_database_id = DEFAULT_DATABASE_ID
                        
                        # Save to environment variables
                        os.environ["GEMINI_API_KEY"] = gemini_api_key
                        os.environ["NOTION_API_KEY"] = notion_api_key
                        os.environ["NOTION_DATABASE_ID"] = notion_database_id
                        
                        # Initialize clients
                        try:
                            notion_client = NotionClient(notion_api_key, database_id=notion_database_id)
                            st.session_state.notion_client = notion_client
                            st.session_state.job_scraper = EnhancedJobScraper(gemini_api_key, notion_client)
                            st.session_state.api_keys_set = True
                            st.success("Default credentials set successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error initializing with default credentials: {str(e)}")
                    else:
                        st.error("Invalid password. Please try again.")
        elif not use_default:
            st.session_state.use_default_credentials = False
        
        # Only show API key inputs if not using default credentials
        if not st.session_state.use_default_credentials:
            # Gemini API Key
            gemini_api_key = st.text_input("Gemini API Key:", 
                                          value=os.environ.get("GEMINI_API_KEY", ""),
                                          type="password")
            
            # Notion API Key
            notion_api_key = st.text_input("Notion API Key:", 
                                          value=os.environ.get("NOTION_API_KEY", ""),
                                          type="password")
            
            # Notion Database Options
            if notion_api_key:
                notion_option = st.radio(
                    "Notion Database Option:",
                    ["Create New Database", "Use Existing Database", "No Notion Integration"]
                )
                
                if notion_option == "Create New Database":
                    notion_page_id = st.text_input("Notion Page ID (where to create database):", 
                                                 value=os.environ.get("NOTION_PAGE_ID", ""))
                    
                    if st.button("Create Database & Set API Keys"):
                        if gemini_api_key and notion_api_key and notion_page_id:
                            try:
                                with st.spinner("Creating Notion database..."):
                                    notion_client = NotionClient(notion_api_key, page_id=notion_page_id)
                                    
                                    # Save to environment variables
                                    os.environ["GEMINI_API_KEY"] = gemini_api_key
                                    os.environ["NOTION_API_KEY"] = notion_api_key
                                    os.environ["NOTION_PAGE_ID"] = notion_page_id
                                    os.environ["NOTION_DATABASE_ID"] = notion_client.database_id
                                    
                                    st.session_state.notion_client = notion_client
                                    st.session_state.job_scraper = EnhancedJobScraper(gemini_api_key, notion_client)
                                    st.session_state.api_keys_set = True
                                    st.success(f"Database created successfully! ID: {notion_client.database_id}")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error creating database: {str(e)}")
                    else:
                            st.error("All fields are required")
                            
                elif notion_option == "Use Existing Database":
                    notion_database_id = st.text_input("Notion Database ID:", 
                                                     value=os.environ.get("NOTION_DATABASE_ID", ""))
                    
                    if st.button("Validate & Set API Keys"):
                        if gemini_api_key and notion_api_key and notion_database_id:
                            try:
                                with st.spinner("Validating Notion database..."):
                                    notion_client = NotionClient(notion_api_key, database_id=notion_database_id)
                                    
                                    # Validate database schema
                                    is_valid, message = notion_client.validate_database_schema()
                                    
                                    if not is_valid:
                                        st.warning(f"Database schema validation: {message}")
                                        
                                        # Ask if user wants to update schema
                                        if st.button("Update Database Schema"):
                                            success, update_msg = notion_client.update_database_schema()
                                            if success:
                                                st.success(update_msg)
                                    else:
                                        st.success("Database schema is valid!")
                                    
                                    # Save to environment variables
                                    os.environ["GEMINI_API_KEY"] = gemini_api_key
                                    os.environ["NOTION_API_KEY"] = notion_api_key
                                    os.environ["NOTION_DATABASE_ID"] = notion_database_id
                                    
                                    st.session_state.notion_client = notion_client
                                    st.session_state.job_scraper = EnhancedJobScraper(gemini_api_key, notion_client)
                                    st.session_state.api_keys_set = True
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error validating database: {str(e)}")
                    else:
                            st.error("All fields are required")
                
                else:  # No Notion Integration
                    if st.button("Set API Keys"):
                        if gemini_api_key:
                            os.environ["GEMINI_API_KEY"] = gemini_api_key
                            st.session_state.job_scraper = EnhancedJobScraper(gemini_api_key)
                            st.session_state.api_keys_set = True
                            st.rerun()
                        else:
                            st.error("Gemini API Key is required")
            else:
                # Just Gemini API without Notion
                if st.button("Set API Keys"):
                    if gemini_api_key:
                        os.environ["GEMINI_API_KEY"] = gemini_api_key
                        st.session_state.job_scraper = EnhancedJobScraper(gemini_api_key)
                        st.session_state.api_keys_set = True
                        st.rerun()
                    else:
                        st.error("Gemini API Key is required")
    
    # Main content
    if not st.session_state.api_keys_set:
        st.markdown('<div class="main-header">Welcome to Job Application Tracker</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">Please configure your API keys in the sidebar to get started.</div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### How to use this app:
        
        1. Enter your Gemini API key in the sidebar
        2. (Optional) Configure Notion integration for job tracking
        3. Process job URLs to extract and analyze job details
        4. Generate personalized referral messages
        5. Track your job applications and referrals
        
        This app helps you manage your job search by automatically extracting job details and creating personalized referral request messages.
        
        **Quick Start**: You can use the "Use Default Credentials" option with the provided password to quickly set up the app with pre-configured API keys.
        """)
        return
    
    if page == "Process New Job":
        st.markdown('<div class="main-header">🚀 Job Application Tracker</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Process New Job</div>', unsafe_allow_html=True)
        
        with st.form("job_url_form"):
            job_url = st.text_input("Enter job posting URL:", placeholder="https://example.com/jobs/12345")
            submitted = st.form_submit_button("Process Job")
            
        if submitted and job_url:
            if not job_url.startswith(('http://', 'https://')):
                st.error("Invalid URL format. Please include http:// or https://")
            else:
                with st.spinner("Processing job posting... This may take a minute..."):
                    try:
                        job_data = st.session_state.job_scraper.process_job_url(job_url)
                        st.session_state.current_job = job_data
                        st.success("Job processed successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error processing job: {str(e)}")
    
    elif page == "Manage Current Job" and st.session_state.current_job:
        job = st.session_state.current_job
        
        st.markdown(f'<div class="main-header">{job.get("job_title", "Untitled Job")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sub-header">at {job.get("company", "Unknown Company")}</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("### 📝 Job Details")
            st.markdown(f"**Location:** {job.get('location', 'Not specified')}")
            st.markdown(f"**Job Type:** {job.get('job_type', 'Not specified')}")
            st.markdown(f"**Industry:** {job.get('industry', 'Not specified')}")
            st.markdown(f"**Salary:** {job.get('salary', 'Not specified')}")
            st.markdown(f"**Experience Required:** {job.get('required_experience', 'Not specified')}")
            
            if job.get('education_requirements'):
                st.markdown("**Education Requirements:**")
                for edu in job.get('education_requirements', []):
                    st.markdown(f"- {edu}")
            
            if job.get('job_id'):
                st.markdown(f"**Job ID:** {job.get('job_id')}")
            
            st.markdown(f"**Job URL:** [Link]({job.get('job_url', '#')})")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("### 🔍 Skills Required")
            
            if job.get('technical_skills'):
                st.markdown("**Technical Skills:**")
                skills_html = ""
                for skill in job.get('technical_skills', []):
                    skills_html += f'<span class="skill-tag">{skill}</span>'
                st.markdown(skills_html, unsafe_allow_html=True)
            
            if job.get('soft_skills'):
                st.markdown("**Soft Skills:**")
                skills_html = ""
                for skill in job.get('soft_skills', []):
                    skills_html += f'<span class="skill-tag">{skill}</span>'
                st.markdown(skills_html, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            if job.get('key_responsibilities'):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown("### 📋 Key Responsibilities")
                for resp in job.get('key_responsibilities', []):
                    st.markdown(f"- {resp}")
                st.markdown('</div>', unsafe_allow_html=True)
            
            if job.get('benefits'):
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown("### 🎁 Benefits")
                for benefit in job.get('benefits', []):
                    st.markdown(f"- {benefit}")
                st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("### 🔗 Referral Management")
            
            if st.button("Search for Connections on LinkedIn"):
                with st.spinner("Opening LinkedIn search..."):
                    updated_job = st.session_state.job_scraper.manage_referrals(job)
                    st.session_state.current_job = updated_job
                    st.success("LinkedIn search opened in a new tab")
            
            st.markdown("### 📨 Connection Message Template")
            connection_msg = job.get("connection_message_template", "")
            edited_connection_msg = st.text_area("Edit connection message (300 char limit):", 
                                                value=connection_msg, 
                                                height=150,
                                                max_chars=300)
            
            if edited_connection_msg != connection_msg:
                st.session_state.current_job["connection_message_template"] = edited_connection_msg
            
            if st.button("Copy Connection Message"):
                pyperclip.copy(edited_connection_msg)
                st.success("Message copied to clipboard!")
            
            st.markdown("### 📧 InMail Message Template")
            inmail_msg = job.get("inmail_message_template", "")
            edited_inmail_msg = st.text_area("Edit InMail message:", 
                                            value=inmail_msg, 
                                            height=300)
            
            if edited_inmail_msg != inmail_msg:
                st.session_state.current_job["inmail_message_template"] = edited_inmail_msg
            
            if st.button("Copy InMail Message"):
                pyperclip.copy(edited_inmail_msg)
                st.success("Message copied to clipboard!")
            
            if st.session_state.notion_client and job.get("notion_page_id"):
                if st.button("Update Message Templates in Notion"):
                    try:
                        properties = {
                            "Connection Message Template": {
                                "rich_text": [
                                    {
                                        "text": {
                                            "content": edited_connection_msg
                                        }
                                    }
                                ]
                            },
                            "InMail Message Template": {
                                "rich_text": [
                                    {
                                        "text": {
                                            "content": edited_inmail_msg
                                        }
                                    }
                                ]
                            }
                        }
                        st.session_state.notion_client.update_job_entry(job["notion_page_id"], properties)
                        st.success("Message templates updated in Notion!")
                    except Exception as e:
                        st.error(f"Error updating Notion: {str(e)}")
        
        # Job Description
        with st.expander("View Full Job Description"):
            st.markdown(job.get("job_description", "No description available"))
    
    elif page == "Manage Current Job" and not st.session_state.current_job:
        st.markdown('<div class="main-header">No Current Job</div>', unsafe_allow_html=True)
        st.markdown('<div class="info-box">Please process a job first or select a saved job.</div>', unsafe_allow_html=True)
    
    elif page == "View Saved Jobs":
        st.markdown('<div class="main-header">Saved Jobs</div>', unsafe_allow_html=True)
        
        if not st.session_state.notion_client:
            st.markdown('<div class="error-msg">Notion integration not configured. Cannot view saved jobs.</div>', unsafe_allow_html=True)
            return
        
        # Load jobs if not already loaded
        if not st.session_state.saved_jobs:
            try:
                with st.spinner("Loading saved jobs..."):
                    entries = st.session_state.notion_client.get_job_entries()
                    st.session_state.saved_jobs = entries
            except Exception as e:
                st.error(f"Error loading jobs: {str(e)}")
                return
        
        if not st.session_state.saved_jobs:
            st.markdown('<div class="info-box">No jobs found in the database.</div>', unsafe_allow_html=True)
            return
        
        # Display jobs in a table
        job_data = []
        for entry in st.session_state.saved_jobs:
            props = entry.get("properties", {})
            
            # Extract job title
            title = "Untitled Job"
            if "Job Title" in props and props["Job Title"].get("title"):
                title_items = props["Job Title"]["title"]
                if title_items and "text" in title_items[0]:
                    title = title_items[0]["text"].get("content", "Untitled Job")
            
            # Extract company
            company = "Unknown"
            if "Company" in props and props["Company"].get("rich_text"):
                company_items = props["Company"]["rich_text"]
                if company_items and "text" in company_items[0]:
                    company = company_items[0]["text"].get("content", "Unknown")
            
            # Extract status
            status = "Not Applied"
            if "Status" in props and props["Status"].get("select"):
                status = props["Status"]["select"].get("name", "Not Applied")
            
            # Extract referral status
            referral_status = "Not Started"
            if "Referral Status" in props and props["Referral Status"].get("select"):
                referral_status = props["Referral Status"]["select"].get("name", "Not Started")
            
            job_data.append({
                "id": entry.get("id"),
                "title": title,
                "company": company,
                "status": status,
                "referral": referral_status
            })
        
        # Convert to DataFrame for display
        df = pd.DataFrame(job_data)
        
        # Add selection column
        st.dataframe(
            df[["title", "company", "status", "referral"]],
            column_config={
                "title": "Job Title",
                "company": "Company",
                "status": "Application Status",
                "referral": "Referral Status"
            },
            use_container_width=True
        )
        
        # Job selection
        selected_job_idx = st.selectbox("Select a job to manage:", 
                                      options=range(len(job_data)),
                                      format_func=lambda x: f"{job_data[x]['title']} at {job_data[x]['company']}")
        
        if st.button("Load Selected Job"):
            selected_entry_id = job_data[selected_job_idx]["id"]
            
            try:
                with st.spinner("Loading job details..."):
                    # Get the full entry from Notion
                    entry = st.session_state.notion_client.get_job_entry(selected_entry_id)
                    props = entry.get("properties", {})
                    
                    # Extract job details
                    job_details = {
                        "notion_page_id": selected_entry_id,
                        "job_title": "",
                        "company": "",
                        "location": "",
                        "job_url": "",
                        "job_id": "",
                        "job_type": "",
                        "industry": "",
                        "salary": "",
                        "required_experience": "",
                        "technical_skills": [],
                        "soft_skills": [],
                        "education_requirements": [],
                        "connection_message_template": "",
                        "inmail_message_template": ""
                    }
                    
                    # Extract text fields
                    text_fields = {
                        "Job Title": "job_title",
                        "Company": "company",
                        "Location": "location",
                        "Job ID": "job_id",
                        "Job Type": "job_type",
                        "Industry": "industry",
                        "Salary": "salary",
                        "Experience Required": "required_experience",
                        "Connection Message Template": "connection_message_template",
                        "InMail Message Template": "inmail_message_template"
                    }
                    
                    for notion_key, detail_key in text_fields.items():
                        if notion_key in props:
                            if notion_key == "Job Title" and props[notion_key].get("title"):
                                items = props[notion_key]["title"]
                                if items and "text" in items[0]:
                                    job_details[detail_key] = items[0]["text"].get("content", "")
                            elif notion_key == "Job Type" and props[notion_key].get("select"):
                                job_details[detail_key] = props[notion_key]["select"].get("name", "")
                            elif props[notion_key].get("rich_text"):
                                items = props[notion_key]["rich_text"]
                                if items and "text" in items[0]:
                                    job_details[detail_key] = items[0]["text"].get("content", "")
                    
                    # Extract URL
                    if "Job URL" in props and props["Job URL"].get("url"):
                        job_details["job_url"] = props["Job URL"].get("url", "")
                    
                    # Extract multi-select fields
                    if "Technical Skills" in props and props["Technical Skills"].get("multi_select"):
                        job_details["technical_skills"] = [item.get("name", "") for item in props["Technical Skills"]["multi_select"]]
                    
                    if "Soft Skills" in props and props["Soft Skills"].get("multi_select"):
                        job_details["soft_skills"] = [item.get("name", "") for item in props["Soft Skills"]["multi_select"]]
                    
                    # Set as current job
                    st.session_state.current_job = job_details
                    st.success("Job loaded successfully!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Error loading job: {str(e)}")

if __name__ == "__main__":
    run_streamlit_app()