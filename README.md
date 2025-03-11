# Job Tracker Application

A Streamlit application for tracking job applications, analyzing job descriptions, and managing your job search process.

## Features

- Scrape job descriptions from URLs
- Analyze job descriptions to extract key information
- Track job applications in Notion
- Generate connection messages for LinkedIn
- Search for company employees on LinkedIn
- Option to use default credentials with password protection

## Default Credentials

The application includes an option to use default credentials for quick setup:

1. Check the "Use Default Credentials" option in the sidebar
2. Enter the password when prompted
3. The application will automatically configure the Gemini API and Notion integration

This is useful for demonstration purposes or for users who don't have their own API keys.

## Deployment on Streamlit Cloud

This application is configured to run on Streamlit Cloud. To deploy:

1. Fork this repository to your GitHub account
2. Connect your GitHub account to Streamlit Cloud
3. Create a new app in Streamlit Cloud and select this repository
4. Set the following secrets in the Streamlit Cloud dashboard:
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `NOTION_TOKEN`: Your Notion API token
   - `NOTION_DATABASE_ID`: Your Notion database ID (optional)

## Local Development

To run the application locally:

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   streamlit run Job_agent.py
   ```

## Environment Variables

The following environment variables can be set:

- `GEMINI_API_KEY`: Your Google Gemini API key
- `NOTION_TOKEN`: Your Notion API token
- `NOTION_DATABASE_ID`: Your Notion database ID
- `CHROMEDRIVER_PATH`: Custom path to chromedriver (optional)

## Troubleshooting

If you encounter issues with Selenium or Chrome WebDriver:

1. The application includes a fallback mechanism to use requests instead of Selenium
2. Make sure Chrome and ChromeDriver are installed on your system
3. Check the logs for specific error messages

## License

MIT 