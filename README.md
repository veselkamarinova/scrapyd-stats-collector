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
    python -m venv env
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

1. Ensure your MySQL server is running and accessible with the credentials provided in the `.venv` file.

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

## License

This project is licensed under the GPL License. See the `LICENSE` file for details.