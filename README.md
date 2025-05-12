# Transaction Dashboard

A real-time dashboard for monitoring transaction data across various servers.

## Features

- **Real-time Dashboard**: Monitor transaction statistics for the last 10, 30, or 60 minutes
- **Transaction Tracking**: View detailed information about recent transactions with filtering capabilities
- **Reporting**: Generate detailed reports in HTML or CSV formats with statistics
- **Administrative Functions**: Manage database records

## Installation

1. Clone this repository
2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with the following content:
   ```
   DB_HOST=localhost
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_NAME=dashboard
   ```
   Replace with your actual MySQL database credentials.

## Database Setup

The application assumes the following database table has been created:

```sql
CREATE TABLE dashboard.transactions (
    transaction_id CHAR(36) NOT NULL,
    username VARCHAR(50) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    ingress_server VARCHAR(100) NOT NULL,
    ingress_time DATETIME(3) NOT NULL,
    egress_server VARCHAR(100),
    egress_time DATETIME(3),
    status ENUM('BAD_REQUEST', 'SUBMITTED', 'COMPLETE', 'TIMEOUT', 'EP_UNAVAILABLE', 'CD_UNAVAILABLE') NOT NULL,
    PRIMARY KEY (transaction_id),
    INDEX idx_username (username),
    INDEX idx_status (status),
    INDEX idx_ingress_time (ingress_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## Running the Application

Start the application with:

```
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Dashboard Features

- **Time Window Selection**: Choose between 10, 30, or 60-minute windows
- **Auto-refresh**: Set refresh intervals (1s, 3s, 5s, 10s, or Off)
- **Transaction Table**: Configure number of items displayed (50, 100, 200)
- **Client-side Filtering**: Filter by username or status without page reload
- **Row Copy**: Copy transaction details to clipboard

## Reports

- Generate reports based on custom date ranges
- Filter by specific username or all users
- Choose between HTML (view in browser) or CSV (download) formats
- View detailed statistics including data rates, transit times, and status breakdowns

## Fallback Mode

If no database connection is available, the application will display example data to showcase functionality. 