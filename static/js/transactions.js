/**
 * Transactions live feed page functionality
 */

// State tracking variables
let isRefreshingTransactions = false;
let currentLiveTransactions = []; // Store all fetched transactions for client-side filtering

/**
 * Update the transactions table based on current filters
 */
function updateLiveTransactionTableDisplay() {
    const tableContainer = document.getElementById('liveTableContainer');
    const usernameFilter = document.getElementById('filter_username').value;
    const statusFilter = document.getElementById('filter_status').value;

    // Apply filters
    const filteredTransactions = currentLiveTransactions.filter(tx => {
        const usernameMatch = !usernameFilter || tx.username === usernameFilter;
        const statusMatch = !statusFilter || tx.status === statusFilter;
        return usernameMatch && statusMatch;
    });

    // Handle empty results
    if (filteredTransactions.length === 0) {
        if (currentLiveTransactions.length > 0 && (usernameFilter || statusFilter)) {
            tableContainer.innerHTML = '<div class="no-data"><i class="fas fa-filter"></i> No transactions match the selected filters.</div>';
        } else {
            tableContainer.innerHTML = '<div class="no-data"><i class="fas fa-info-circle"></i> No transactions to display.</div>';
        }
        return;
    }
    
    // Render the transactions
    renderTransactionsTable(filteredTransactions, 'liveTableContainer', true);
}

/**
 * Fetch transactions from the API
 */
function fetchLiveTransactions() {
    if (isRefreshingTransactions) return;
    isRefreshingTransactions = true;

    const numItems = document.getElementById('num_items').value;
    const tableContainer = document.getElementById('liveTableContainer');

    // Show loading state if needed
    if (!tableContainer.querySelector('.data-table')) {
        tableContainer.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading transaction data...</div>';
    }

    // Fetch data from API
    fetch(`/api/transactions-feed?num_items=${numItems}`)
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok: ' + response.statusText);
            return response.json();
        })
        .then(data => {
            currentLiveTransactions = data.transactions || [];
            updateLiveTransactionTableDisplay(); // Update table with potentially filtered data
            document.getElementById('num_items').value = data.num_items; // Reflect actual num_items
        })
        .catch(error => {
            console.error('Error fetching live transactions:', error);
            tableContainer.innerHTML = '<div class="error-msg"><i class="fas fa-exclamation-triangle"></i> Error loading transactions.</div>';
        })
        .finally(() => {
            isRefreshingTransactions = false;
        });
}

/**
 * Load usernames for the filter dropdown
 */
function loadUsernamesForFilter() {
    fetch('/api/usernames')
        .then(response => response.json())
        .then(data => {
            const usernameSelect = document.getElementById('filter_username');
            const currentValue = usernameSelect.value;
            
            // Clear existing options except the first one
            while (usernameSelect.options.length > 1) usernameSelect.remove(1);
            
            // Add new options
            data.usernames.forEach(username => {
                const option = document.createElement('option');
                option.value = username; 
                option.textContent = username;
                usernameSelect.appendChild(option);
            });
            
            // Restore previous selection if possible
            if (currentValue) usernameSelect.value = currentValue;
        })
        .catch(error => console.error('Error loading usernames for filter:', error));
}

// Initialize transactions page when the DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Load initial data
    fetchLiveTransactions();
    loadUsernamesForFilter();
    
    // Setup auto-refresh
    setupAutoRefresh(fetchLiveTransactions, 'live_refresh_rate');

    // Add event listeners
    document.getElementById('num_items').addEventListener('change', fetchLiveTransactions);
    document.getElementById('filter_username').addEventListener('change', updateLiveTransactionTableDisplay);
    document.getElementById('filter_status').addEventListener('change', updateLiveTransactionTableDisplay);
    document.getElementById('live_refresh_rate').addEventListener('change', function(){
        setupAutoRefresh(fetchLiveTransactions, 'live_refresh_rate');
        if (this.value !== "0") fetchLiveTransactions();
    });
}); 