/**
 * Dashboard page specific functionality
 */

// State tracking variables
let isRefreshingStats = false;
let lastDataRefreshTime = new Date();

/**
 * Update dashboard with the fetched data
 * @param {Object} data - Dashboard data from the API
 */
function updateDashboardDisplay(data) {
    // Update last refresh time
    lastDataRefreshTime = new Date();
    
    // Update the stat cards
    if (data && data.stats) {
        const stats = data.stats;
        const egressStats = stats.egress || {};
        const generalStats = stats.general || {};
        
        // Update stat cards
        document.getElementById('totalVolumeValue').textContent = 
            egressStats.total_volume_complete_str !== undefined ? egressStats.total_volume_complete_str : '-';
        
        document.getElementById('txPerSecValue').textContent = 
            egressStats.tx_per_sec !== undefined ? egressStats.tx_per_sec : '-';
        
        document.getElementById('avgLatencyValue').textContent = 
            egressStats.avg_transit_time !== undefined ? egressStats.avg_transit_time : '-';
        
        document.getElementById('activeUsersValue').textContent = 
            generalStats.active_users !== undefined ? generalStats.active_users : '-';
    }

    // Get container elements
    const statsContainer = document.getElementById('statsContainer');
    const transactionsTableContainer = document.getElementById('dashboardTransactionsTableContainer');

    // Handle error state if no data
    if (!data || !data.stats) {
        statsContainer.innerHTML = '<div class="error-msg"><i class="fas fa-exclamation-triangle"></i> Error loading statistics data.</div>';
        transactionsTableContainer.innerHTML = '<div class="error-msg"><i class="fas fa-exclamation-triangle"></i> Error loading transactions data.</div>';
        return;
    }

    const stats = data.stats;
    const ingressStats = stats.ingress || {};
    const egressStats = stats.egress || {};

    // Update detailed stats panels
    updateDetailedStatsPanels(statsContainer, ingressStats, egressStats);
    
    // Update transactions table
    renderTransactionsTable(data.transactions_in_window || [], 'dashboardTransactionsTableContainer', false);
}

/**
 * Update the detailed stats panels with data
 * @param {HTMLElement} container - Container element for the panels
 * @param {Object} ingressStats - Ingress statistics
 * @param {Object} egressStats - Egress statistics
 */
function updateDetailedStatsPanels(container, ingressStats, egressStats) {
    container.innerHTML = '';
    
    // Latency panel
    let panelsHTML = `
        <div class="detail-panel">
            <div class="panel-title"><i class="fas fa-stopwatch fa-sm"></i> Latency Metrics</div>
            <div class="stat-item"><strong>Average:</strong> <span class="stat-value">${egressStats.avg_transit_time || '-'}</span></div>
            <div class="stat-item"><strong>Maximum:</strong> <span class="stat-value">${egressStats.max_transit_time || '-'}</span></div>
            <div class="stat-item"><strong>P95:</strong> <span class="stat-value">${egressStats.p95_transit_time || '-'}</span></div>
            <div class="stat-item"><strong>P99:</strong> <span class="stat-value">${egressStats.p99_transit_time || '-'}</span></div>
        </div>
    `;
    
    // Performance panel
    panelsHTML += `
        <div class="detail-panel">
            <div class="panel-title"><i class="fas fa-bolt fa-sm"></i> Performance</div>
            <div class="stat-item"><strong>Throughput:</strong> <span class="stat-value">${egressStats.tx_per_sec ? egressStats.tx_per_sec + ' tx/s' : '-'}</span></div>
            <div class="stat-item"><strong>Data Rate:</strong> <span class="stat-value">${egressStats.data_rate_mbps ? egressStats.data_rate_mbps + ' Mbps' : '-'}</span></div>
            <div class="stat-item"><strong>Total Vol:</strong> <span class="stat-value">${egressStats.total_volume_complete_str || '-'}</span></div>
            <div class="stat-item"><strong>Peak Rate:</strong> <span class="stat-value">${egressStats.peak_tx_per_sec ? egressStats.peak_tx_per_sec + ' tx/s' : '-'}</span></div>
        </div>
    `;
    
    // Status distribution chart
    panelsHTML += `
        <div class="detail-panel">
            <div class="panel-title"><i class="fas fa-chart-pie fa-sm"></i> Status Distribution</div>
            <div class="status-distribution-chart" id="statusDistributionChart"></div>
        </div>
    `;
    
    container.innerHTML = panelsHTML;
    
    // Create the status counts object
    const statusCounts = {
        'Submitted': ingressStats.SUBMITTED || 0,
        'Complete': egressStats.COMPLETE || 0,
        'Bad Request': ingressStats.BAD_REQUEST || 0, 
        'CD Unavailable': ingressStats.CD_UNAVAILABLE || 0,
        'EP Unavailable': egressStats.EP_UNAVAILABLE || 0
    };
    
    // Render the donut chart
    createStatusDonutChart(statusCounts, 'statusDistributionChart');
}

/**
 * Fetch dashboard data from the API
 */
function fetchDashboardData() {
    if (isRefreshingStats) return;
    isRefreshingStats = true;
    
    const timeWindow = document.getElementById('time_window').value;
    const statsContainer = document.getElementById('statsContainer');
    const txTableContainer = document.getElementById('dashboardTransactionsTableContainer');

    // Show loading if needed
    if (!statsContainer.querySelector('.detail-panel')) {
        statsContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
    }
    
    if (!txTableContainer.querySelector('.data-table') && !txTableContainer.querySelector('.no-data')) {
        txTableContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
    }

    fetch(`/api/dashboard-stats?time_window=${timeWindow}`)
        .then(response => {
            if (!response.ok) throw new Error('Network response: ' + response.statusText);
            return response.json();
        })
        .then(data => {
            updateDashboardDisplay(data);
        })
        .catch(error => {
            console.error('Error fetching dashboard data:', error);
            statsContainer.innerHTML = '<div class="error-msg"><i class="fas fa-exclamation-triangle"></i> Error loading statistics</div>';
            txTableContainer.innerHTML = '<div class="error-msg"><i class="fas fa-exclamation-triangle"></i> Error loading transactions</div>';
        })
        .finally(() => {
            isRefreshingStats = false;
        });
}

// Initialize dashboard when the DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    // Initialize 
    lastDataRefreshTime = new Date();
    
    // Fetch initial data
    fetchDashboardData();
    
    // Setup auto-refresh
    setupAutoRefresh(fetchDashboardData, 'refresh_rate');
    
    // Add event listeners
    document.getElementById('time_window').addEventListener('change', fetchDashboardData);
    document.getElementById('refresh_rate').addEventListener('change', function() {
        setupAutoRefresh(fetchDashboardData, 'refresh_rate');
        if (this.value !== "0") fetchDashboardData();
    });
}); 