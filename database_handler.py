import datetime
import json
import mysql.connector
import os
import re
import sys
from mysql.connector import errorcode

TABLE_NAME = "job_stats"
VERSION_TABLE_NAME = "schema_version"

COUNT_COLUMNS = ("number_scraped", "dropped", "warnings", "errors")

# Schema version 0 of job_stats, the table created before #5: the columns in
# order, with their types, and the indexes by name, with their columns.
FIRST_SCHEMA = (
    [
        ("job_id", "CHAR(32)"),
        ("spider", "VARCHAR(255)"),
        ("start_time", "DATETIME"),
        ("end_time", "DATETIME"),
        ("number_scraped", "SMALLINT"),
        ("dropped", "SMALLINT"),
        ("warnings", "SMALLINT"),
        ("errors", "SMALLINT"),
        ("max_mem", "BIGINT"),
        ("finish_reason", "VARCHAR(255)"),
    ],
    {},
)

# The steps that bring job_stats from one schema version to the next, in
# order: step n brings version n - 1 to version n. A step is a list of
# changes: ("MODIFY", column, type), ("ADD COLUMN", column, type, the column
# it follows or None for the end), ("ADD INDEX", name, columns) and
# ("DROP INDEX", name), where the index PRIMARY is the primary key. The
# changes of a step run as one ALTER TABLE statement, which MariaDB and MySQL
# apply completely or not at all.
MIGRATIONS = [
    # The job counts as unsigned integers (#5).
    [("MODIFY", name, "INT UNSIGNED") for name in COUNT_COLUMNS],
    # The primary key and the index on spider and end time (#22).
    [
        ("ADD INDEX", "PRIMARY", ("job_id",)),
        ("ADD INDEX", "spider_end_time", ("spider", "end_time")),
    ],
    # The project, the counters and the stats dump, and the index on project,
    # spider and end time instead of the one on spider and end time (#24).
    [
        ("DROP INDEX", "spider_end_time"),
        ("ADD COLUMN", "project", "VARCHAR(255)", "job_id"),
        ("ADD COLUMN", "responses", "INT UNSIGNED", None),
        ("ADD COLUMN", "retries", "INT UNSIGNED", None),
        ("ADD COLUMN", "status_403", "INT UNSIGNED", None),
        ("ADD COLUMN", "status_429", "INT UNSIGNED", None),
        ("ADD COLUMN", "criticals", "INT UNSIGNED", None),
        ("ADD COLUMN", "stats", "JSON", None),
        ("ADD INDEX", "project_spider_end_time", ("project", "spider", "end_time")),
    ],
]
SCHEMA_VERSION = len(MIGRATIONS)


def index_definition(name, columns):
    if name == "PRIMARY":
        return f"PRIMARY KEY ({', '.join(columns)})"
    return f"INDEX {name} ({', '.join(columns)})"


def apply_step(schema, changes):
    # The schema that the changes of a step give, and the ALTER TABLE
    # statement that makes them, from one list, so that the two cannot
    # differ.
    columns, indexes = list(schema[0]), dict(schema[1])
    clauses = []
    for change in changes:
        if change[0] == "MODIFY":
            _, name, column_type = change
            columns = [(n, column_type if n == name else t) for n, t in columns]
            clauses.append(f"MODIFY {name} {column_type}")
        elif change[0] == "ADD COLUMN":
            _, name, column_type, after = change
            if after is None:
                columns.append((name, column_type))
                clauses.append(f"ADD COLUMN {name} {column_type}")
            else:
                position = [n for n, _ in columns].index(after) + 1
                columns.insert(position, (name, column_type))
                clauses.append(f"ADD COLUMN {name} {column_type} AFTER {after}")
        elif change[0] == "ADD INDEX":
            _, name, index_columns = change
            indexes[name] = index_columns
            clauses.append(f"ADD {index_definition(name, index_columns)}")
        elif change[0] == "DROP INDEX":
            _, name = change
            del indexes[name]
            clauses.append(f"DROP INDEX {name}")
    return (columns, indexes), f"ALTER TABLE {TABLE_NAME} " + ", ".join(clauses)


# SCHEMAS[n] is the schema of version n, ALTER_STATEMENTS[n - 1] the
# statement of step n. create_table() creates the table at the latest schema.
SCHEMAS = [FIRST_SCHEMA]
ALTER_STATEMENTS = []
for changes in MIGRATIONS:
    schema, statement = apply_step(SCHEMAS[-1], changes)
    SCHEMAS.append(schema)
    ALTER_STATEMENTS.append(statement)


def normalize_type(column_type):
    # The same text for a type as declared and as INFORMATION_SCHEMA shows
    # it on MariaDB and on MySQL 8. MariaDB shows the display width of
    # integer types (int(10) unsigned, bigint(20)), MySQL 8 does not (int
    # unsigned, bigint). MariaDB stores JSON as LONGTEXT with a JSON_VALID
    # check, MySQL as json.
    column_type = re.sub(
        r"^(tinyint|smallint|mediumint|int|bigint)\(\d+\)", r"\1", column_type.lower()
    )
    return "json" if column_type == "longtext" else column_type


def schema_differences(schema, columns, indexes):
    # How a table with the given columns (name to type, as the server shows
    # it) and indexes (name to columns) differs from a schema; empty when it
    # has exactly the columns, types and indexes of the schema. Types are
    # normalized only to compare them; the messages show them as declared
    # and as the server shows them.
    expected_columns = dict(schema[0])
    expected_indexes = schema[1]
    differences = []
    for name, column_type in expected_columns.items():
        if name not in columns:
            differences.append(f"missing column {name} {column_type}")
        elif normalize_type(columns[name]) != normalize_type(column_type):
            differences.append(
                f"column {name} is {columns[name]}, expected {column_type}"
            )
    for name in sorted(columns.keys() - expected_columns.keys()):
        differences.append(f"extra column {name} {columns[name]}")
    for name, index_columns in expected_indexes.items():
        if name not in indexes:
            differences.append(f"missing index {index_definition(name, index_columns)}")
        elif indexes[name] != index_columns:
            differences.append(
                f"index {name} is on ({', '.join(indexes[name])}), "
                f"expected ({', '.join(index_columns)})"
            )
    for name in sorted(indexes.keys() - expected_indexes.keys()):
        differences.append(f"extra index {index_definition(name, indexes[name])}")
    return differences


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

    def prepare_table(self):
        # Creates job_stats at the latest schema, or upgrades it to that
        # schema. Returns False when that fails; the caller stops, since
        # inserts would fail. Every check that stops the run comes before
        # the first statement that changes the database (CREATE TABLE,
        # INSERT into schema_version, ALTER TABLE), on every path, so that a
        # run that stops on a check changes nothing.
        if not self.cursor:
            print("No database connection.")
            raise Exception("No database connection.")
        # The recorded version is read before the table, so that a step of
        # an overlapping run in between leaves the recorded version below
        # the table's, not above it.
        try:
            recorded = self.recorded_version()
        except mysql.connector.Error as err:
            print(f"Failed upgrading table {TABLE_NAME}: {err}", file=sys.stderr)
            return False
        # A later collector recorded a version that this one has no schema
        # for, for example before a rollback to this one. Checked before the
        # table is created, since a table created at this collector's latest
        # schema would be behind the recorded version for the later one.
        if recorded is not None and recorded > SCHEMA_VERSION:
            print(
                f"Failed upgrading table {TABLE_NAME}: schema version "
                f"{recorded} is recorded, which is newer than the latest "
                f"schema version of this collector, {SCHEMA_VERSION}.",
                file=sys.stderr,
            )
            return False
        if not self.table_exists(TABLE_NAME):
            self.create_table()
            return True
        print(f"Table {TABLE_NAME} already exists.")
        return self.upgrade_table(recorded=recorded)

    def create_table(self):
        columns, indexes = SCHEMAS[SCHEMA_VERSION]
        definitions = [f"{name} {column_type}" for name, column_type in columns]
        definitions += [index_definition(n, c) for n, c in indexes.items()]
        create_table_query = f"CREATE TABLE {TABLE_NAME} ({', '.join(definitions)});"
        try:
            self.create_version_table()
            self.cursor.execute(create_table_query)
            self.record_version(SCHEMA_VERSION)
            print("Table created successfully.")
        except mysql.connector.Error as err:
            print(f"Failed creating table: {err}")
            raise

    def create_version_table(self):
        # One row per schema version of job_stats that the collector found
        # or applied; the highest is the current one. Rows are only inserted,
        # so the collector needs no UPDATE or DELETE privilege.
        self.cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {VERSION_TABLE_NAME} ("
            "    version INT UNSIGNED NOT NULL,"
            "    recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "    PRIMARY KEY (version)"
            ");"
        )

    def recorded_version(self):
        # None when no version is recorded, also when schema_version does
        # not exist: prepare_table() creates it only after its checks.
        self.cursor.execute(
            "SELECT COUNT(*) FROM information_schema.TABLES"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            (VERSION_TABLE_NAME,),
        )
        if not self.cursor.fetchone()[0]:
            return None
        self.cursor.execute(f"SELECT MAX(version) FROM {VERSION_TABLE_NAME}")
        return self.cursor.fetchone()[0]

    def record_version(self, version):
        # INSERT IGNORE: an overlapping run may have recorded it already.
        self.cursor.execute(
            f"INSERT IGNORE INTO {VERSION_TABLE_NAME} (version) VALUES (%s)",
            (version,),
        )
        self.cnx.commit()

    def read_schema(self):
        # The columns of job_stats (name to type, as the server shows it) and
        # its indexes (name to columns, in index order) from
        # INFORMATION_SCHEMA.
        self.cursor.execute(
            "SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
            (TABLE_NAME,),
        )
        columns = dict(self.cursor.fetchall())
        self.cursor.execute(
            "SELECT INDEX_NAME, COLUMN_NAME FROM information_schema.STATISTICS"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s"
            " ORDER BY INDEX_NAME, SEQ_IN_INDEX",
            (TABLE_NAME,),
        )
        indexes = {}
        for name, column in self.cursor.fetchall():
            indexes[name] = indexes.get(name, ()) + (column,)
        return columns, indexes

    def find_blocking_rows(self, version):
        # Rows that would make a step after the given version fail, or under
        # a non-strict sql_mode change data. Checked before any step runs, so
        # that such rows stop the run before the table is changed.
        problems = []
        if version < 1:
            self.cursor.execute(
                f"SELECT job_id FROM {TABLE_NAME} WHERE "
                + " OR ".join(f"{name} < 0" for name in COUNT_COLUMNS)
            )
            job_ids = [job_id or "NULL" for (job_id,) in self.cursor.fetchall()]
            if job_ids:
                problems.append(
                    "negative counts, which an unsigned column cannot hold, "
                    f"in job ID(s) {', '.join(job_ids)}"
                )
        if version < 2:
            self.cursor.execute(
                f"SELECT job_id FROM {TABLE_NAME} WHERE job_id IS NOT NULL"
                " GROUP BY job_id HAVING COUNT(*) > 1"
            )
            job_ids = [job_id for (job_id,) in self.cursor.fetchall()]
            if job_ids:
                problems.append(
                    "job ID(s) stored more than once, which the primary key "
                    f"does not allow: {', '.join(job_ids)}"
                )
            self.cursor.execute(
                f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE job_id IS NULL"
            )
            count = self.cursor.fetchone()[0]
            if count:
                problems.append(
                    f"{count} row(s) without a job ID, which the primary key "
                    "does not allow"
                )
        return problems

    def upgrade_table(self, recorded):
        # Brings an existing job_stats to the schema of create_table(), given
        # the version recorded before prepare_table() checked that the table
        # exists. Returns False when that fails.
        try:
            columns, indexes = self.read_schema()
            # The version is the one whose schema the table has exactly, also
            # when a version is recorded, so that a table changed by hand
            # stops the run before anything is recorded or altered.
            differences = [
                schema_differences(schema, columns, indexes) for schema in SCHEMAS
            ]
            if all(differences):
                closest = min(range(len(SCHEMAS)), key=lambda v: len(differences[v]))
                print(
                    f"Failed upgrading table {TABLE_NAME}: its columns and "
                    "indexes match no schema version. The closest is version "
                    f"{closest}, which differs in: {'; '.join(differences[closest])}.",
                    file=sys.stderr,
                )
                return False
            version = differences.index([])
            # Versions are recorded only after their step, so a table behind
            # its recorded version was changed by hand.
            if recorded is not None and recorded > version:
                print(
                    f"Failed upgrading table {TABLE_NAME}: schema version "
                    f"{recorded} is recorded, but its columns and indexes are "
                    f"those of version {version}. It differs from version "
                    f"{recorded} in: {'; '.join(differences[recorded])}.",
                    file=sys.stderr,
                )
                return False
            problems = self.find_blocking_rows(version)
            if problems:
                for problem in problems:
                    print(
                        f"Failed upgrading table {TABLE_NAME}: {problem}.",
                        file=sys.stderr,
                    )
                return False
            # No version is recorded for a table created before the
            # collector recorded versions. A recorded version below the
            # table's is left by a run that stopped, or is running, between a
            # step and its record: MariaDB and MySQL commit an ALTER TABLE at
            # once. The checks above are done, so schema_version may now be
            # created.
            if recorded is None:
                self.create_version_table()
            if recorded != version:
                self.record_version(version)
                print(f"Table {TABLE_NAME} has schema version {version}.")
        except mysql.connector.Error as err:
            print(f"Failed upgrading table {TABLE_NAME}: {err}", file=sys.stderr)
            return False
        for version in range(version + 1, SCHEMA_VERSION + 1):
            statement = ALTER_STATEMENTS[version - 1]
            try:
                self.cursor.execute(statement)
                self.record_version(version)
            except mysql.connector.Error as err:
                print(
                    f"Failed upgrading table {TABLE_NAME} to schema version "
                    f"{version}: {err}",
                    file=sys.stderr,
                )
                return False
            print(f"Upgraded table {TABLE_NAME} to schema version {version}.")
        return True

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
