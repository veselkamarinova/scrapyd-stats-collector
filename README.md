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
    git clone <repository_url>
    cd <repository_directory>
    ```

2. Install the required Python packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Copy the `.env.dist` file to `.env` and update it with your configuration:
    ```sh
    cp .env.dist .env
    ```

4. Update the `.env` file with your MySQL, Scrapy server, Grafana, and Telegram credentials:
    ```dotenv
    SCRAPYD_USERNAME=my_username
    SCRAPYD_PASSWORD=my_secret_password
    SCRAPYD_URL=https://mysite.com
    DB_USER=my_db_user
    DB_PASSWORD=my_db_password
    DB_HOST=localhost
    DB_PORT=3306
    DB_NAME=my_database
    GRAFANA_URL=http://localhost:3000
    ```

## Obtaining Telegram Bot Token and Chat ID

1. **Create a Telegram Bot**:
    - Open Telegram and search for `@BotFather`.
    - Start a chat with `@BotFather` and use the `/newbot` command to create a new bot.
    - Follow the instructions to set a name and username for your bot.
    - `@BotFather` will provide you with a bot token. This is your `TELEGRAM_BOT_TOKEN`.

2. **Get Your Chat ID**:
    - Start a chat with your bot by searching for its username in Telegram and sending a message.
    - Open the following URL in your browser, replacing `YOUR_BOT_TOKEN` with your actual bot token:
      ```
      https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
      ```
    - Look for the `chat` object in the response. The `id` field in this object is your `TELEGRAM_CHAT_ID`.

## Usage

```shell
# Create a virtual environment and activate it.
$ python -m venv env
$ source env/bin/activate
```

### Code style

The project uses the `Black` code style. For instructions how to set it up in
PyCharm, see https://black.readthedocs.io/en/stable/integrations/editors.html#pycharm-intellij-idea

To automatically format the code:

```shell
$ black .
```

1. Ensure your MySQL server is running and accessible with the credentials provided in the `.env` file.

2. Run the `processing_logs.py` script to fetch job logs, process them, and store the statistics in the database:
    ```sh
    python processing_logs.py
    ```

3. Configure Grafana to visualize the data from the MySQL database.
 3.1. Install Grafana
 3.2. Add MySQL Data Source
  - Open Grafana in your web browser (default is http://localhost:3000).
  - Log in with the default credentials (username: `admin`, password: `admin`).
  - Click on the gear icon on the left sidebar to open the Configuration page.
  - Click on `Data Sources` and then `Add data source`.
  - Select `MySQL` from the list of data sources.
  - Enter the MySQL connection details (host, database, user, password).
  - Click `Save & Test` to verify the connection.
 3.3. Create a Dashboard
  - Click on the `+` icon on the left sidebar to create a new dashboard.
  - Add a new panel to the dashboard.
  - Select the data source you created earlier.
  - Write a query to fetch the data you want to visualize.
  - Choose the type of visualization (e.g., Graph, Table).
  - Configure the visualization with the desired query and settings.
  - Click `Save` to save the panel.

4. Set up Grafana alerts to send notifications to Telegram using the provided bot token and chat ID.
    - Click on the bell icon (🔔) in the left sidebar to go to the Alerting menu.
    - Create alert rules. Define the alert conditions. For example, you can set an alert if the number of errors exceeds a certain threshold.
    - Add a notification channel. Select `Telegram` as the notification channel type.
    - Enter the name, bot token and chat ID.
    - Click `Send Test` to verify the connection.

## Classes and Functions

### `processing_logs.py`

- Fetches job logs from the Scrapy server.
- Processes the logs to extract job statistics.
- Stores the statistics in the MySQL database.

### `job_stats.py`

- `JobStats`: Class to parse and store job statistics.
  - `create_from_logfile(job_id, spider, start_time, end_time, log_content)`: Static method to create a `JobStats` object from log content.

### `database_handler.py`

- `DatabaseHandler`: Class to manage the MySQL database connection and operations.
  - `connect()`: Connects to the MySQL database.
  - `create_table(table_name)`: Creates a table if it does not exist.
  - `has_id(job_id)`: Checks if a job ID exists in the database.
  - `insert_job_stats(job_stats)`: Inserts job statistics into the database.
  - `list_databases()`: Lists all databases.
  - `close()`: Closes the database connection.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.