import datetime
import json
import mysql.connector
import os
import sys
from mysql.connector import errorcode

TABLE_NAME = "job_stats"


def serialize_datetime(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


class DatabaseHandler:
    def __init__(self):
        self.config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "host": os.getenv("DB_HOST"),
            "port": int(os.getenv("DB_PORT")),
            "database": os.getenv("DB_NAME"),
        }
        self.cnx = None
        self.cursor = None

    def connect(self):
        try:
            config = self.config.copy()
            self.cnx = mysql.connector.connect(**config)
            self.cursor = self.cnx.cursor()
            print("Connected to the database successfully.")
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                raise Exception("Something is wrong with your user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                raise Exception("Database does not exist")
            else:
                raise Exception(err)

    def table_exists(self, table_name):
        if self.cursor:
            try:
                self.cursor.execute("SHOW TABLES LIKE %s", (table_name,))
                result = self.cursor.fetchone()
                return result is not None
            except mysql.connector.Error as err:
                print(f"Failed checking table existence: {err}")
                return False
        else:
            print("No database connection.")
            return False

    def create_table(self):
        if not self.table_exists(TABLE_NAME):
            create_table_query = (
                f"CREATE TABLE {TABLE_NAME} ("
                "    job_id CHAR(32),"
                "    project VARCHAR(255),"
                "    spider VARCHAR(255),"
                "    start_time DATETIME,"
                "    end_time DATETIME,"
                "    number_scraped INT UNSIGNED,"
                "    dropped INT UNSIGNED,"
                "    warnings INT UNSIGNED,"
                "    errors INT UNSIGNED,"
                "    max_mem BIGINT,"
                "    finish_reason VARCHAR(255),"
                "    responses INT UNSIGNED,"
                "    retries INT UNSIGNED,"
                "    status_403 INT UNSIGNED,"
                "    status_429 INT UNSIGNED,"
                "    criticals INT UNSIGNED,"
                "    stats JSON,"
                "    PRIMARY KEY (job_id),"
                "    INDEX project_spider_end_time (project, spider, end_time)"
                ");"
            )
            if self.cursor:
                try:
                    self.cursor.execute(create_table_query)
                    print("Table created successfully.")
                except mysql.connector.Error as err:
                    print(f"Failed creating table: {err}")
                    raise
            else:
                print("No database connection.")
                raise Exception("No database connection.")
        else:
            print(f"Table {TABLE_NAME} already exists.")

    def has_id(self, job_id):
        if self.cursor:
            try:
                self.cursor.execute(
                    f"SELECT job_id FROM {TABLE_NAME} WHERE job_id = %s", (job_id,)
                )
                result = self.cursor.fetchone()
                return result is not None
            except mysql.connector.Error as err:
                print(f"Failed checking job ID {job_id}: {err}", file=sys.stderr)
                raise
        else:
            print("No database connection.")
            return False

    def has_rows(self):
        if self.cursor:
            try:
                self.cursor.execute(f"SELECT 1 FROM {TABLE_NAME} LIMIT 1")
                result = self.cursor.fetchone()
                return result is not None
            except mysql.connector.Error as err:
                print(
                    f"Failed checking whether {TABLE_NAME} has rows: {err}",
                    file=sys.stderr,
                )
                raise
        else:
            print("No database connection.")
            return False

    def insert_data(self, insert_query, data):
        if self.cursor:
            try:
                self.cursor.execute(insert_query, data)
                self.cnx.commit()
                print(f"Stored data for spider %s on %s" % (data[2], data[3]))
            except mysql.connector.Error as err:
                if err.errno == errorcode.ER_DUP_ENTRY:
                    print(f"Job ID {data[0]} is already stored.")
                    return
                print(
                    f"Failed inserting data for job ID {data[0]}: {err}",
                    file=sys.stderr,
                )
                raise
        else:
            print("No database connection.")

    def insert_job_stats(self, job_stats):
        insert_query = (
            f"INSERT INTO {TABLE_NAME} "
            "(job_id, project, spider, start_time, end_time, number_scraped, dropped, warnings, errors, max_mem, finish_reason, "
            "responses, retries, status_403, status_429, criticals, stats) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
        )
        # A job without a stats dump or without a log is stored with stats
        # NULL, not the JSON value null.
        stats = None
        serialized = True
        if job_stats.stats is not None:
            try:
                stats = json.dumps(
                    job_stats.stats, default=serialize_datetime, allow_nan=False
                )
            except (TypeError, ValueError) as err:
                # The parser keeps values that JSON cannot hold, such as sets,
                # bytes, infinite floats and tuple keys of nested dicts. Store
                # the job without its stats rather than stop the run, and
                # report the failure to the caller.
                print(
                    f"Failed serializing stats for job ID {job_stats.job_id}: {err}",
                    file=sys.stderr,
                )
                serialized = False
        data = (
            job_stats.job_id,
            job_stats.project,
            job_stats.spider,
            job_stats.start_time,
            job_stats.end_time,
            job_stats.scraped_count,
            job_stats.dropped_count,
            job_stats.warning_count,
            job_stats.error_count,
            job_stats.max_mem,
            job_stats.status,
            job_stats.response_count,
            job_stats.retry_count,
            job_stats.status_403_count,
            job_stats.status_429_count,
            job_stats.critical_count,
            stats,
        )
        self.insert_data(insert_query, data)
        return serialized

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.cnx:
            self.cnx.close()
        print("Database connection closed.")
