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

# LangChain components
from langchain_google_genai import GoogleGenerativeAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import StructuredOutputParser, ResponseSchema

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedJobScraper:
    def __init__(self, gemini_api_key: str):
        self.setup_chrome_options()
        self.setup_llm(gemini_api_key)
        self.setup_output_parsers()
        
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
            model="gemini-pro",
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
                logger.info(f"Successfully extracted job description ({len(job_description)} characters)")
                
                return job_description
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Error scraping website: {str(e)}")
            raise ValueError(f"Failed to extract job content: {str(e)}")
    
    def analyze_job_description(self, text: str) -> Dict:
        """Analyze job description text"""
        try:
            prompt = PromptTemplate(
                template="""Analyze this job description and extract key information in EXACTLY this format:

                Job Description:
                {text}

                STRICT OUTPUT FORMAT (Return ONLY this JSON object):
                {{
                    "technical_skills": ["skill1", "skill2"],
                    "soft_skills": ["skill1", "skill2"],
                    "missing_keywords": [],
                    "existing_keywords": [],
                    "keyword_ranking": [["keyword1", 9], ["keyword2", 8]],
                    "required_experience": "X years",
                    "education_requirements": ["requirement1", "requirement2"],
                    "suggested_modifications": {{
                        "section_name": {{
                            "content": "LaTeX formatted content",
                            "location": "start|end"
                        }}
                    }}
                }}

                STRICT RULES:
                1. Return ONLY the JSON object, no other text
                2. ALL keys must be present in the response
                3. technical_skills: List of technical skills mentioned
                4. soft_skills: List of soft skills and competencies
                5. keyword_ranking: List of [keyword, importance_score] pairs, score from 1-10
                6. missing_keywords and existing_keywords must be arrays (can be empty)
                7. suggested_modifications must be a dictionary (can be empty)
                8. Do not include any explanatory text or markdown
                """,
                input_variables=["text"]
            )

            chain = LLMChain(llm=self.llm, prompt=prompt)
            result = chain.invoke({"text": text})
            
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
                "technical_skills",
                "soft_skills",
                "missing_keywords",
                "existing_keywords",
                "keyword_ranking",
                "required_experience",
                "education_requirements",
                "suggested_modifications"
            }
            
            # Initialize default structure
            default_structure = {
                "technical_skills": [],
                "soft_skills": [],
                "missing_keywords": [],
                "existing_keywords": [],
                "keyword_ranking": [],
                "required_experience": "Not specified",
                "education_requirements": [],
                "suggested_modifications": {}
            }
            
            # Merge response with default structure
            for key in required_keys:
                if key not in response:
                    response[key] = default_structure[key]
                    logger.warning(f"Missing key '{key}' in response, using default value")
            
            # Validate types
            list_keys = ["technical_skills", "soft_skills", "missing_keywords", 
                        "existing_keywords", "education_requirements"]
            for key in list_keys:
                if not isinstance(response[key], list):
                    response[key] = list(response[key]) if response[key] else []
            
            if not isinstance(response["keyword_ranking"], list):
                response["keyword_ranking"] = []
            
            if not isinstance(response["suggested_modifications"], dict):
                response["suggested_modifications"] = {}
            
            return response

        except Exception as e:
            logger.error(f"Error analyzing job description: {str(e)}")
            logger.error(f"Raw response: {result['text'] if 'result' in locals() else 'No response'}")
            # Return default structure on error
            return {
                "technical_skills": [],
                "soft_skills": [],
                "missing_keywords": [],
                "existing_keywords": [],
                "keyword_ranking": [],
                "required_experience": "Not specified",
                "education_requirements": [],
                "suggested_modifications": {}
            }

def main():
    GEMINI_API_KEY = "AIzaSyCkb4a_yq_Iviefm_FJHQr40ukm7BqlLww"
    
    while True:
        print("\n=== Job Description Analyzer ===")
        print("1. Enter job URL")
        print("2. Exit")
        
        choice = input("\nSelect an option (1-2): ").strip()
        
        if choice == "2":
            print("Goodbye!")
            break
        elif choice == "1":
            url = input("\nEnter job posting URL: ").strip()
            if not url.startswith(('http://', 'https://')):
                print("Invalid URL format. Please include http:// or https://")
                continue
            
            print("\nScraping job description... Please wait...")
            try:
                scraper = EnhancedJobScraper(GEMINI_API_KEY)
                content = scraper.scrape_website(url)
                
                if not content:
                    print("Failed to extract content from the URL")
                    continue
                
                print("\nAnalyzing job description...")
                analysis = scraper.analyze_job_description(content)
                
                print("\n" + "="*50)
                print("           ATS Optimization Report")
                print("="*50)
                
                print("\n📚 Technical Skills Required:")
                if analysis.get('technical_skills'):
                    for skill in analysis['technical_skills']:
                        print(f"  • {skill}")
                else:
                    print("  No specific technical skills mentioned")
                
                print("\n🤝 Soft Skills Required:")
                if analysis.get('soft_skills'):
                    for skill in analysis['soft_skills']:
                        print(f"  • {skill}")
                else:
                    print("  No specific soft skills mentioned")
                
                print("\n📜 Education Requirements:")
                if analysis.get('education_requirements'):
                    for edu in analysis['education_requirements']:
                        print(f"  • {edu}")
                else:
                    print("  No specific education requirements mentioned")
                
                print("\n⏳ Experience Required:")
                print(f"  {analysis.get('required_experience', 'Not specified')}")
                
                print("\n🎯 Top Keywords by Importance:")
                if analysis.get('keyword_ranking'):
                    for keyword, score in analysis['keyword_ranking'][:10]:  # Show top 10
                        print(f"  • {keyword}: {score}/10")
                else:
                    print("  No keyword rankings available")
                
                print("\n❌ Missing Keywords:")
                if analysis.get('missing_keywords'):
                    for keyword in analysis['missing_keywords']:
                        print(f"  • {keyword}")
                else:
                    print("  No missing keywords identified")
                
                print("\n✅ Existing Keywords:")
                if analysis.get('existing_keywords'):
                    for keyword in analysis['existing_keywords']:
                        print(f"  • {keyword}")
                else:
                    print("  No existing keywords identified")
                
                print("\nWould you like to analyze another job posting?")
                
            except Exception as e:
                print(f"\nError occurred: {str(e)}")
                print("Please try again with a different URL")
        else:
            print("Invalid option. Please select 1 or 2.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {str(e)}")