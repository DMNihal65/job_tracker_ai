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
from datetime import datetime
import requests
import pyperclip
import webbrowser

# LangChain components
from langchain_google_genai import GoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import StructuredOutputParser, ResponseSchema

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        """Add a job entry to the Notion database"""
        if not self.database_id:
            raise ValueError("No database ID available. Please create a database first.")
            
        url = "https://api.notion.com/v1/pages"
        
        # Format the data according to Notion API requirements
        properties = {
            "Job Title": {
                "title": [
                    {
                        "text": {
                            "content": job_data.get("job_title", "Untitled Job")
                        }
                    }
                ]
            },
            "Company": {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data.get("company", "Unknown")
                        }
                    }
                ]
            },
            "Location": {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data.get("location", "Remote/Unknown")
                        }
                    }
                ]
            },
            "Job URL": {
                "url": job_data.get("job_url", "")
            },
            "Date Applied": {
                "date": {
                    "start": datetime.now().strftime("%Y-%m-%d")
                }
            },
            "Status": {
                "select": {
                    "name": "Not Applied"
                }
            },
            "Job Type": {
                "select": {
                    "name": job_data.get("job_type", "Full-time") if job_data.get("job_type") != "Not specified" else "Full-time"
                }
            },
            "Industry": {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data.get("industry", "Not specified")
                        }
                    }
                ]
            },
            "Referral Status": {
                "select": {
                    "name": "Not Started"
                }
            },
            "Connection Messages Sent": {
                "number": 0
            },
            "Responses Received": {
                "number": 0
            }
        }
        
        # Add job ID if available
        job_id = job_data.get("job_id", "")
        if not job_id:
            # Try to extract job ID from URL
            url_match = re.search(r'(?:id=|\/jobs?\/|\/positions?\/)([a-zA-Z0-9_-]+)', job_data.get("job_url", ""))
            if url_match:
                job_id = url_match.group(1)
        
        if job_id:
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
        if job_data.get("technical_skills"):
            # Limit to 10 skills to avoid Notion API limits
            skills = job_data["technical_skills"][:10]
            properties["Technical Skills"] = {
                "multi_select": [{"name": skill} for skill in skills]
            }
            
        # Add soft skills if available
        if job_data.get("soft_skills"):
            # Limit to 10 skills to avoid Notion API limits
            skills = job_data["soft_skills"][:10]
            properties["Soft Skills"] = {
                "multi_select": [{"name": skill} for skill in skills]
            }
            
        # Add experience required if available
        if job_data.get("required_experience"):
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
        if job_data.get("education_requirements"):
            properties["Education"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": ", ".join(job_data["education_requirements"])
                        }
                    }
                ]
            }
            
        # Add salary if available
        if job_data.get("salary"):
            properties["Salary"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data["salary"]
                        }
                    }
                ]
            }
            
        # Add notes if available
        if job_data.get("notes"):
            properties["Notes"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": job_data["notes"]
                        }
                    }
                ]
            }
        
        # Add job description to the page content
        children = []
        if job_data.get("job_description"):
            # Split description into chunks if it's too long
            description = job_data["job_description"]
            max_length = 2000  # Notion API limit for text blocks
            
            children = [
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": "Job Description"}}]
                    }
                }
            ]
            
            # Add key responsibilities section if available
            if job_data.get("key_responsibilities"):
                children.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": "Key Responsibilities"}}]
                    }
                })
                
                for resp in job_data["key_responsibilities"]:
                    children.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": resp}}]
                        }
                    })
            
            # Add benefits section if available
            if job_data.get("benefits"):
                children.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": "Benefits"}}]
                    }
                })
                
                for benefit in job_data["benefits"]:
                    children.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": benefit}}]
                        }
                    })
            
            # Add referral section
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Referral Management"}}]
                }
            })
            
            # Add connection message template
            job_title = job_data.get("job_title", "the position")
            company = job_data.get("company", "the company")
            
            connection_template = f"""Hi [Name],

I hope this message finds you well. I noticed you work at {company} and I'm interested in the {job_title} role. 

I've applied through the portal, but I understand that referrals can be valuable. Would you be open to referring me for this position? I'd be happy to share my resume and discuss how my background aligns with the role.

Job link: {job_data.get("job_url", "")}
Job ID: {job_id if job_id else "Not available"}

Thank you for considering my request. I appreciate your time.

Best regards,
[Your Name]"""
            
            children.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": "Connection Message Template"}}]
                }
            })
            
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": connection_template}}]
                }
            })
            
            # Add full job description
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Full Description"}}]
                }
            })
            
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
        
        data = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
            "children": children
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        
        if response.status_code != 200:
            logger.error(f"Error adding job to Notion: {response.text}")
            raise Exception(f"Failed to add job to Notion: {response.status_code}")
        
        return response.json()

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
        """Generate a personalized connection message for LinkedIn"""
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
                6. Not include placeholders like [Name] or [Your Name]

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
            return f"Hi, I'm interested in the {job_data.get('job_title', 'position')} at {job_data.get('company', 'your company')}. Would you be open to referring me for this role? Thanks!"
    
    def generate_inmail_message(self, job_data: Dict) -> str:
        """Generate a more detailed InMail or message for LinkedIn"""
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
                2. Briefly introduce yourself and your interest in the role
                3. Mention 2-3 relevant skills that match the job
                4. Politely ask for a referral
                5. Include the job link and ID
                6. Offer to share resume/portfolio
                7. Thank them for their time
                8. Be under 1000 characters

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
            company = job_data.get("company", "your company")
            
            return f"""Hi,

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
        print(f"\nOpened LinkedIn search for: {search_query}")
        print("Please use this search to find potential referral connections.")

class EnhancedJobScraper:
    def __init__(self, gemini_api_key: str, notion_client=None):
        self.setup_chrome_options()
        self.setup_llm(gemini_api_key)
        self.setup_output_parsers()
        self.notion_client = notion_client
        self.linkedin_helper = LinkedInHelper(gemini_api_key)
        
    def setup_chrome_options(self):
        """Configure Chrome options for reliable scraping"""
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--enable-javascript")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
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
        try:
            logger.info(f"Starting to scrape URL: {url}")
            
            # Setup webdriver with automatic ChromeDriver management
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            
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
                "job_id": job_data.get("job_id", "")
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
    
    def manage_referrals(self, job_data: Dict) -> None:
        """Manage referrals for a job posting"""
        if not job_data.get("company"):
            print("Company information is missing. Cannot search for referrals.")
            return
        
        print("\n=== Referral Management ===")
        print("1. Search for company employees on LinkedIn")
        print("2. Generate connection request message")
        print("3. Generate detailed InMail/message")
        print("4. Update referral status in Notion")
        print("5. Back to main menu")
        
        choice = input("\nSelect an option (1-5): ").strip()
        
        if choice == "1":
            # Search for company employees on LinkedIn
            self.linkedin_helper.search_company_employees(
                job_data.get("company", ""), 
                job_data.get("job_title", "")
            )
            
        elif choice == "2":
            # Generate connection request message
            message = self.linkedin_helper.generate_connection_message(job_data)
            print("\n=== LinkedIn Connection Request Message ===")
            print(f"\n{message}")
            print(f"\nCharacter count: {len(message)}/300")
            
            # Copy to clipboard
            pyperclip.copy(message)
            print("\n✅ Message copied to clipboard!")
            
        elif choice == "3":
            # Generate detailed InMail/message
            message = self.linkedin_helper.generate_inmail_message(job_data)
            print("\n=== LinkedIn Detailed Message ===")
            print(f"\n{message}")
            print(f"\nCharacter count: {len(message)}")
            
            # Copy to clipboard
            pyperclip.copy(message)
            print("\n✅ Message copied to clipboard!")
            
        elif choice == "4":
            # Update referral status in Notion
            if not self.notion_client or not job_data.get("notion_page_id"):
                print("Notion integration not available or job not saved to Notion.")
                return
                
            print("\nUpdate referral status:")
            print("1. Not Started")
            print("2. Searching Connections")
            print("3. Requests Sent")
            print("4. Referral Received")
            print("5. No Connections Found")
            
            status_choice = input("\nSelect status (1-5): ").strip()
            status_map = {
                "1": "Not Started",
                "2": "Searching Connections",
                "3": "Requests Sent",
                "4": "Referral Received",
                "5": "No Connections Found"
            }
            
            if status_choice in status_map:
                status = status_map[status_choice]
                
                # Get additional information if needed
                connections = ""
                messages_sent = 0
                responses = 0
                
                if status_choice in ["3", "4"]:
                    connections = input("\nEnter names of connections (comma separated): ").strip()
                    messages_sent = int(input("Number of messages sent: ") or "0")
                    responses = int(input("Number of responses received: ") or "0")
                
                # Update Notion
                properties = {
                    "Referral Status": {
                        "select": {
                            "name": status
                        }
                    }
                }
                
                if connections:
                    properties["Referral Connections"] = {
                        "rich_text": [
                            {
                                "text": {
                                    "content": connections
                                }
                            }
                        ]
                    }
                
                if messages_sent > 0:
                    properties["Connection Messages Sent"] = {
                        "number": messages_sent
                    }
                
                if responses > 0:
                    properties["Responses Received"] = {
                        "number": responses
                    }
                
                self.notion_client.update_job_entry(job_data["notion_page_id"], properties)
                print(f"\n✅ Referral status updated to: {status}")
            else:
                print("\n❌ Invalid option selected.")

def main():
    # Load environment variables or use defaults
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCkb4a_yq_Iviefm_FJHQr40ukm7BqlLww")
    NOTION_API_KEY = os.environ.get("NOTION_API_KEY", "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")
    NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "1b32f69c-d22c-8185-8feb-ffa2cb233b05")
    NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID", "1b32f69cd22c80909a03f7f0b16e89ad")
    
    # Check if Notion credentials are available
    notion_client = None
    
    if NOTION_API_KEY:
        try:
            if NOTION_DATABASE_ID:
                notion_client = NotionClient(NOTION_API_KEY, database_id=NOTION_DATABASE_ID)
                print("Notion integration enabled with existing database.")
            elif NOTION_PAGE_ID:
                notion_client = NotionClient(NOTION_API_KEY, page_id=NOTION_PAGE_ID)
                print(f"Created new job tracking database in Notion with ID: {notion_client.database_id}")
                # Save the database ID for future use
                os.environ["NOTION_DATABASE_ID"] = notion_client.database_id
                print("Database ID saved for future use.")
            else:
                print("Notion API key provided but no database ID or page ID. Will configure later.")
        except Exception as e:
            print(f"Error setting up Notion: {str(e)}")
            notion_client = None
    else:
        print("Notion API key not provided. Running without Notion integration.")
    
    scraper = EnhancedJobScraper(GEMINI_API_KEY, notion_client)
    
    # Store the current job data for referral management
    current_job = None
    
    while True:
        print("\n=== Job Tracker ===")
        print("1. Process new job URL")
        print("2. Manage referrals for current job")
        print("3. View saved jobs")
        print("4. Configure Notion integration")
        print("5. Exit")
        
        choice = input("\nSelect an option (1-5): ").strip()
        
        if choice == "5":
            print("Goodbye!")
            break
            
        elif choice == "1":
            url = input("\nEnter job posting URL: ").strip()
            if not url.startswith(('http://', 'https://')):
                print("Invalid URL format. Please include http:// or https://")
                continue
            
            print("\nProcessing job posting... Please wait...")
            try:
                current_job = scraper.process_job_url(url)
                
                print("\n" + "="*50)
                print("           Job Details")
                print("="*50)
                
                print(f"\n📋 Job Title: {current_job['job_title']}")
                print(f"🏢 Company: {current_job['company']}")
                print(f"📍 Location: {current_job['location']}")
                print(f"💰 Salary: {current_job['salary']}")
                print(f"⏱️ Job Type: {current_job['job_type']}")
                print(f"🏭 Industry: {current_job['industry']}")
                
                if current_job.get('job_id'):
                    print(f"🔑 Job ID: {current_job['job_id']}")
                
                print("\n📚 Technical Skills Required:")
                if current_job.get('technical_skills'):
                    for skill in current_job['technical_skills']:
                        print(f"  • {skill}")
                else:
                    print("  No specific technical skills mentioned")
                
                print("\n🤝 Soft Skills Required:")
                if current_job.get('soft_skills'):
                    for skill in current_job['soft_skills']:
                        print(f"  • {skill}")
                else:
                    print("  No specific soft skills mentioned")
                
                print("\n📜 Education Requirements:")
                if current_job.get('education_requirements'):
                    for edu in current_job['education_requirements']:
                        print(f"  • {edu}")
                else:
                    print("  No specific education requirements mentioned")
                
                print("\n⏳ Experience Required:")
                print(f"  {current_job.get('required_experience', 'Not specified')}")
                
                print("\n🔑 Key Responsibilities:")
                if current_job.get('key_responsibilities'):
                    for resp in current_job['key_responsibilities']:
                        print(f"  • {resp}")
                else:
                    print("  No specific responsibilities mentioned")
                
                print("\n🎁 Benefits:")
                if current_job.get('benefits'):
                    for benefit in current_job['benefits']:
                        print(f"  • {benefit}")
                else:
                    print("  No specific benefits mentioned")
                
                if notion_client and notion_client.database_id:
                    print("\n✅ Job added to Notion database!")
                    print(f"   Database ID: {notion_client.database_id}")
                    print(f"   Page ID: {current_job.get('notion_page_id', 'Unknown')}")
                
                print("\nWould you like to manage referrals for this job? (y/n)")
                if input().lower().startswith('y'):
                    scraper.manage_referrals(current_job)
                
            except Exception as e:
                print(f"\nError occurred: {str(e)}")
                print("Please try again with a different URL")
        
        elif choice == "2":
            if current_job:
                scraper.manage_referrals(current_job)
            else:
                print("No job currently loaded. Please process a job URL first.")
        
        elif choice == "3":
            if not notion_client:
                print("Notion integration not available. Cannot view saved jobs.")
                continue
                
            try:
                print("\nFetching saved jobs from Notion...")
                entries = notion_client.get_job_entries()
                
                if not entries:
                    print("No jobs found in the database.")
                    continue
                
                print("\n=== Saved Jobs ===")
                for i, entry in enumerate(entries, 1):
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
                    
                    print(f"{i}. {title} at {company} - Status: {status}, Referral: {referral_status}")
                
                # Allow user to select a job to manage
                job_choice = input("\nEnter job number to manage (or 0 to go back): ").strip()
                if job_choice.isdigit() and 1 <= int(job_choice) <= len(entries):
                    selected_entry = entries[int(job_choice) - 1]
                    page_id = selected_entry.get("id")
                    
                    # Extract job details from the selected entry
                    props = selected_entry.get("properties", {})
                    selected_job = {
                        "notion_page_id": page_id,
                        "job_title": "",
                        "company": "",
                        "job_url": "",
                        "job_id": ""
                    }
                    
                    # Extract job title
                    if "Job Title" in props and props["Job Title"].get("title"):
                        title_items = props["Job Title"]["title"]
                        if title_items and "text" in title_items[0]:
                            selected_job["job_title"] = title_items[0]["text"].get("content", "")
                    
                    # Extract company
                    if "Company" in props and props["Company"].get("rich_text"):
                        company_items = props["Company"]["rich_text"]
                        if company_items and "text" in company_items[0]:
                            selected_job["company"] = company_items[0]["text"].get("content", "")
                    
                    # Extract job URL
                    if "Job URL" in props and props["Job URL"].get("url"):
                        selected_job["job_url"] = props["Job URL"].get("url", "")
                    
                    # Extract job ID
                    if "Job ID" in props and props["Job ID"].get("rich_text"):
                        id_items = props["Job ID"]["rich_text"]
                        if id_items and "text" in id_items[0]:
                            selected_job["job_id"] = id_items[0]["text"].get("content", "")
                    
                    # Set as current job and manage referrals
                    current_job = selected_job
                    scraper.manage_referrals(current_job)
                
            except Exception as e:
                print(f"\nError fetching jobs: {str(e)}")
        
        elif choice == "4":
            print("\n=== Notion Configuration ===")
            api_key = input("Enter your Notion API key: ").strip()
            
            if api_key:
                print("\nChoose an option:")
                print("1. Create a new database in an existing page")
                print("2. Use an existing database")
                
                notion_choice = input("\nSelect an option (1-2): ").strip()
                
                if notion_choice == "1":
                    page_id = input("Enter the Notion page ID where the database should be created: ").strip()
                    
                    if page_id:
                        try:
                            notion_client = NotionClient(api_key, page_id=page_id)
                            scraper.notion_client = notion_client
                            
                            # Save to environment variables for this session
                            os.environ["NOTION_API_KEY"] = api_key
                            os.environ["NOTION_PAGE_ID"] = page_id
                            os.environ["NOTION_DATABASE_ID"] = notion_client.database_id
                            
                            print("\n✅ Notion database created successfully!")
                            print(f"   Database ID: {notion_client.database_id}")
                            print("   This ID has been saved for future use.")
                        except Exception as e:
                            print(f"\n❌ Error creating Notion database: {str(e)}")
                    else:
                        print("\n❌ Page ID is required to create a new database.")
                
                elif notion_choice == "2":
                    database_id = input("Enter your Notion database ID: ").strip()
                    
                    if database_id:
                        try:
                            notion_client = NotionClient(api_key, database_id=database_id)
                            scraper.notion_client = notion_client
                            
                            # Save to environment variables for this session
                            os.environ["NOTION_API_KEY"] = api_key
                            os.environ["NOTION_DATABASE_ID"] = database_id
                            
                            print("\n✅ Notion integration configured successfully!")
                        except Exception as e:
                            print(f"\n❌ Error configuring Notion: {str(e)}")
                    else:
                        print("\n❌ Database ID is required for existing database integration.")
                else:
                    print("\n❌ Invalid option selected.")
            else:
                print("\n❌ API key is required for Notion integration.")
        
        else:
            print("Invalid option. Please select 1-5.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")