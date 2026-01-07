/**
 * E-Claim Downloader Web UI - Frontend JavaScript
 */

// State
let pollingInterval = null;

/**
 * Trigger download and start polling for status
 */
async function triggerDownload() {
    const button = document.getElementById('trigger-btn');
    const buttonText = document.getElementById('trigger-text');

    // Disable button
    button.disabled = true;
    buttonText.textContent = 'Starting...';

    try {
        const response = await fetch('/download/trigger', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            showToast('Download started successfully!', 'success');
            buttonText.textContent = 'Running...';

            // Start polling for status
            startStatusPolling();
        } else {
            showToast(data.error || 'Failed to start download', 'error');
            button.disabled = false;
            buttonText.textContent = 'Trigger Download';
        }
    } catch (error) {
        console.error('Error triggering download:', error);
        showToast('Error starting download', 'error');
        button.disabled = false;
        buttonText.textContent = 'Trigger Download';
    }
}

/**
 * Start polling download status
 */
function startStatusPolling() {
    // Clear any existing interval
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }

    // Poll every 5 seconds
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch('/download/status');
            const status = await response.json();

            updateStatusUI(status);

            if (!status.running) {
                // Download completed
                clearInterval(pollingInterval);
                pollingInterval = null;

                showToast('Download completed!', 'success');

                // Reset button
                const button = document.getElementById('trigger-btn');
                const buttonText = document.getElementById('trigger-text');
                button.disabled = false;
                buttonText.textContent = 'Trigger Download';

                // Refresh page after 2 seconds
                setTimeout(() => {
                    location.reload();
                }, 2000);
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }, 5000);
}

/**
 * Update UI based on download status
 */
function updateStatusUI(status) {
    const button = document.getElementById('trigger-btn');
    const buttonText = document.getElementById('trigger-text');

    if (status.running) {
        button.disabled = true;
        buttonText.textContent = 'Running...';
    } else {
        button.disabled = false;
        buttonText.textContent = 'Trigger Download';
    }
}

/**
 * Delete file with confirmation
 */
async function deleteFile(filename) {
    // Confirm deletion
    if (!confirm(`Are you sure you want to delete "${filename}"?\n\nThis action cannot be undone.`)) {
        return;
    }

    try {
        const response = await fetch(`/files/${encodeURIComponent(filename)}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('File deleted successfully', 'success');

            // Remove row from UI
            const row = document.querySelector(`[data-file="${filename}"]`);
            if (row) {
                row.style.opacity = '0';
                row.style.transition = 'opacity 0.3s';
                setTimeout(() => {
                    row.remove();

                    // Check if table is now empty
                    const tbody = document.querySelector('tbody');
                    if (tbody && tbody.children.length === 0) {
                        location.reload();
                    }
                }, 300);
            }
        } else {
            showToast(data.message || 'Failed to delete file', 'error');
        }
    } catch (error) {
        console.error('Error deleting file:', error);
        showToast('Error deleting file', 'error');
    }
}

/**
 * Show toast notification (XSS-safe implementation)
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `px-6 py-4 rounded-lg shadow-lg text-white transform transition-all duration-300 translate-x-0 opacity-100`;

    // Set background color based on type
    const colors = {
        'success': 'bg-green-500',
        'error': 'bg-red-500',
        'warning': 'bg-yellow-500',
        'info': 'bg-blue-500'
    };
    toast.classList.add(colors[type] || colors.info);

    // Create content wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'flex items-center space-x-3';

    // Create icon
    const iconWrapper = document.createElement('div');
    iconWrapper.className = 'flex-shrink-0';

    const iconSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    iconSvg.setAttribute('class', 'w-6 h-6');
    iconSvg.setAttribute('fill', 'none');
    iconSvg.setAttribute('stroke', 'currentColor');
    iconSvg.setAttribute('viewBox', '0 0 24 24');

    const iconPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    iconPath.setAttribute('stroke-linecap', 'round');
    iconPath.setAttribute('stroke-linejoin', 'round');
    iconPath.setAttribute('stroke-width', '2');

    // Set path based on type
    const iconPaths = {
        'success': 'M5 13l4 4L19 7',
        'error': 'M6 18L18 6M6 6l12 12',
        'warning': 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
        'info': 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
    };

    iconPath.setAttribute('d', iconPaths[type] || iconPaths.info);
    iconSvg.appendChild(iconPath);
    iconWrapper.appendChild(iconSvg);

    // Create message text (XSS-safe)
    const messageDiv = document.createElement('div');
    messageDiv.className = 'flex-1 font-medium';
    messageDiv.textContent = message; // Safe - uses textContent

    // Create close button
    const closeButton = document.createElement('button');
    closeButton.className = 'flex-shrink-0 ml-4';
    closeButton.onclick = () => toast.remove();

    const closeSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    closeSvg.setAttribute('class', 'w-5 h-5');
    closeSvg.setAttribute('fill', 'none');
    closeSvg.setAttribute('stroke', 'currentColor');
    closeSvg.setAttribute('viewBox', '0 0 24 24');

    const closePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    closePath.setAttribute('stroke-linecap', 'round');
    closePath.setAttribute('stroke-linejoin', 'round');
    closePath.setAttribute('stroke-width', '2');
    closePath.setAttribute('d', 'M6 18L18 6M6 6l12 12');

    closeSvg.appendChild(closePath);
    closeButton.appendChild(closeSvg);

    // Assemble toast
    contentWrapper.appendChild(iconWrapper);
    contentWrapper.appendChild(messageDiv);
    contentWrapper.appendChild(closeButton);
    toast.appendChild(contentWrapper);

    container.appendChild(toast);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

/**
 * Calculate number of months between two dates
 */
function calculateMonthsBetween(m1, y1, m2, y2) {
    return ((y2 - y1) * 12) + (m2 - m1) + 1;
}

/**
 * Download single month
 */
async function downloadSingleMonth() {
    const month = parseInt(document.getElementById('single-month').value);
    const year = parseInt(document.getElementById('single-year').value);

    try {
        const response = await fetch('/download/trigger/single', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ month, year })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`Download started for month ${month}/${year}`, 'success');
            startStatusPolling();
        } else {
            showToast(data.error || 'Failed to start download', 'error');
        }
    } catch (error) {
        console.error('Error starting single month download:', error);
        showToast('Error starting download', 'error');
    }
}

/**
 * Download bulk (date range)
 */
async function downloadBulk() {
    const startMonth = parseInt(document.getElementById('bulk-start-month').value);
    const startYear = parseInt(document.getElementById('bulk-start-year').value);
    const endMonth = parseInt(document.getElementById('bulk-end-month').value);
    const endYear = parseInt(document.getElementById('bulk-end-year').value);

    // Calculate total months
    const totalMonths = calculateMonthsBetween(startMonth, startYear, endMonth, endYear);

    // Confirm with user
    if (!confirm(
        `Download ${totalMonths} month${totalMonths !== 1 ? 's' : ''} of data?\n\n` +
        `From: ${startMonth}/${startYear} to ${endMonth}/${endYear}\n` +
        `Estimated time: ~${totalMonths} minute${totalMonths !== 1 ? 's' : ''}\n\n` +
        `Downloads will be processed sequentially.`
    )) {
        return;
    }

    try {
        const response = await fetch('/download/trigger/bulk', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                start_month: startMonth,
                start_year: startYear,
                end_month: endMonth,
                end_year: endYear
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('Bulk download started!', 'success');
            startBulkProgressPolling();
        } else {
            showToast(data.error || 'Failed to start bulk download', 'error');
        }
    } catch (error) {
        console.error('Error starting bulk download:', error);
        showToast('Error starting bulk download', 'error');
    }
}

/**
 * Start polling bulk download progress
 */
function startBulkProgressPolling() {
    const progressDiv = document.getElementById('bulk-progress');
    const currentMonthSpan = document.getElementById('current-month');
    const progressCountSpan = document.getElementById('progress-count');
    const progressBar = document.getElementById('progress-bar');
    const progressPercentage = document.getElementById('progress-percentage');

    // Show progress display
    progressDiv.classList.remove('hidden');

    // Clear any existing interval
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }

    // Poll every 3 seconds
    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch('/download/bulk/progress');
            const progress = await response.json();

            if (progress.running && progress.current_month) {
                // Update current month
                currentMonthSpan.textContent = `Month ${progress.current_month.month}/${progress.current_month.year}`;

                // Update progress count
                progressCountSpan.textContent = `${progress.completed_months} / ${progress.total_months} months`;

                // Update progress bar
                // Show at least 5% progress when downloading to indicate activity
                const completedPercentage = (progress.completed_months / progress.total_months) * 100;
                const percentage = progress.completed_months === 0 ? 5 : completedPercentage;
                progressBar.style.width = `${percentage}%`;
                progressPercentage.textContent = progress.completed_months === 0
                    ? 'Downloading...'
                    : `${Math.round(completedPercentage)}%`;
            }

            if (progress.status === 'completed') {
                // Bulk download completed
                clearInterval(pollingInterval);
                pollingInterval = null;

                progressBar.style.width = '100%';
                progressPercentage.textContent = '100%';

                showToast('Bulk download completed!', 'success');

                // Refresh page after 2 seconds
                setTimeout(() => {
                    location.reload();
                }, 2000);
            } else if (progress.status === 'failed') {
                // Bulk download failed
                clearInterval(pollingInterval);
                pollingInterval = null;

                showToast('Bulk download failed. Check logs for details.', 'error');

                // Hide progress after 3 seconds
                setTimeout(() => {
                    progressDiv.classList.add('hidden');
                }, 3000);
            }
        } catch (error) {
            console.error('Error polling bulk progress:', error);
        }
    }, 3000);
}

/**
 * Check initial download status on page load
 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/download/status');
        const status = await response.json();

        if (status.running) {
            // Start polling if already running
            startStatusPolling();
        }

        // Check for bulk download in progress
        const bulkResponse = await fetch('/download/bulk/progress');
        const bulkProgress = await bulkResponse.json();

        if (bulkProgress.running && bulkProgress.status === 'running') {
            // Resume bulk progress polling
            startBulkProgressPolling();
        }
    } catch (error) {
        console.error('Error checking initial status:', error);
    }
});
