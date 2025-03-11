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
from typing import Dict, List, Tuple
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import os
from datetime import datetime
import requests

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
        
        # Database schema for job tracking
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
                "Referral": {
                    "select": {
                        "options": [
                            {"name": "Yes", "color": "green"},
                            {"name": "No", "color": "red"}
                        ]
                    }
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
            "Referral": {
                "select": {
                    "name": "No"
                }
            }
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
            
            # Add full job description
            children.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
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

class EnhancedJobScraper:
    def __init__(self, gemini_api_key: str, notion_client=None):
        self.setup_chrome_options()
        self.setup_llm(gemini_api_key)
        self.setup_output_parsers()
        self.notion_client = notion_client
        
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
        
    def scrape_website(self, url: str) -> str:
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
                    "location": ""
                }
                
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
                "job_description": job_data.get("job_description", "")
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
    
    while True:
        print("\n=== Job Tracker ===")
        print("1. Process job URL")
        print("2. Configure Notion integration")
        print("3. Exit")
        
        choice = input("\nSelect an option (1-3): ").strip()
        
        if choice == "3":
            print("Goodbye!")
            break
        elif choice == "1":
            url = input("\nEnter job posting URL: ").strip()
            if not url.startswith(('http://', 'https://')):
                print("Invalid URL format. Please include http:// or https://")
                continue
            
            print("\nProcessing job posting... Please wait...")
            try:
                job_data = scraper.process_job_url(url)
                
                print("\n" + "="*50)
                print("           Job Details")
                print("="*50)
                
                print(f"\n📋 Job Title: {job_data['job_title']}")
                print(f"🏢 Company: {job_data['company']}")
                print(f"📍 Location: {job_data['location']}")
                print(f"💰 Salary: {job_data['salary']}")
                print(f"⏱️ Job Type: {job_data['job_type']}")
                print(f"🏭 Industry: {job_data['industry']}")
                
                print("\n📚 Technical Skills Required:")
                if job_data.get('technical_skills'):
                    for skill in job_data['technical_skills']:
                        print(f"  • {skill}")
                else:
                    print("  No specific technical skills mentioned")
                
                print("\n🤝 Soft Skills Required:")
                if job_data.get('soft_skills'):
                    for skill in job_data['soft_skills']:
                        print(f"  • {skill}")
                else:
                    print("  No specific soft skills mentioned")
                
                print("\n📜 Education Requirements:")
                if job_data.get('education_requirements'):
                    for edu in job_data['education_requirements']:
                        print(f"  • {edu}")
                else:
                    print("  No specific education requirements mentioned")
                
                print("\n⏳ Experience Required:")
                print(f"  {job_data.get('required_experience', 'Not specified')}")
                
                print("\n🔑 Key Responsibilities:")
                if job_data.get('key_responsibilities'):
                    for resp in job_data['key_responsibilities']:
                        print(f"  • {resp}")
                else:
                    print("  No specific responsibilities mentioned")
                
                print("\n🎁 Benefits:")
                if job_data.get('benefits'):
                    for benefit in job_data['benefits']:
                        print(f"  • {benefit}")
                else:
                    print("  No specific benefits mentioned")
                
                if notion_client and notion_client.database_id:
                    print("\n✅ Job added to Notion database!")
                    print(f"   Database ID: {notion_client.database_id}")
                    print(f"   Page ID: {job_data.get('notion_page_id', 'Unknown')}")
                
                print("\nWould you like to process another job posting?")
                
            except Exception as e:
                print(f"\nError occurred: {str(e)}")
                print("Please try again with a different URL")
        
        elif choice == "2":
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
            print("Invalid option. Please select 1, 2, or 3.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")