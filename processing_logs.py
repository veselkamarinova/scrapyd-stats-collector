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
if not db_handler.prepare_table():
    db_handler.close()
    sys.exit(1)


# Read values from environment variables
USERNAME = os.getenv("SCRAPYD_USERNAME")
PASSWORD = os.getenv("SCRAPYD_PASSWORD")
BASE_URL = os.getenv("SCRAPYD_URL")

# Seconds to wait for a connection and for a response from scrapyd.
REQUEST_TIMEOUT = (10, 60)


basic = HTTPBasicAuth(USERNAME, PASSWORD)
url = BASE_URL + "/listjobs.json"
failures = 0
try:
    response = requests.get(url, auth=basic, timeout=REQUEST_TIMEOUT)
except requests.RequestException as e:
    print(f"Failed fetching {url}: {e}", file=sys.stderr)
    failures += 1
    response = None

if response is None:
    pass
elif response.status_code == 200:
    data = response.json()
    if "finished" in data and len(data["finished"]) > 0:
        # scrapyd keeps only the last finished_to_keep finished jobs and, with
        # the default MemoryJobStorage, empties the list when it restarts.
        # When the table has rows but the oldest listed job is not stored,
        # jobs that finished before it may have dropped out of the list since
        # the last run. Check before the loop, which stores that job. scrapyd
        # gives end_time as the str() of a naive local datetime,
        # "YYYY-MM-DD HH:MM:SS[.ffffff]", which sorts by local wall-clock
        # time: out of order during the hour the clocks go back.
        oldest_job = min(data["finished"], key=lambda job: job.get("end_time"))
        try:
            if db_handler.has_rows() and not db_handler.has_id(oldest_job.get("id")):
                print(
                    f"Oldest finished job ID {oldest_job.get('id')} (end time "
                    f"{oldest_job.get('end_time')}) is not stored: jobs that "
                    "finished before it may have been lost.",
                    file=sys.stderr,
                )
                failures += 1
        except mysql.connector.Error:
            failures += 1
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
                try:
                    log_response = requests.get(
                        log_url, auth=basic, timeout=REQUEST_TIMEOUT
                    )
                except requests.RequestException as e:
                    print(
                        f"Failed fetching log for job ID {job.get('id')} from {log_url}: {e}",
                        file=sys.stderr,
                    )
                    failures += 1
                    continue
                if log_response.status_code == 200:
                    log_content = log_response.text
                    job_stats = JobStats.create_from_logfile(
                        job_id=job.get("id"),
                        project=job.get("project"),
                        spider=job.get("spider"),
                        start_time=job.get("start_time"),
                        end_time=job.get("end_time"),
                        log_content=log_content,
                    )
                    try:
                        if not db_handler.insert_job_stats(job_stats):
                            failures += 1
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
                # scrapyd gives a null log_url when logs_dir is disabled or
                # the log file does not exist: it keeps the logs of only the
                # last jobs_to_keep jobs of a spider. Store the job from the
                # listjobs.json fields with the stats unknown, and count a
                # failure, since its stats are lost. The next run finds the
                # row and skips the job.
                print(
                    f"Log of job ID {job.get('id')} was not available: "
                    "storing the job without stats.",
                    file=sys.stderr,
                )
                failures += 1
                job_stats = JobStats.create_without_stats(
                    job_id=job.get("id"),
                    project=job.get("project"),
                    spider=job.get("spider"),
                    start_time=job.get("start_time"),
                    end_time=job.get("end_time"),
                    scraped_count=None,
                )
                try:
                    if not db_handler.insert_job_stats(job_stats):
                        failures += 1
                except mysql.connector.Error:
                    failures += 1
else:
    print(f"Failed fetching {url}: HTTP {response.status_code}", file=sys.stderr)
    failures += 1
db_handler.close()

if failures:
    print(f"{failures} failure(s) during collection.", file=sys.stderr)
    sys.exit(1)
