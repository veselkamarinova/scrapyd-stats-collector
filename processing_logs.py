import os
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from job_stats import JobStats

load_dotenv()
# Read values from environment variables
USERNAME = os.getenv("SCRAPYD_USERNAME")
PASSWORD = os.getenv("SCRAPYD_PASSWORD")
BASE_URL = os.getenv("SCRAPYD_URL")


basic = HTTPBasicAuth(USERNAME, PASSWORD)
url = BASE_URL + "/listjobs.json"
response = requests.get(url, auth=basic)

if response.status_code == 200:
    data = response.json()
    logs = []
    if "finished" in data and len(data["finished"]) > 0:
        for job in data["finished"]:
            log_url_info = job.get("log_url")
            if log_url_info:
                log_url = BASE_URL + log_url_info
                log_response = requests.get(log_url, auth=basic)
                if log_response.status_code == 200:
                    log_content = log_response.text
                    job_stats = JobStats.create_from_logfile(
                        job_id=job.get("id"),
                        spider=job.get("spider"),
                        start_time=job.get("start_time"),
                        end_time=job.get("end_time"),
                        log_content=log_content,
                    )
                    logs.append(job_stats)
