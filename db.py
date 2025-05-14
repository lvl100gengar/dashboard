import mysql.connector
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME')
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

def get_recent_transactions(minutes_ago=None, limit=None):
    print(f"[DB DEBUG] get_recent_transactions called with minutes_ago={minutes_ago}, limit={limit}") # DEBUG
    conn = get_db_connection()
    if not conn:
        print("[DB DEBUG] Database connection failed.") # DEBUG
        return []
    print("[DB DEBUG] Database connection successful.") # DEBUG

    cursor = conn.cursor(dictionary=True)
    params = []
    
    query_base = """
        SELECT 
            transaction_id, username, file_name, file_size, 
            ingress_server, ingress_time, egress_server, egress_time, status
        FROM transactions 
    """
    
    conditions = []
    
    if minutes_ago is not None and minutes_ago > 0:
        time_filter = datetime.now() - timedelta(minutes=minutes_ago)
        conditions.append("ingress_time >= %s")
        params.append(time_filter)
        print(f"[DB DEBUG] Time filter applied: ingress_time >= {time_filter}") # DEBUG
    else:
        print("[DB DEBUG] No time filter applied.") # DEBUG
        
    if conditions:
        query_base += " WHERE " + " AND ".join(conditions)
        
    query_base += " ORDER BY ingress_time DESC"
    
    if limit is not None:
        query_base += " LIMIT %s"
        params.append(limit)
        
    try:
        print(f"[DB DEBUG] Executing query: {query_base} with params: {params}") # DEBUG
        cursor.execute(query_base, tuple(params))
        transactions = cursor.fetchall()
        print(f"[DB DEBUG] Query returned {len(transactions)} transactions.") # DEBUG
        
        # Calculate transit_time and format times
        for t in transactions:
            if t['egress_time'] and t['ingress_time']:
                transit = t['egress_time'] - t['ingress_time']
                t['transit_time_seconds'] = transit.total_seconds()
                t['transit_time'] = f"{transit.total_seconds():.3f}s"
            else:
                t['transit_time_seconds'] = None
                t['transit_time'] = "N/A"
            
            t['ingress_time_str'] = t['ingress_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if t['ingress_time'] else "N/A"
            t['egress_time_str'] = t['egress_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if t['egress_time'] else "N/A"
            
        return transactions
    except mysql.connector.Error as err:
        print(f"Error fetching recent transactions: {err}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def get_transactions_for_report(start_time_dt, end_time_dt, username=None):
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    try:
        params = [start_time_dt, end_time_dt]
        query = """
            SELECT 
                transaction_id, username, file_name, file_size, 
                ingress_server, ingress_time, egress_server, egress_time, status
            FROM transactions 
            WHERE ingress_time >= %s AND ingress_time <= %s
        """
        if username and username.lower() != 'all':
            query += " AND username = %s"
            params.append(username)
        
        query += " ORDER BY ingress_time DESC"
        
        cursor.execute(query, tuple(params))
        transactions = cursor.fetchall()
        
        # Add transit_time and string formatted times for consistency if needed elsewhere
        # but for raw data for reports, original datetime objects might be preferable for calculations.
        for t in transactions:
            if t['egress_time'] and t['ingress_time']:
                transit = t['egress_time'] - t['ingress_time']
                t['transit_time_seconds'] = transit.total_seconds() # Keep as float for calculations
                t['transit_time_str'] = f"{t['transit_time_seconds']:.3f}s"
            else:
                t['transit_time_seconds'] = None
                t['transit_time_str'] = "N/A"
            
            t['ingress_time_str'] = t['ingress_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if t['ingress_time'] else "N/A"
            t['egress_time_str'] = t['egress_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if t['egress_time'] else "N/A"

        return transactions
    except mysql.connector.Error as err:
        print(f"Error fetching transactions for report: {err}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def get_unique_usernames():
    """Retrieve all unique usernames from the database."""
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor()
    try:
        query = "SELECT DISTINCT username FROM transactions ORDER BY username"
        cursor.execute(query)
        usernames = [row[0] for row in cursor.fetchall()]
        return usernames
    except mysql.connector.Error as err:
        print(f"Error fetching unique usernames: {err}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def clear_all_transactions():
    """Clear all transactions from the database."""
    conn = get_db_connection()
    if not conn:
        return False, "Database connection failed."
    
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM transactions") # Consider TRUNCATE TABLE transactions for performance on large tables
        conn.commit()
        return True, f"{cursor.rowcount} transactions deleted successfully."
    except mysql.connector.Error as err:
        conn.rollback()
        print(f"Error clearing transactions: {err}")
        return False, f"Error clearing transactions: {err}"
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

def get_db_metadata():
    """Fetches metadata about the database like host, type, version, and uptime."""
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "error": "Database connection failed.", "host": os.getenv('DB_HOST', 'N/A')}

    cursor = conn.cursor(dictionary=True)
    metadata = {
        "status": "connected",
        "host": os.getenv('DB_HOST', 'N/A'),
        "db_type": "MySQL",
        "version": None,
        "uptime": None,
        "error": None
    }
    try:
        cursor.execute("SELECT VERSION() as version;")
        result = cursor.fetchone()
        if result:
            metadata["version"] = result["version"]

        cursor.execute("SHOW GLOBAL STATUS LIKE 'Uptime';")
        result = cursor.fetchone()
        if result and result['Value']:
            uptime_seconds = int(result['Value'])
            days = uptime_seconds // (24 * 3600)
            uptime_seconds %= (24 * 3600)
            hours = uptime_seconds // 3600
            uptime_seconds %= 3600
            minutes = uptime_seconds // 60
            if days > 0:
                metadata["uptime"] = f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                metadata["uptime"] = f"{hours}h {minutes}m"
            else:
                metadata["uptime"] = f"{minutes}m"
        else:
            metadata["uptime"] = "N/A"
            
    except mysql.connector.Error as err:
        print(f"Error fetching DB metadata: {err}")
        metadata["status"] = "error"
        metadata["error"] = str(err)
        metadata["version"] = "Error"
        metadata["uptime"] = "Error"
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return metadata

def get_db_table_info():
    """Fetches information about database tables, like row counts and overall size."""
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed."}

    cursor = conn.cursor(dictionary=True)
    info = {
        "table_stats": {},
        "total_records_transactions": 0,
        "db_size_mb": None,
        "error": None
    }
    try:
        cursor.execute("SELECT table_name, table_rows FROM INFORMATION_SCHEMA.TABLES WHERE table_schema = DATABASE();")
        tables = cursor.fetchall()
        for table in tables:
            info["table_stats"][table["table_name"]] = table["table_rows"]
            if table["table_name"] == "transactions":
                info["total_records_transactions"] = table["table_rows"]
        
        cursor.execute("SELECT table_schema AS \"Database\", ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS \"SizeMB\" FROM information_schema.TABLES WHERE table_schema = DATABASE() GROUP BY table_schema;")
        size_result = cursor.fetchone()
        if size_result:
            info["db_size_mb"] = f"{size_result['SizeMB']} MB"
            
    except mysql.connector.Error as err:
        print(f"Error fetching DB table info: {err}")
        info["error"] = str(err)
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
    return info

# Add more functions here for other database operations as needed 