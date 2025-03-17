import requests
import re
import json


class JobStats:
    def __init__(
        self,
        job_id,
        spider,
        start_time,
        end_time,
        scraped_count,
        dropped_count,
        warning_count,
        error_count,
        max_mem,
        status,
    ):
        self.job_id = job_id
        self.spider = spider
        self.start_time = start_time
        self.end_time = end_time
        self.scraped_count = scraped_count
        self.dropped_count = dropped_count
        self.warning_count = warning_count
        self.error_count = error_count
        self.max_mem = max_mem
        self.status = status

    @staticmethod
    def create_from_logfile(job_id, spider, start_time, end_time, log_content):

        # Example regex to extract some information from the log content
        regex_pattern = r"\[scrapy\.statscollectors].*\n({.*})"
        matches = re.findall(regex_pattern, log_content, re.DOTALL | re.MULTILINE)
        # Example JSON processing
        json_data = json.loads(matches[0])
        # Process the extracted data as needed
        print(f"Log content for job {id}: {log_content}")
        return JobStats(
            job_id,
            spider,
            start_time,
            end_time,
            scraped_count,
            dropped_count,
            warning_count,
            error_count,
            max_mem,
            status,
        )

    def __str__(self):
        return f"Job ID: {self.id}, Spider: {self.spider}, Start Time: {self.start_time}, End Time: {self.end_time}, Log URL: {self.log_url}"
