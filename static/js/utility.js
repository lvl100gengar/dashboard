/**
 * Utility functions for the dashboard application
 */

/**
 * Confirmation dialog for database clearing
 * @returns {boolean} Whether the user confirmed the action
 */
function confirmDatabaseClear() {
    return confirm('WARNING: You are about to permanently delete all transaction records.\n\nThis action cannot be undone. Are you absolutely sure you want to proceed?');
}

/**
 * Format a file size in bytes to a human readable format
 * @param {number} bytes - The file size in bytes
 * @returns {string} Formatted file size string
 */
function formatFileSize(bytes) {
    if (bytes === null || bytes === undefined) return 'N/A';
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    else return (bytes / 1073741824).toFixed(1) + ' GB';
}

/**
 * Extract the time portion from a timestamp
 * @param {string} timestamp - Timestamp in format like "2023-04-15 14:32:45"
 * @returns {string} Time portion or original string if can't parse
 */
function formatTimeOnly(timestamp) {
    if (!timestamp) return 'N/A';
    
    // Try to extract time portion (assuming format like "2023-04-15 14:32:45")
    const timeParts = timestamp.split(' ');
    if (timeParts.length > 1) {
        return timeParts[1]; // Return just the time part
    }
    
    return timestamp; // Return original if can't parse
}

/**
 * Get status color from CSS variables
 * @param {string} status - The status name
 * @returns {string} The CSS color for the status
 */
function getStatusColor(status) {
    const statusKey = status.toLowerCase().replace(/\s+/g, '-');
    const colorVarName = `--status-${statusKey}-color`;
    return getComputedStyle(document.documentElement).getPropertyValue(colorVarName).trim() || '#999999';
}

/**
 * Setup auto-refresh timer 
 * @param {function} fetchFunction - Function to call on refresh
 * @param {string} selectElementId - ID of the select element with refresh rate
 * @returns {number} The timer ID
 */
function setupAutoRefresh(fetchFunction, selectElementId) {
    // Clear any existing timer
    if (window.activeRefreshTimers && window.activeRefreshTimers[selectElementId]) {
        clearInterval(window.activeRefreshTimers[selectElementId]);
    }
    
    // Initialize the refresh timers object if it doesn't exist
    if (!window.activeRefreshTimers) {
        window.activeRefreshTimers = {};
    }
    
    // Get refresh rate from the select element
    const refreshRate = parseInt(document.getElementById(selectElementId).value, 10) * 1000;
    
    // Set up the timer if refresh rate is greater than 0
    if (refreshRate > 0) {
        window.activeRefreshTimers[selectElementId] = setInterval(fetchFunction, refreshRate);
    }
    
    return window.activeRefreshTimers[selectElementId];
}

/**
 * Render a transactions table
 * @param {Array} transactions - Array of transaction objects
 * @param {string} containerId - ID of the container element
 * @param {boolean} includeActions - Whether to include action buttons
 * @returns {void}
 */
function renderTransactionsTable(transactions, containerId, includeActions = true) {
    const container = document.getElementById(containerId);
    
    if (!transactions || transactions.length === 0) {
        container.innerHTML = '<div class="no-data"><i class="fas fa-info-circle"></i> No transactions to display.</div>';
        return;
    }

    let tableHtml = `
        <div class="transactions-table">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>File</th>
                        <th class="numeric">Size</th>
                        <th>Ingress</th>
                        <th>Egress</th>
                        <th class="numeric">Transit</th>
                        <th>Status</th>
                        ${includeActions ? '<th>Actions</th>' : ''}
                    </tr>
                </thead>
                <tbody>`;
    
    transactions.forEach(tx => {
        const statusClass = tx.status ? tx.status.toLowerCase().replace(/_/g, '-') : 'unknown';
        
        // Format times to only show the time portion
        const ingressTime = tx.ingress_time_str ? formatTimeOnly(tx.ingress_time_str) : 'N/A';
        const egressTime = tx.egress_time_str ? formatTimeOnly(tx.egress_time_str) : 'N/A';
        
        tableHtml += `
            <tr>
                <td class="cell-primary">${tx.username || 'N/A'}</td>
                <td class="cell-truncate" title="${tx.file_name || 'N/A'}">${tx.file_name || 'N/A'}</td>
                <td class="cell-primary cell-tabular numeric">${formatFileSize(tx.file_size)}</td>
                <td class="cell-primary cell-tabular">${ingressTime}</td>
                <td class="cell-primary cell-tabular">${egressTime}</td>
                <td class="cell-highlight cell-tabular numeric">${tx.transit_time || 'N/A'}</td>
                <td><span class="status-badge ${statusClass}">${tx.status || 'UNKNOWN'}</span></td>`;

        if (includeActions) {
            tableHtml += `
                <td>
                    <button class="copy-btn" data-transaction='${JSON.stringify(tx).replace(/'/g, "&#39;")}' title="Copy transaction details">
                        <i class="fas fa-copy"></i>
                    </button>
                </td>`;
        }
            
        tableHtml += `</tr>`;
    });
    
    tableHtml += '</tbody></table></div>';
    container.innerHTML = tableHtml;

    // Setup action buttons if they exist
    if (includeActions) {
        setupCopyButtons();
    }
}

/**
 * Setup click handlers for copy buttons
 */
function setupCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const txData = JSON.parse(this.getAttribute('data-transaction'));
            const textToCopy = Object.entries(txData)
                .filter(([key]) => !key.includes('_str') && key !== 'transit_time' && typeof txData[key] !== 'object')
                .map(([key, value]) => `${key}: ${value}`)
                .join('\n');

            navigator.clipboard.writeText(textToCopy).then(() => {
                const originalIcon = this.innerHTML;
                this.innerHTML = '<i class="fas fa-check"></i>';
                setTimeout(() => { this.innerHTML = originalIcon; }, 1000);
            }).catch(err => console.error('Copy failed:', err));
        });
    });
}

/**
 * Create a SVG donut chart for status distribution
 * @param {Object} statusCounts - Object with status names and their counts
 * @param {string} containerId - ID of the container element
 */
function createStatusDonutChart(statusCounts, containerId) {
    const chartContainer = document.getElementById(containerId);
    
    // Calculate total statuses
    const totalStatuses = Object.values(statusCounts).reduce((sum, count) => sum + count, 0);
    
    if (totalStatuses === 0) {
        chartContainer.innerHTML = '<div class="no-data">No transaction data available</div>';
        return;
    }
    
    // Create color mapping
    const cssClassMap = {};
    Object.keys(statusCounts).forEach(status => {
        const statusKey = status.toLowerCase().replace(/\s+/g, '-');
        cssClassMap[status] = `${statusKey}-color`;
    });
    
    // Filter out zero counts and sort by count (highest first)
    const activeStatuses = Object.entries(statusCounts)
        .filter(([_, count]) => count > 0)
        .sort((a, b) => b[1] - a[1]);
    
    // Calculate complete percentage
    const completeCount = statusCounts['Complete'] || 0;
    const completePercentage = totalStatuses > 0 ? 
        ((completeCount / totalStatuses) * 100).toFixed(0) : 0;
    
    // Create HTML for donut segments using SVG
    const donutHTML = `
        <div class="donut-chart-container">
            <svg class="donut-svg" viewBox="0 0 100 100">
                ${createDonutSegments(activeStatuses, totalStatuses)}
            </svg>
            <div class="donut-hole">
                <div class="donut-percentage">${completePercentage}%</div>
                <div class="donut-label">Complete</div>
            </div>
        </div>
        <div class="donut-legend">
            ${createLegendItems(activeStatuses, totalStatuses, cssClassMap)}
        </div>
    `;
    
    chartContainer.innerHTML = donutHTML;
    
    // Add interactivity to legend items
    setupDonutInteractions();
}

/**
 * Create SVG donut segments
 * @param {Array} statuses - Array of [status, count] pairs
 * @param {number} total - Total count of all statuses
 * @returns {string} SVG path elements for the donut segments
 */
function createDonutSegments(statuses, total) {
    let segments = '';
    let cumulativeAngle = 0;
    
    statuses.forEach(([status, count]) => {
        const percentage = (count / total) * 100;
        const color = getStatusColor(status);
        
        if (percentage > 0) {
            // Calculate angles for the arc (SVG uses different angle system)
            const startAngle = cumulativeAngle;
            const angleSize = percentage * 3.6; // 3.6 = 360 / 100
            const endAngle = startAngle + angleSize;
            
            // Convert to radians for calculation
            const startRad = (startAngle - 90) * Math.PI / 180;
            const endRad = (endAngle - 90) * Math.PI / 180;
            
            // Calculate the SVG arc path
            const x1 = 50 + 50 * Math.cos(startRad);
            const y1 = 50 + 50 * Math.sin(startRad);
            const x2 = 50 + 50 * Math.cos(endRad);
            const y2 = 50 + 50 * Math.sin(endRad);
            
            // Determine if the arc should be drawn the long way around
            const largeArcFlag = angleSize > 180 ? 1 : 0;
            
            // Create the donut segment (arc path)
            segments += `
                <path class="donut-segment" 
                      data-status="${status}"
                      d="M 50 50 L ${x1} ${y1} A 50 50 0 ${largeArcFlag} 1 ${x2} ${y2} Z"
                      fill="${color}">
                </path>
            `;
            
            cumulativeAngle += angleSize;
        }
    });
    
    return segments;
}

/**
 * Create legend items HTML
 * @param {Array} statuses - Array of [status, count] pairs
 * @param {number} total - Total count of all statuses
 * @param {Object} cssClassMap - Mapping of status to CSS class names
 * @returns {string} HTML for the legend items
 */
function createLegendItems(statuses, total, cssClassMap) {
    let legendHTML = '';
    
    statuses.forEach(([status, count]) => {
        const percentage = ((count / total) * 100).toFixed(0);
        legendHTML += `
            <div class="legend-item" data-status="${status}">
                <div class="legend-color ${cssClassMap[status]}"></div>
                <span>${status}: ${count} (${percentage}%)</span>
            </div>
        `;
    });
    
    return legendHTML;
}

/**
 * Setup interactivity for donut chart legends
 */
function setupDonutInteractions() {
    // Function to highlight a segment/status
    function highlightStatus(status) {
        if (!status) return;
        
        // Activate the corresponding segment
        document.querySelectorAll('.donut-segment').forEach(segment => {
            if (segment.getAttribute('data-status') === status) {
                segment.classList.add('active');
                segment.style.opacity = 1;
            } else {
                segment.classList.remove('active');
                segment.style.opacity = 0.7;
            }
        });
        
        // Highlight legend item
        document.querySelectorAll('.legend-item').forEach(item => {
            if (item.getAttribute('data-status') === status) {
                item.style.fontWeight = 'bold';
            } else {
                item.style.opacity = '0.6';
            }
        });
    }
    
    // Function to reset highlight
    function resetHighlight() {
        // Reset all segments
        document.querySelectorAll('.donut-segment').forEach(segment => {
            segment.classList.remove('active');
            segment.style.opacity = 1;
        });
        
        // Reset legend items
        document.querySelectorAll('.legend-item').forEach(item => {
            item.style.fontWeight = 'normal';
            item.style.opacity = '1';
        });
    }
    
    // Add interactivity to legend items only
    document.querySelectorAll('.legend-item').forEach(item => {
        const status = item.getAttribute('data-status');
        
        item.addEventListener('mouseenter', () => {
            highlightStatus(status);
        });
        
        item.addEventListener('mouseleave', () => {
            resetHighlight();
        });
    });
} 