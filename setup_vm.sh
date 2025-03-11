#!/bin/bash

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python and pip
sudo apt-get install -y python3 python3-pip python3-venv

# Install Chrome dependencies
sudo apt-get install -y wget gnupg xvfb libxi6 libgconf-2-4 libxss1 libnss3 libnspr4 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libu2f-udev libvulkan1

# Install Chrome
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable

# Install ChromeDriver
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f 1)
CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION")
wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/bin/chromedriver
sudo chmod +x /usr/bin/chromedriver
rm chromedriver_linux64.zip

# Create a directory for the application
mkdir -p ~/job-tracker
cd ~/job-tracker

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Clone the repository (replace with your repository URL)
git clone https://github.com/yourusername/job-tracker.git .

# Install requirements
pip install -r requirements.txt

# Create a systemd service file for the application
cat << EOF | sudo tee /etc/systemd/system/job-tracker.service
[Unit]
Description=Job Tracker Streamlit App
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=/bin/bash -c "source $(pwd)/venv/bin/activate && Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset & export DISPLAY=:99 && streamlit run $(pwd)/Job_agent.py --server.port=8501 --server.address=0.0.0.0"
Restart=always
Environment="GEMINI_API_KEY=your_gemini_api_key"
Environment="NOTION_API_KEY=your_notion_api_key"
Environment="NOTION_DATABASE_ID=your_notion_database_id"
Environment="NOTION_PAGE_ID=your_notion_page_id"

[Install]
WantedBy=multi-user.target
EOF

# Start and enable the service
sudo systemctl daemon-reload
sudo systemctl start job-tracker
sudo systemctl enable job-tracker

# Set up firewall to allow traffic on port 8501
sudo ufw allow 8501/tcp

echo "Job Tracker application has been deployed and started."
echo "You can access it at http://$(curl -s ifconfig.me):8501" 