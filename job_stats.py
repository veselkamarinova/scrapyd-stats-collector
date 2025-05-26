import requests
import re
import json
import datetime


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
        # If there are no matches, the job was interrupted. Skip it.
        if not matches:
            return None
        # Remove curly braces and match key-value pairs
        dict_string = matches[0].strip("{}")
        pattern = re.compile(
            r"('.*?': .*?datetime\.datetime\(\d{4}, \d{1,2}, \d{1,2}, \d{1,2}, \d{1,2}, \d{1,2}, \d{1,6}\)|'.*?': '.*?'|'.*?': \d+|'.*?': \d+\.\d+)"
        )
        matches = pattern.findall(dict_string)

        # Initialize an empty dictionary
        result_dict = {}

        # Process each key-value pair
        for match in matches:
            key, value = match.split(": ", 1)
            # Convert key to string and value to appropriate type
            key = key.strip("'")
            if "datetime.datetime" in value:
                value = eval(value)
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "", 1).isdigit():
                value = float(value)
            else:
                value = value.strip("'")
            result_dict[key] = value

        scraped_count = (
            result_dict["item_scraped_count"]
            if "item_scraped_count" in result_dict
            else 0
        )
        dropped_count = (
            result_dict["item_dropped_count"]
            if "item_dropped_count" in result_dict
            else 0
        )
        warning_count = (
            result_dict["log_count/WARNING"]
            if "log_count/WARNING" in result_dict
            else 0
        )
        error_count = (
            result_dict["log_count/ERROR"] if "log_count/ERROR" in result_dict else 0
        )
        max_mem = result_dict["memusage/max"]
        status = result_dict["finish_reason"]

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
