import mysql.connector
import os
import sys
from mysql.connector import errorcode

TABLE_NAME = "job_stats"


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
                "    spider VARCHAR(255),"
                "    start_time DATETIME,"
                "    end_time DATETIME,"
                "    number_scraped INT UNSIGNED,"
                "    dropped INT UNSIGNED,"
                "    warnings INT UNSIGNED,"
                "    errors INT UNSIGNED,"
                "    max_mem BIGINT,"
                "    finish_reason VARCHAR(255)"
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

    def insert_data(self, insert_query, data):
        if self.cursor:
            try:
                self.cursor.execute(insert_query, data)
                self.cnx.commit()
                print(f"Stored data for spider %s on %s" % (data[1], data[2]))
            except mysql.connector.Error as err:
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
            "(job_id, spider, start_time, end_time, number_scraped, dropped, warnings, errors, max_mem, finish_reason) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
        )
        data = (
            job_stats.job_id,
            job_stats.spider,
            job_stats.start_time,
            job_stats.end_time,
            job_stats.scraped_count,
            job_stats.dropped_count,
            job_stats.warning_count,
            job_stats.error_count,
            job_stats.max_mem,
            job_stats.status,
        )
        self.insert_data(insert_query, data)

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.cnx:
            self.cnx.close()
        print("Database connection closed.")
