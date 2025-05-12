from flask import Flask, render_template, request, Response, redirect, url_for, jsonify
import uuid
import random
from datetime import datetime, timedelta
from db import get_recent_transactions, get_transactions_for_report, clear_all_transactions, get_unique_usernames # Import clear_all_transactions and get_unique_usernames
import csv
import io
import statistics # For standard deviation

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

# Hardcoded example data (fallback)
example_data_definition = [
    {
        'transaction_id': lambda: str(uuid.uuid4()),
        'username': 'user_alpha',
        'file_name': 'document_final_v3.docx',
        'file_size': lambda: random.randint(100000, 5000000),
        'ingress_server': 'ing_server_01',
        'ingress_time': lambda: datetime.now() - timedelta(seconds=random.randint(0, 3600)),
        'egress_server': None,
        'egress_time': None,
        'status': 'SUBMITTED'
    },
    {
        'transaction_id': lambda: str(uuid.uuid4()),
        'username': 'user_beta',
        'file_name': 'archive_backup.zip',
        'file_size': lambda: random.randint(50000000, 200000000),
        'ingress_server': 'ing_server_02',
        'ingress_time': lambda: datetime.now() - timedelta(seconds=random.randint(0, 3600)),
        'egress_server': 'egr_server_01',
        'egress_time': lambda: datetime.now() - timedelta(seconds=random.randint(0, 100)), # Ensure egress is after ingress for this example
        'status': 'COMPLETE'
    },
    {
        'transaction_id': lambda: str(uuid.uuid4()),
        'username': 'user_gamma',
        'file_name': 'presentation_deck.pptx',
        'file_size': lambda: random.randint(1000000, 10000000),
        'ingress_server': 'ing_server_01',
        'ingress_time': lambda: datetime.now() - timedelta(seconds=random.randint(0, 3600)),
        'egress_server': None,
        'egress_time': None,
        'status': 'BAD_REQUEST'
    }
]

def generate_example_data():
    generated_examples = []
    for item_def in example_data_definition:
        item = {}
        for key, value_gen in item_def.items():
            item[key] = value_gen() if callable(value_gen) else value_gen
        
        if item['status'] == 'COMPLETE' and item.get('egress_time') and item.get('ingress_time'):
            if item['egress_time'] <= item['ingress_time']:
                item['egress_time'] = item['ingress_time'] + timedelta(seconds=random.randint(1,300))

        if item.get('egress_time') and item.get('ingress_time'):
            transit_time = item['egress_time'] - item['ingress_time']
            item['transit_time_seconds'] = transit_time.total_seconds()
            item['transit_time'] = f"{item['transit_time_seconds']:.3f}s"
        else:
            item['transit_time_seconds'] = None
            item['transit_time'] = "N/A"
        item['ingress_time_str'] = item['ingress_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if item.get('ingress_time') else "N/A"
        item['egress_time_str'] = item['egress_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if item.get('egress_time') else "N/A"
        generated_examples.append(item)
    return generated_examples

def calculate_dashboard_stats(transactions_for_stats, time_window_minutes):
    stats = {
        'ingress': {'BAD_REQUEST': 0, 'CD_UNAVAILABLE': 0, 'SUBMITTED': 0, 'total_tx': 0, 'tx_per_sec': 0.0},
        'egress': {'COMPLETE': 0, 'EP_UNAVAILABLE': 0, 'total_tx': 0, 'total_bytes': 0, 'total_duration_seconds': 0, 
                  'data_rate_mbps': 0.0, 'tx_per_sec': 0.0, 'avg_transit_time': 0.0, 'max_transit_time': 0.0, 
                  'p95_transit_time': 0.0, 'p99_transit_time': 0.0}
    }
    if not transactions_for_stats:
        return stats

    relevant_tx_for_egress_rates = []
    transit_times = []

    for t in transactions_for_stats:
        # Ingress stats consider all transactions in the window
        stats['ingress']['total_tx'] += 1
        if t['status'] == 'BAD_REQUEST':
            stats['ingress']['BAD_REQUEST'] += 1
        if t['status'] == 'CD_UNAVAILABLE':
            stats['ingress']['CD_UNAVAILABLE'] += 1
        if t['status'] == 'SUBMITTED':
            stats['ingress']['SUBMITTED'] += 1
            
        # Egress stats specific to COMPLETE and EP_UNAVAILABLE
        if t['status'] in ['COMPLETE', 'EP_UNAVAILABLE']:
            stats['egress']['total_tx'] += 1
            if t['status'] == 'COMPLETE':
                stats['egress']['COMPLETE'] += 1
            if t['status'] == 'EP_UNAVAILABLE':
                stats['egress']['EP_UNAVAILABLE'] += 1
            
            if t.get('file_size') and t.get('ingress_time') and t.get('egress_time'):
                stats['egress']['total_bytes'] += t['file_size']
                # transit_time_seconds should be pre-calculated by db.py or generate_example_data
                duration = t.get('transit_time_seconds', 0)
                if duration > 0:
                    relevant_tx_for_egress_rates.append(t)
                    transit_times.append(duration)
                    stats['egress']['total_duration_seconds'] += duration
    
    # Calculate transit time statistics
    if transit_times:
        stats['egress']['avg_transit_time'] = format_time(sum(transit_times) / len(transit_times))
        stats['egress']['max_transit_time'] = format_time(max(transit_times))
        stats['egress']['p95_transit_time'] = format_time(calculate_percentile(transit_times, 95))
        stats['egress']['p99_transit_time'] = format_time(calculate_percentile(transit_times, 99))
    
    if stats['egress']['total_duration_seconds'] > 0 and relevant_tx_for_egress_rates:
        total_bytes_for_rate = sum(tx['file_size'] for tx in relevant_tx_for_egress_rates)
        stats['egress']['data_rate_mbps'] = round((total_bytes_for_rate * 8 / (1024*1024)) / stats['egress']['total_duration_seconds'], 1)
        stats['egress']['tx_per_sec'] = round(len(relevant_tx_for_egress_rates) / stats['egress']['total_duration_seconds'], 1)
    
    if time_window_minutes > 0:
        time_window_seconds = time_window_minutes * 60
        if stats['ingress']['total_tx'] > 0:
            stats['ingress']['tx_per_sec'] = round(stats['ingress']['total_tx'] / time_window_seconds, 1)
    
    return stats

@app.route('/')
def index():
    time_window = int(request.args.get('time_window', 60))
    num_items = int(request.args.get('num_items', 50))
    
    # Just render the template without data - data will be loaded via AJAX
    return render_template('index.html', 
                           stats=None,
                           transactions=None, 
                           using_example_data=False,
                           time_window=time_window,
                           num_items=num_items,
                           initial_load=True)

def calculate_percentile(values, percentile):
    """Calculate the percentile value from a list of values without using NumPy"""
    if not values:
        return 0.0
    
    # Sort the values
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    # Calculate the index for the percentile
    index = (n - 1) * (percentile / 100)
    
    # If index is an integer, return the value at that index
    if index.is_integer():
        return sorted_values[int(index)]
    
    # Otherwise interpolate between the two closest values
    lower_index = int(index)
    upper_index = lower_index + 1
    
    lower_value = sorted_values[lower_index]
    # Handle case where upper_index is out of bounds (should not happen with our logic)
    upper_value = sorted_values[upper_index] if upper_index < n else lower_value
    
    # Interpolate
    fraction = index - lower_index
    return lower_value + (upper_value - lower_value) * fraction

def format_data_rate(bits_per_second):
    """Format data rate with appropriate SI units, starting from Bps"""
    if bits_per_second is None or bits_per_second < 0:
        return "0 Bps"
    
    if bits_per_second < 1000:
        return f"{bits_per_second:.1f} Bps"
    
    # Use SI units: K = 1000, not 1024
    units = ['', 'K', 'M', 'G', 'T', 'P']
    unit_index = 0
    
    while bits_per_second >= 1000 and unit_index < len(units) - 1:
        bits_per_second /= 1000.0
        unit_index += 1
    
    return f"{bits_per_second:.1f} {units[unit_index]}Bps"

def format_time(seconds):
    """Format time with appropriate SI units, starting from ms"""
    if seconds is None or seconds < 0:
        return "0 ms"
    
    # Less than a millisecond
    if seconds < 0.001:
        return f"{seconds * 1000000:.1f} µs"
    
    # Less than a second
    if seconds < 1:
        return f"{seconds * 1000:.1f} ms"
    
    # Less than a minute
    if seconds < 60:
        return f"{seconds:.1f} s"
    
    # Less than an hour
    if seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} m"
    
    # Hours or more
    hours = seconds / 3600
    return f"{hours:.1f} h"

def calculate_report_stats_for_subset(transactions_subset):
    if not transactions_subset:
        return {
            'total_transactions': 0, 
            'total_bytes': 0,
            'min_data_rate': 0.0,
            'max_data_rate': 0.0, 
            'avg_data_rate': 0.0,
            'min_transit_time': 0.0, 
            'max_transit_time': 0.0, 
            'avg_transit_time': 0.0,
            'p75_transit_time': 0.0, 
            'p95_transit_time': 0.0, 
            'p99_transit_time': 0.0,
            'status_breakdown': {}
        }

    data_rates_bps = []
    transit_times_seconds = []
    total_bytes = 0
    status_breakdown = {}

    for t in transactions_subset:
        total_bytes += t.get('file_size', 0)
        status = t.get('status', 'UNKNOWN')
        status_breakdown[status] = status_breakdown.get(status, 0) + 1

        if t.get('transit_time_seconds') and t['transit_time_seconds'] > 0 and t.get('file_size'):
            # Calculate in bits per second (not mbps)
            rate = (t['file_size'] * 8) / t['transit_time_seconds']
            data_rates_bps.append(rate)
            transit_times_seconds.append(t['transit_time_seconds'])
    
    # Calculate percentiles for transit time only, not for data rates
    p75_transit = calculate_percentile(transit_times_seconds, 75) if transit_times_seconds else 0.0
    p95_transit = calculate_percentile(transit_times_seconds, 95) if transit_times_seconds else 0.0
    p99_transit = calculate_percentile(transit_times_seconds, 99) if transit_times_seconds else 0.0
    
    # Format values with SI units
    min_data_rate = min(data_rates_bps) if data_rates_bps else 0.0
    max_data_rate = max(data_rates_bps) if data_rates_bps else 0.0
    avg_data_rate = statistics.mean(data_rates_bps) if data_rates_bps else 0.0
    
    min_transit = min(transit_times_seconds) if transit_times_seconds else 0.0
    max_transit = max(transit_times_seconds) if transit_times_seconds else 0.0
    avg_transit = statistics.mean(transit_times_seconds) if transit_times_seconds else 0.0
    
    return {
        'total_transactions': len(transactions_subset),
        'total_bytes': total_bytes,
        'min_data_rate': min_data_rate,
        'max_data_rate': max_data_rate,
        'avg_data_rate': avg_data_rate,
        'min_data_rate_formatted': format_data_rate(min_data_rate),
        'max_data_rate_formatted': format_data_rate(max_data_rate),
        'avg_data_rate_formatted': format_data_rate(avg_data_rate),
        'min_transit_time': min_transit,
        'max_transit_time': max_transit,
        'avg_transit_time': avg_transit,
        'min_transit_time_formatted': format_time(min_transit),
        'max_transit_time_formatted': format_time(max_transit),
        'avg_transit_time_formatted': format_time(avg_transit),
        'p75_transit_time': p75_transit,
        'p95_transit_time': p95_transit,
        'p99_transit_time': p99_transit,
        'p75_transit_time_formatted': format_time(p75_transit),
        'p95_transit_time_formatted': format_time(p95_transit), 
        'p99_transit_time_formatted': format_time(p99_transit),
        'status_breakdown': status_breakdown
    }

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
    
    # Get transactions from database or generate example data if DB unavailable
    transactions = get_transactions_for_report(start_dt, end_dt, username_filter if username_filter.lower() != 'all' else None)
    
    # If no transactions from DB, use example data
    using_example_data = False
    if not transactions:
        # Generate example data for the report - create more varied examples for a better report
        using_example_data = True
        all_example_data = []
        # Generate a larger set of example data to make the report more interesting
        num_examples = 50
        for _ in range(num_examples):
            all_example_data.extend(generate_example_data())
        
        # Filter example data to match the time window
        transactions = [
            tx for tx in all_example_data 
            if start_dt <= tx['ingress_time'] <= end_dt
        ]
        
        # Apply username filter if specified
        if username_filter and username_filter.lower() != 'all':
            transactions = [tx for tx in transactions if tx['username'] == username_filter]
    
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
        if using_example_data:
            filename += "_example"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={filename}.csv"}
        )
    
    # For HTML format, generate HTML report for download
    elif selected_report_format == 'html':
        # Calculate statistics for the report
        overall_stats = calculate_report_stats_for_subset(transactions)
        overall_stats['start_time_str'] = start_dt.strftime('%Y-%m-%d %H:%M')
        overall_stats['end_time_str'] = end_dt.strftime('%Y-%m-%d %H:%M')
        
        # Calculate stats for each username
        user_specific_stats = {}
        distinct_users = sorted(list(set(t['username'] for t in transactions)))
        for user in distinct_users:
            user_tx = [t for t in transactions if t['username'] == user]
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
            using_example_data=using_example_data,
            now=datetime.now()
        )
        
        filename = f"transactions_{start_dt.strftime('%Y%m%d%H%M%S')}_{end_dt.strftime('%Y%m%d%H%M%S')}"
        if using_example_data:
            filename += "_example"
        
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

@app.route('/api/dashboard')
def api_dashboard():
    """API endpoint to get dashboard data as JSON for background refresh"""
    time_window = int(request.args.get('time_window', 60))
    num_items = int(request.args.get('num_items', 50))
    
    transactions_for_stats = get_recent_transactions(minutes_ago=time_window, limit=None)
    recent_transactions_for_table = get_recent_transactions(minutes_ago=time_window, limit=num_items)
    
    using_example_data = False
    if not transactions_for_stats:
        all_example_data = generate_example_data()
        transactions_for_stats = all_example_data 
        recent_transactions_for_table = all_example_data[:num_items]
        using_example_data = True
    elif not recent_transactions_for_table and transactions_for_stats:
        recent_transactions_for_table = transactions_for_stats[:num_items]

    dashboard_stats = calculate_dashboard_stats(transactions_for_stats, time_window)
    
    # Convert datetime objects to ISO format strings for JSON serialization
    transactions_json = []
    for t in recent_transactions_for_table:
        t_dict = dict(t)  # Create a copy to avoid modifying the original
        
        # These are already strings, keep as-is
        t_dict['ingress_time_str'] = t.get('ingress_time_str', 'N/A')
        t_dict['egress_time_str'] = t.get('egress_time_str', 'N/A')
        t_dict['transit_time'] = t.get('transit_time', 'N/A')
        
        # Convert datetime objects to ISO strings
        if 'ingress_time' in t_dict and isinstance(t_dict['ingress_time'], datetime):
            t_dict['ingress_time'] = t_dict['ingress_time'].isoformat()
        if 'egress_time' in t_dict and isinstance(t_dict['egress_time'], datetime):
            t_dict['egress_time'] = t_dict['egress_time'].isoformat()
            
        transactions_json.append(t_dict)
    
    return jsonify({
        'stats': dashboard_stats,
        'transactions': transactions_json,
        'using_example_data': using_example_data,
        'time_window': time_window,
        'num_items': num_items,
        'timestamp': datetime.now().isoformat()  # Add timestamp for debugging/audit
    })

@app.route('/api/usernames')
def api_usernames():
    """API endpoint to get unique usernames for dropdowns"""
    usernames = get_unique_usernames()
    
    if not usernames:
        # If DB fails, provide some example usernames
        usernames = ["user_alpha", "user_beta", "user_gamma"]
    
    return jsonify({
        'usernames': usernames
    })

if __name__ == '__main__':
    app.run(debug=True) 