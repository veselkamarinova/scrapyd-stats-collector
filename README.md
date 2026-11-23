# Job Processing and Logging System

This project is designed to process job logs from a Scrapy server, extract relevant statistics, store them in a MySQL database, and visualize the data in Grafana. Alerts are sent to Telegram.


## Requirements

- Python 3.x
- MySQL server
- `pip` for managing Python packages
- Grafana for data visualization
- Telegram for receiving alerts

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/veselkamarinova/scrapyd-stats-collector.git
    cd scrapyd-stats-collector
    ```
2. Set up a virtual environment (optional but recommended):
    ```sh
    python -m venv .venv
    source .venv/bin/activate  
    ```

3. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

4. Copy the `.env.dist` file to `.env` and update it with your configuration:
    ```sh
    cp .env.dist .env
    ```



### Code style

The project uses the `Black` code style. For instructions how to set it up in
PyCharm, see https://black.readthedocs.io/en/stable/integrations/editors.html#pycharm-intellij-idea

To automatically format the code:

```shell
$ black .
```

#### Ensure your MySQL server is running and accessible with the credentials provided in the `.env` file.

The database user needs the SELECT, INSERT, CREATE, ALTER and INDEX
privileges on the database:

```sql
GRANT SELECT, INSERT, CREATE, ALTER, INDEX ON <database>.* TO '<user>'@'<host>';
```

The collector creates the `job_stats` table on its first run. When the table
was created by an earlier version of the collector, it upgrades the table to
the current schema at the start of the run and records the schema version in
the `schema_version` table. The upgrade stops with exit status 1, without
changing the table, while the table holds rows that the new schema does not
allow: negative counts, a job ID that is stored more than once, or a row
without a job ID; the error message names the job IDs, or the number of
rows without one. It also stops, without changing the table, when the
columns and indexes of the table match no schema version of the collector,
for example after a column or index was added or changed by hand, or match
an earlier version than the one recorded in `schema_version`; the error
message names the version and how the table differs from it. It stops in
the same way when `schema_version` records a later version than the
collector knows, for example after a rollback to an earlier commit of the
collector; this check comes first, so a missing `job_stats` table is not
created then.

The upgrade does not check the storage engine or row format of the table.
On a table with a key length limit lower than InnoDB's default, such as a
MyISAM table or one with `ROW_FORMAT=COMPACT`, the step that adds the
index on spider and end time fails with exit status 1 after the earlier
step was applied and recorded. Convert the table, for example with
`ALTER TABLE job_stats ENGINE=InnoDB ROW_FORMAT=DYNAMIC`, and the next run
continues from the recorded version.

#### Run the `processing_logs.py` script to fetch job logs, process them, and store the statistics in the database:
    ```sh
    python processing_logs.py
    ```

##### Configure Grafana to visualize the data from the MySQL database.

##### Install Grafana

##### Add MySQL Data Source
-  Open Grafana in your web browser (default is http://localhost:3000).
-  Log in with the default credentials (username: `admin`, password: `admin`).
-  Click on the gear icon on the left sidebar to open the Configuration page.
-  Click on `Data Sources` and then `Add data source`.
-  Select `MySQL` from the list of data sources.
-  Enter the MySQL connection details (host, database, user, password).
-  Click `Save & Test` to verify the connection.

##### Create a Dashboard
-  Click on the `+` icon on the left sidebar to create a new dashboard.
-  Add a new panel to the dashboard.
-  Select the data source you created earlier.
-  Write a query to fetch the data you want to visualize.
-  Choose the type of visualization (e.g., Graph, Table).
-  Configure the visualization with the desired query and settings.
-  Click `Save` to save the panel.

##### Set up Grafana alerts to send notifications to Telegram using the provided bot token and chat ID.
-  Click on the bell icon (🔔) in the left sidebar to go to the Alerting menu.
-  Create alert rules. Define the alert conditions. For example, you can set an alert if the number of errors exceeds a certain threshold.
#####  Add a notification channel. Select `Telegram` as the notification channel type.
##### Enter the name, bot token and chat ID.
#####  Click `Send Test` to verify the connection.
