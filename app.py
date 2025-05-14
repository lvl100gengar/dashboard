from flask import Flask, render_template, request, Response, redirect, url_for, jsonify
import uuid
import random
from datetime import datetime, timedelta
from db import (
    get_recent_transactions, get_transactions_for_report, 
    clear_all_transactions, get_unique_usernames,
    get_db_metadata, get_db_table_info
)
import csv
import io
import statistics # For standard deviation
import os

app = Flask(__name__)

# Custom Jinja filter for formatting file sizes
@app.template_filter('filesizeformat')
def filesizeformat(value, binary=False):
    """Format a number of bytes like a human readable filesize (e.g. 10 kB, 1.2 MB, 100 Bytes)."""
    if value is None:
        return "0 Bytes"
    if value < 1024:
        return f"{value} Bytes"
    
    exponent = int( (len(str(int(value))) -1) // 3 )
    
    if binary:
        # For binary, 1 K = 1024.
        if exponent > 5: exponent = 5 # Limit to PB
        unit = ['Bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB'][exponent]
        size = float(value) / (1024**exponent)
    else:
        # For SI, 1 K = 1000.
        if exponent > 5: exponent = 5 # Limit to PB
        unit = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'][exponent]
        size = float(value) / (1000**exponent)
        
    return f"{size:.1f} {unit}"

# HELPER FUNCTIONS (Restoring these as they are needed)
def calculate_percentile(values, percentile):
    """Calculate the percentile value from a list of values without using NumPy"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    index = (n - 1) * (percentile / 100)
    if index.is_integer():
        return sorted_values[int(index)]
    lower_index = int(index)
    upper_index = lower_index + 1
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index] if upper_index < n else lower_value
    fraction = index - lower_index
    return lower_value + (upper_value - lower_value) * fraction

def format_time(seconds):
    """Format time with appropriate SI units, starting from ms"""
    if seconds is None or not isinstance(seconds, (int, float)) or seconds < 0:
        return "0 ms"
    if seconds < 0.001:
        return f"{seconds * 1000000:.1f} µs"
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    if seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} m"
    hours = seconds / 3600
    return f"{hours:.1f} h"

def format_data_rate(bits_per_second):
    """Format data rate with appropriate SI units, starting from Bps (Restored if needed by reports)"""
    if bits_per_second is None or bits_per_second < 0:
        return "0 Bps"
    if bits_per_second < 1000:
        return f"{bits_per_second:.1f} Bps"
    units = ['', 'K', 'M', 'G', 'T', 'P']
    unit_index = 0
    val_to_format = float(bits_per_second)
    while val_to_format >= 1000 and unit_index < len(units) - 1:
        val_to_format /= 1000.0
        unit_index += 1
    return f"{val_to_format:.1f} {units[unit_index]}Bps"

def calculate_report_stats_for_subset(transactions_subset, duration_minutes=None):
    """Calculate detailed stats for a subset of transactions for reporting (Restored)."""
    if not transactions_subset:
        return {
            'total_transactions': 0, 'total_bytes': 0,
            'max_data_rate': 0.0, 'avg_data_rate': 0.0,
            'max_transit_time': 0.0, 'avg_transit_time': 0.0,
            'p75_transit_time': 0.0, 'p95_transit_time': 0.0, 'p99_transit_time': 0.0,
            'status_breakdown': {},
            'max_data_rate_formatted': '0 Bps', 'avg_data_rate_formatted': '0 Bps',
            'max_transit_time_formatted': '0 ms', 'avg_transit_time_formatted': '0 ms',
            'p75_transit_time_formatted': '0 ms', 'p95_transit_time_formatted': '0 ms', 'p99_transit_time_formatted': '0 ms',
            'min_file_size': 0, 'avg_file_size': 0, 'max_file_size': 0,
            'min_file_size_formatted': '0 Bytes', 'avg_file_size_formatted': '0 Bytes', 'max_file_size_formatted': '0 Bytes',
            'transaction_rate_per_minute': 0.0
        }

    data_rates_bps = []
    transit_times_seconds = []
    file_sizes = []
    total_bytes = 0
    status_breakdown = {}

    for t in transactions_subset:
        file_size = t.get('file_size', 0)
        total_bytes += file_size
        if file_size > 0: # Only consider for file size stats if actual size > 0
            file_sizes.append(file_size)
        status = t.get('status', 'UNKNOWN')
        status_breakdown[status] = status_breakdown.get(status, 0) + 1
        if t.get('transit_time_seconds') and t['transit_time_seconds'] > 0 and file_size > 0:
            rate = (file_size * 8) / t['transit_time_seconds']
            data_rates_bps.append(rate)
            transit_times_seconds.append(t['transit_time_seconds'])
    
    # File size stats
    min_fs = min(file_sizes) if file_sizes else 0
    avg_fs = statistics.mean(file_sizes) if file_sizes else 0
    max_fs = max(file_sizes) if file_sizes else 0

    # Calculate percentiles and means, ensuring lists are not empty
    p75_transit = calculate_percentile(transit_times_seconds, 75) if transit_times_seconds else 0.0
    p95_transit = calculate_percentile(transit_times_seconds, 95) if transit_times_seconds else 0.0
    p99_transit = calculate_percentile(transit_times_seconds, 99) if transit_times_seconds else 0.0
    
    max_data_rate = max(data_rates_bps) if data_rates_bps else 0.0
    avg_data_rate = statistics.mean(data_rates_bps) if data_rates_bps else 0.0
    
    max_transit = max(transit_times_seconds) if transit_times_seconds else 0.0
    avg_transit = statistics.mean(transit_times_seconds) if transit_times_seconds else 0.0

    # Transaction rate
    tx_rate_per_min = 0.0
    if duration_minutes and duration_minutes > 0 and len(transactions_subset) > 0:
        tx_rate_per_min = round(len(transactions_subset) / duration_minutes, 1)
    
    return {
        'total_transactions': len(transactions_subset),
        'total_bytes': total_bytes,
        'max_data_rate': max_data_rate,
        'avg_data_rate': avg_data_rate,
        'max_data_rate_formatted': format_data_rate(max_data_rate),
        'avg_data_rate_formatted': format_data_rate(avg_data_rate),
        'max_transit_time': max_transit,
        'avg_transit_time': avg_transit,
        'max_transit_time_formatted': format_time(max_transit),
        'avg_transit_time_formatted': format_time(avg_transit),
        'p75_transit_time': p75_transit,
        'p95_transit_time': p95_transit,
        'p99_transit_time': p99_transit,
        'p75_transit_time_formatted': format_time(p75_transit),
        'p95_transit_time_formatted': format_time(p95_transit), 
        'p99_transit_time_formatted': format_time(p99_transit),
        'status_breakdown': status_breakdown,
        'min_file_size': min_fs,
        'avg_file_size': avg_fs,
        'max_file_size': max_fs,
        'min_file_size_formatted': filesizeformat(min_fs),
        'avg_file_size_formatted': filesizeformat(avg_fs),
        'max_file_size_formatted': filesizeformat(max_fs),
        'transaction_rate_per_minute': tx_rate_per_min
    }

def calculate_dashboard_stats(transactions_for_stats, time_window_minutes):
    stats = {
        'ingress': {
            'BAD_REQUEST': 0, 'CD_UNAVAILABLE': 0, 'SUBMITTED': 0,
            'total_tx': 0, 'tx_per_sec': 0.0,
            'bad_request_rate': 0.0, 'cd_unavailable_rate': 0.0
        },
        'egress': {
            'COMPLETE': 0, 'EP_UNAVAILABLE': 0, 
            'total_tx': 0, 'total_bytes': 0, 'total_duration_seconds': 0,
            'data_rate_mbps': 0.0, 'tx_per_sec': 0.0, 
            'avg_transit_time': 0.0, 'max_transit_time': 0.0,
            'p95_transit_time': 0.0, 'p99_transit_time': 0.0,
            'ep_unavailable_rate': 0.0,
            'total_volume_complete_bytes': 0,
            'total_volume_complete_str': '0 Bytes'
        },
        'general': {
            'active_users': 0,
            'success_rate': 0.0
        }
    }
    if not transactions_for_stats:
        stats['egress']['avg_transit_time'] = '-'
        stats['egress']['max_transit_time'] = '-'
        stats['egress']['p95_transit_time'] = '-'
        stats['egress']['p99_transit_time'] = '-'
        return stats

    relevant_tx_for_egress_rates = []
    transit_times = []
    active_usernames = set()

    for t in transactions_for_stats:
        stats['ingress']['total_tx'] += 1
        if t.get('username'):
            active_usernames.add(t['username'])

        if t['status'] == 'BAD_REQUEST':
            stats['ingress']['BAD_REQUEST'] += 1
        if t['status'] == 'CD_UNAVAILABLE':
            stats['ingress']['CD_UNAVAILABLE'] += 1
        if t['status'] == 'SUBMITTED':
            stats['ingress']['SUBMITTED'] += 1
            
        if t['status'] in ['COMPLETE', 'EP_UNAVAILABLE']:
            stats['egress']['total_tx'] += 1
            if t['status'] == 'COMPLETE':
                stats['egress']['COMPLETE'] += 1
                if t.get('file_size'): # Accumulate for total volume (complete)
                    stats['egress']['total_volume_complete_bytes'] += t['file_size']
            if t['status'] == 'EP_UNAVAILABLE':
                stats['egress']['EP_UNAVAILABLE'] += 1
            
            if t.get('file_size') and t.get('ingress_time') and t.get('egress_time'):
                stats['egress']['total_bytes'] += t['file_size']
                duration = t.get('transit_time_seconds', 0)
                if duration > 0:
                    relevant_tx_for_egress_rates.append(t)
                    transit_times.append(duration)
                    stats['egress']['total_duration_seconds'] += duration
    
    if transit_times:
        stats['egress']['avg_transit_time'] = format_time(sum(transit_times) / len(transit_times))
        stats['egress']['max_transit_time'] = format_time(max(transit_times))
        stats['egress']['p95_transit_time'] = format_time(calculate_percentile(transit_times, 95))
        stats['egress']['p99_transit_time'] = format_time(calculate_percentile(transit_times, 99))
    else:
        stats['egress']['avg_transit_time'] = '-'
        stats['egress']['max_transit_time'] = '-'
        stats['egress']['p95_transit_time'] = '-'
        stats['egress']['p99_transit_time'] = '-'
    
    if stats['egress']['total_duration_seconds'] > 0 and relevant_tx_for_egress_rates:
        total_bytes_for_rate = sum(tx['file_size'] for tx in relevant_tx_for_egress_rates)
        stats['egress']['data_rate_mbps'] = round((total_bytes_for_rate * 8 / (1024*1024)) / stats['egress']['total_duration_seconds'], 1)
        stats['egress']['tx_per_sec'] = round(len(relevant_tx_for_egress_rates) / stats['egress']['total_duration_seconds'], 1)
    
    if time_window_minutes > 0:
        time_window_seconds = time_window_minutes * 60
        if stats['ingress']['total_tx'] > 0:
            stats['ingress']['tx_per_sec'] = round(stats['ingress']['total_tx'] / time_window_seconds, 1)

    # Calculate new error rates
    total_ingress_tx = stats['ingress']['total_tx']
    if total_ingress_tx > 0:
        stats['ingress']['bad_request_rate'] = round((stats['ingress']['BAD_REQUEST'] / total_ingress_tx) * 100, 1)
        stats['ingress']['cd_unavailable_rate'] = round((stats['ingress']['CD_UNAVAILABLE'] / total_ingress_tx) * 100, 1)

    total_egress_attempts = stats['egress']['COMPLETE'] + stats['egress']['EP_UNAVAILABLE']
    if total_egress_attempts > 0:
        stats['egress']['ep_unavailable_rate'] = round((stats['egress']['EP_UNAVAILABLE'] / total_egress_attempts) * 100, 1)
    
    # Set active user count
    stats['general']['active_users'] = len(active_usernames)
    
    # Calculate Success Rate
    total_successful = stats['egress']['COMPLETE']
    total_failed = stats['ingress']['BAD_REQUEST'] + stats['ingress']['CD_UNAVAILABLE'] + stats['egress']['EP_UNAVAILABLE']
    total_attempts_for_success_rate = total_successful + total_failed
    
    if total_attempts_for_success_rate > 0:
        stats['general']['success_rate'] = round((total_successful / total_attempts_for_success_rate) * 100, 1)
    else:
        stats['general']['success_rate'] = 0.0

    # Format total_volume_complete_bytes for display
    stats['egress']['total_volume_complete_str'] = filesizeformat(stats['egress']['total_volume_complete_bytes'])

    return stats

@app.route('/')
def dashboard():
    time_window = int(request.args.get('time_window', 60))
    return render_template('dashboard_page.html', 
                           time_window=time_window,
                           initial_load=True)

@app.route('/transactions')
def transactions_live():
    num_items = int(request.args.get('num_items', 50))
    return render_template('transactions_live_page.html',
                           num_items=num_items,
                           initial_load=True)

@app.route('/reports')
def reports_generate():
    return render_template('reports_generate_page.html',
                           initial_load=True)

@app.route('/api/dashboard-stats')
def api_dashboard_stats():
    time_window = int(request.args.get('time_window', 60))
    transactions_for_stats = get_recent_transactions(minutes_ago=time_window, limit=None)
    dashboard_stats_data = calculate_dashboard_stats(transactions_for_stats, time_window)
    
    # Prepare transactions for JSON serialization (similar to /api/transactions-feed)
    transactions_in_window_json = []
    for t in transactions_for_stats: # Use the same list used for stats
        t_dict = dict(t) 
        t_dict['ingress_time_str'] = t.get('ingress_time_str', 'N/A')
        t_dict['egress_time_str'] = t.get('egress_time_str', 'N/A')
        t_dict['transit_time'] = t.get('transit_time', 'N/A')
        if 'ingress_time' in t_dict and isinstance(t_dict['ingress_time'], datetime):
            t_dict['ingress_time'] = t_dict['ingress_time'].isoformat()
        if 'egress_time' in t_dict and isinstance(t_dict['egress_time'], datetime):
            t_dict['egress_time'] = t_dict['egress_time'].isoformat()
        transactions_in_window_json.append(t_dict)
        
    return jsonify({
        'stats': dashboard_stats_data,
        'time_window': time_window,
        'transactions_in_window': transactions_in_window_json, # Add transactions to the response
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/transactions-feed')
def api_transactions_feed():
    num_items = int(request.args.get('num_items', 50))
    live_transactions = get_recent_transactions(minutes_ago=None, limit=num_items) 
    
    transactions_json = []
    for t in live_transactions:
        t_dict = dict(t)
        t_dict['ingress_time_str'] = t.get('ingress_time_str', 'N/A')
        t_dict['egress_time_str'] = t.get('egress_time_str', 'N/A')
        t_dict['transit_time'] = t.get('transit_time', 'N/A')
        if 'ingress_time' in t_dict and isinstance(t_dict['ingress_time'], datetime):
            t_dict['ingress_time'] = t_dict['ingress_time'].isoformat()
        if 'egress_time' in t_dict and isinstance(t_dict['egress_time'], datetime):
            t_dict['egress_time'] = t_dict['egress_time'].isoformat()
        transactions_json.append(t_dict)
        
    return jsonify({
        'transactions': transactions_json,
        'num_items': num_items,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/download_report', methods=['POST'])
def download_report():
    """Handle report generation and download directly"""
    # Default to the last 24 hours if no date range is specified
    default_start_dt = datetime.now() - timedelta(hours=24)
    default_end_dt = datetime.now()
    
    try:
        daterange_str = request.form.get('daterange', '')
        start_str, end_str = daterange_str.split(' - ')
        start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        # Handle error or use default if parsing fails
        start_dt, end_dt = default_start_dt, default_end_dt
    
    username_filter = request.form.get('username', 'all').strip()
    selected_report_format = request.form.get('report_format', 'csv')
    
    # Get transactions from database
    transactions = get_transactions_for_report(start_dt, end_dt, username_filter if username_filter.lower() != 'all' else None)
    
    # If no transactions found, redirect with a message
    if not transactions:
        return redirect(url_for('reports_generate', 
                                report_message="No transactions found for the selected criteria. Please try a different date range or filter.", 
                                report_message_type="warning"))

    # For CSV format, return CSV file
    if selected_report_format == 'csv':
        si = io.StringIO()
        cw = csv.writer(si)
        
        # Define headers based on DB table + calculated fields
        headers = ['transaction_id', 'username', 'file_name', 'file_size', 'ingress_server', 
                  'ingress_time', 'egress_server', 'egress_time', 'status', 'transit_time_seconds']
        cw.writerow(headers)
        
        for t in transactions:
            row = [t.get(h) for h in headers]
            cw.writerow(row)
        
        output = si.getvalue()
        filename = f"transactions_{start_dt.strftime('%Y%m%d%H%M%S')}_{end_dt.strftime('%Y%m%d%H%M%S')}"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}.csv"}
        )
    
    # For HTML format, generate HTML report for download
    elif selected_report_format == 'html':
        # Calculate statistics for the report
        report_duration_minutes = (end_dt - start_dt).total_seconds() / 60
        overall_stats = calculate_report_stats_for_subset(transactions, duration_minutes=report_duration_minutes)
        overall_stats['start_time_str'] = start_dt.strftime('%Y-%m-%d %H:%M')
        overall_stats['end_time_str'] = end_dt.strftime('%Y-%m-%d %H:%M')
        
        # Calculate stats for each username
        user_specific_stats = {}
        distinct_users = sorted(list(set(t['username'] for t in transactions)))
        for user in distinct_users:
            user_tx = [t for t in transactions if t['username'] == user]
            # Not passing duration_minutes for user-specific rates for now
            user_specific_stats[user] = calculate_report_stats_for_subset(user_tx)
        
        # Create HTML report
        report_data = {
            'transactions': transactions,
            'overall_stats': overall_stats,
            'user_stats': user_specific_stats
        }
        
        html_content = render_template(
            'report_template.html',
            report_data=report_data,
            now=datetime.now()
        )
        
        filename = f"transactions_{start_dt.strftime('%Y%m%d%H%M%S')}_{end_dt.strftime('%Y%m%d%H%M%S')}"
        
        return Response(
            html_content,
            mimetype="text/html",
            headers={"Content-disposition": f"attachment; filename={filename}.html"}
        )

@app.route('/admin/clear-db', methods=['POST'])
def admin_clear_db():
    success, message = clear_all_transactions()
    message_type = 'success' if success else 'error'
    # Use global flash message instead of rendering admin page
    if success:
        return jsonify({"success": True, "message": message, "message_type": message_type})
    else:
        return jsonify({"success": False, "message": message, "message_type": message_type})

@app.route('/api/usernames')
def api_usernames():
    """API endpoint to get unique usernames for dropdowns"""    
    usernames = get_unique_usernames()   
   
    return jsonify({
        'usernames': usernames
    })

@app.route('/api/db-status')
def api_get_db_status():
    metadata = get_db_metadata()
    if 'host' not in metadata:
        metadata['host'] = os.getenv('DB_HOST', 'N/A') 
    return jsonify(metadata)

@app.route('/api/db-table-stats', endpoint='api_get_db_table_stats')
def api_get_db_table_stats():
    table_info = get_db_table_info()
    if table_info.get('error'):
        return jsonify({"error": table_info['error']}), 500
    
    response_data = {
        "table_stats": table_info.get("table_stats", {}),
        "total_records": table_info.get("total_records_transactions", 0),
        "db_size": table_info.get("db_size_mb", "N/A")
    }
    return jsonify(response_data)

@app.route('/favicon.ico')
def favicon():
    return Response(status=204)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 