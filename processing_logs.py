import os
import sys
import mysql.connector
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from job_stats import JobStats
from database_handler import DatabaseHandler

load_dotenv()

db_handler = DatabaseHandler()
db_handler.connect()
db_handler.create_table("job_stats")


# Read values from environment variables
USERNAME = os.getenv("SCRAPYD_USERNAME")
PASSWORD = os.getenv("SCRAPYD_PASSWORD")
BASE_URL = os.getenv("SCRAPYD_URL")


basic = HTTPBasicAuth(USERNAME, PASSWORD)
url = BASE_URL + "/listjobs.json"
response = requests.get(url, auth=basic)
failures = 0

if response.status_code == 200:
    data = response.json()
    if "finished" in data and len(data["finished"]) > 0:
        for job in data["finished"]:
            try:
                if db_handler.has_id(job.get("id")):
                    continue
            except mysql.connector.Error:
                failures += 1
                continue
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
                    if job_stats:
                        try:
                            db_handler.insert_job_stats(job_stats)
                        except mysql.connector.Error:
                            failures += 1
                else:
                    print(
                        f"Failed fetching log for job ID {job.get('id')} from {log_url}: "
                        f"HTTP {log_response.status_code}",
                        file=sys.stderr,
                    )
                    failures += 1
else:
    print(f"Failed fetching {url}: HTTP {response.status_code}", file=sys.stderr)
    failures += 1
db_handler.close()

if failures:
    print(f"{failures} failure(s) during collection.", file=sys.stderr)
    sys.exit(1)
