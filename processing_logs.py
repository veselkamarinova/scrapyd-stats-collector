import os
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()
# Read values from environment variables
USERNAME = os.getenv("SCRAPYD_USERNAME")
PASSWORD = os.getenv("SCRAPYD_PASSWORD")
BASE_URL = os.getenv("SCRAPYD_URL")


basic = HTTPBasicAuth(USERNAME, PASSWORD)
url = BASE_URL + "/listjobs.json"
response = requests.get(url, auth=basic)


