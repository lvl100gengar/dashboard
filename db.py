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

def get_recent_transactions(minutes_ago=60, limit=50):
    conn = get_db_connection()
    if not conn:
        return []

    cursor = conn.cursor(dictionary=True)
    try:
        time_filter = datetime.now() - timedelta(minutes=minutes_ago)
        
        query = """
            SELECT 
                transaction_id, username, file_name, file_size, 
                ingress_server, ingress_time, egress_server, egress_time, status
            FROM transactions 
            WHERE ingress_time >= %s 
            ORDER BY ingress_time DESC
        """
        
        # If limit is specified, add LIMIT clause
        if limit is not None:
            query += " LIMIT %s"
            cursor.execute(query, (time_filter, limit))
        else:
            cursor.execute(query, (time_filter,))
            
        transactions = cursor.fetchall()
        
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

# Add more functions here for other database operations as needed 