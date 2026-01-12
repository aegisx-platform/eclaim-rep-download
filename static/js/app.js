/**
 * E-Claim Downloader Web UI - Frontend JavaScript
 */

// State
let pollingInterval = null;
let importPollingInterval = null;

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
    const autoImport = document.getElementById('single-auto-import')?.checked || false;

    try {
        const response = await fetch('/download/trigger/single', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ month, year, auto_import: autoImport })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`Download started for month ${month}/${year}${autoImport ? ' (with auto-import)' : ''}`, 'success');
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
 * Current download type state
 */
let currentDownloadType = 'rep';

/**
 * Switch download type (REP, Statement, SMT)
 */
function switchDownloadType(type) {
    currentDownloadType = type;

    // Update button styles
    document.querySelectorAll('.dl-type-btn').forEach(btn => {
        btn.classList.remove('bg-blue-600', 'text-white');
        btn.classList.add('text-gray-600', 'hover:bg-gray-200');
    });
    const activeBtn = document.getElementById(`dl-type-${type}`);
    if (activeBtn) {
        activeBtn.classList.remove('text-gray-600', 'hover:bg-gray-200');
        activeBtn.classList.add('bg-blue-600', 'text-white');
    }

    // Update source info
    const sourceLabel = document.getElementById('dl-source-label');
    const sourceLink = document.getElementById('dl-source-link');
    const formTitle = document.getElementById('dl-form-title');

    const typeInfo = {
        rep: {
            label: 'REP (Request for Electronic Payment)',
            link: 'eclaim.nhso.go.th',
            url: 'https://eclaim.nhso.go.th',
            title: 'ดาวน์โหลดข้อมูล REP'
        },
        statement: {
            label: 'Statement (ใบแจ้งยอดสรุปรายการเบิกจ่าย)',
            link: 'eclaim.nhso.go.th',
            url: 'https://eclaim.nhso.go.th',
            title: 'ดาวน์โหลด Statement'
        },
        smt: {
            label: 'SMT Budget (งบประมาณ Smart Money Transfer)',
            link: 'smt.nhso.go.th',
            url: 'https://smt.nhso.go.th',
            title: 'ดาวน์โหลด SMT Budget'
        }
    };

    const info = typeInfo[type];
    if (sourceLabel) sourceLabel.textContent = info.label;
    if (sourceLink) {
        sourceLink.textContent = info.link;
        sourceLink.href = info.url;
    }
    if (formTitle) formTitle.textContent = info.title;

    // Show/hide type-specific sections
    const yearMonthSection = document.getElementById('dl-year-month-section');
    const patientTypeSection = document.getElementById('dl-patient-type-section');
    const vendorSection = document.getElementById('dl-vendor-section');
    const schemesSection = document.getElementById('dl-schemes-section');
    const statementSchemeSection = document.getElementById('dl-statement-scheme-section');
    const dateRangeSection = document.getElementById('dl-date-range-section');
    const estimateSection = document.getElementById('dl-estimate-section');

    // Hide all type-specific sections first
    if (patientTypeSection) patientTypeSection.classList.add('hidden');
    if (vendorSection) vendorSection.classList.add('hidden');
    if (schemesSection) schemesSection.classList.add('hidden');
    if (statementSchemeSection) statementSchemeSection.classList.add('hidden');

    // Show relevant sections based on type
    if (type === 'rep') {
        if (yearMonthSection) yearMonthSection.classList.remove('hidden');
        if (schemesSection) schemesSection.classList.remove('hidden');
        if (dateRangeSection) dateRangeSection.classList.remove('hidden');
        if (estimateSection) estimateSection.classList.remove('hidden');
    } else if (type === 'statement') {
        if (yearMonthSection) yearMonthSection.classList.remove('hidden');
        if (patientTypeSection) patientTypeSection.classList.remove('hidden');
        if (statementSchemeSection) statementSchemeSection.classList.remove('hidden');
        if (dateRangeSection) dateRangeSection.classList.add('hidden');
        if (estimateSection) estimateSection.classList.add('hidden');
    } else if (type === 'smt') {
        // SMT: Hide year/month, show SMT-specific options
        if (yearMonthSection) yearMonthSection.classList.add('hidden');
        if (vendorSection) vendorSection.classList.remove('hidden');
        if (dateRangeSection) dateRangeSection.classList.add('hidden');
        if (estimateSection) estimateSection.classList.add('hidden');
        // Initialize SMT date fields with defaults
        initSmtDateFields();
    }
}

/**
 * Download based on selected type
 */
async function downloadByType() {
    if (currentDownloadType === 'rep') {
        downloadBulk();
    } else if (currentDownloadType === 'statement') {
        downloadStatement();
    } else if (currentDownloadType === 'smt') {
        downloadSmtBudget();
    }
}

/**
 * Initialize SMT date fields with default values (fiscal year start to today)
 * Thai fiscal year: October 1st to September 30th
 */
function initSmtDateFields() {
    const startDateInput = document.getElementById('dl-smt-start-date');
    const endDateInput = document.getElementById('dl-smt-end-date');

    if (startDateInput && endDateInput) {
        const now = new Date();

        // Calculate fiscal year start (October 1st)
        // If current month >= October (10), fiscal year started this year
        // If current month < October, fiscal year started last year
        let fiscalYearStart;
        if (now.getMonth() >= 9) { // October = month 9 (0-indexed)
            fiscalYearStart = new Date(now.getFullYear(), 9, 1); // Oct 1 this year
        } else {
            fiscalYearStart = new Date(now.getFullYear() - 1, 9, 1); // Oct 1 last year
        }

        // Format as YYYY-MM-DD for input[type=date] using local date (not UTC)
        const formatDate = (d) => {
            const year = d.getFullYear();
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };

        startDateInput.value = formatDate(fiscalYearStart);
        endDateInput.value = formatDate(now);
    }
}

/**
 * Convert date to Thai Buddhist Era format (dd/mm/yyyy)
 */
function toThaiDateFormat(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const beYear = date.getFullYear() + 543;
    return `${day}/${month}/${beYear}`;
}

/**
 * Download SMT Budget with progress indicator
 */
async function downloadSmtBudget() {
    const downloadBtn = document.getElementById('download-btn');
    const downloadBtnText = document.getElementById('download-btn-text');

    const vendorId = document.getElementById('dl-vendor-id')?.value || '';
    const startDate = document.getElementById('dl-smt-start-date')?.value || '';
    const endDate = document.getElementById('dl-smt-end-date')?.value || '';
    const scheme = document.getElementById('dl-smt-scheme')?.value || '';
    const smtType = document.getElementById('dl-smt-type')?.value || '';
    const autoImport = document.getElementById('dl-smt-auto-import')?.checked || false;

    if (!vendorId) {
        showToast('กรุณาระบุ Vendor ID', 'error');
        return;
    }

    // Check if already downloading
    if (downloadBtn && downloadBtn.disabled) {
        showToast('กำลังดาวน์โหลดอยู่ กรุณารอให้เสร็จก่อน', 'warning');
        return;
    }

    // Convert dates to Thai format (dd/mm/yyyy BE)
    const thaiStartDate = toThaiDateFormat(startDate);
    const thaiEndDate = toThaiDateFormat(endDate);

    // Show loading state
    const originalText = downloadBtnText?.textContent || 'ดาวน์โหลดข้อมูล';

    if (downloadBtn) {
        downloadBtn.disabled = true;
        downloadBtn.classList.add('opacity-75', 'cursor-wait');
    }
    if (downloadBtnText) {
        downloadBtnText.textContent = autoImport ? '⏳ กำลังดึงข้อมูลและนำเข้า...' : '⏳ กำลังดึงข้อมูล...';
    }

    try {
        const response = await fetch('/api/smt/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                vendor_id: vendorId,
                start_date: thaiStartDate,
                end_date: thaiEndDate,
                budget_source: scheme,
                budget_type: smtType,
                auto_import: autoImport
            })
        });

        const result = await response.json();
        if (result.success) {
            showToast(result.message || 'Download completed', 'success');
            // Reload SMT files list if on SMT tab
            if (typeof loadSmtFiles === 'function') {
                loadSmtFiles();
            }
        } else {
            showToast(result.error || 'Download failed', 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    } finally {
        // Restore button state
        if (downloadBtn) {
            downloadBtn.disabled = false;
            downloadBtn.classList.remove('opacity-75', 'cursor-wait');
        }
        if (downloadBtnText) {
            downloadBtnText.textContent = originalText;
        }
    }
}

/**
 * Download bulk (date range)
 */
async function downloadBulk() {
    const downloadBtn = document.getElementById('download-btn');
    const downloadBtnText = document.getElementById('download-btn-text');

    // Check if already downloading
    if (downloadBtn && downloadBtn.disabled) {
        showToast('กำลังดาวน์โหลดอยู่ กรุณารอให้เสร็จก่อน', 'warning');
        return;
    }

    const startMonth = parseInt(document.getElementById('bulk-start-month').value);
    const startYear = parseInt(document.getElementById('bulk-start-year').value);
    const endMonth = parseInt(document.getElementById('bulk-end-month').value);
    const endYear = parseInt(document.getElementById('bulk-end-year').value);
    const autoImport = document.getElementById('bulk-auto-import')?.checked || false;

    // Calculate total months
    const totalMonths = calculateMonthsBetween(startMonth, startYear, endMonth, endYear);

    // Confirm with user
    if (!confirm(
        `Download ${totalMonths} month${totalMonths !== 1 ? 's' : ''} of data?\n\n` +
        `From: ${startMonth}/${startYear} to ${endMonth}/${endYear}\n` +
        `Estimated time: ~${totalMonths} minute${totalMonths !== 1 ? 's' : ''}\n` +
        `Auto-import: ${autoImport ? 'YES' : 'NO'}\n\n` +
        `Downloads will be processed sequentially.`
    )) {
        return;
    }

    // Disable button
    setDownloadButtonState(true, 'กำลังเริ่มต้น...');

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
                end_year: endYear,
                auto_import: autoImport
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`Bulk download started!${autoImport ? ' (with auto-import)' : ''}`, 'success');
            setDownloadButtonState(true, 'กำลังดาวน์โหลด...');
            startBulkProgressPolling();
        } else {
            showToast(data.error || 'Failed to start bulk download', 'error');
            setDownloadButtonState(false);
        }
    } catch (error) {
        console.error('Error starting bulk download:', error);
        showToast('Error starting bulk download', 'error');
        setDownloadButtonState(false);
    }
}

/**
 * Set download button state (enabled/disabled)
 */
function setDownloadButtonState(disabled, text = null) {
    const downloadBtn = document.getElementById('download-btn');
    const downloadBtnText = document.getElementById('download-btn-text');

    if (downloadBtn) {
        downloadBtn.disabled = disabled;
    }
    if (downloadBtnText) {
        downloadBtnText.textContent = text || 'ดาวน์โหลดข้อมูล';
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
                // Get iteration progress (X/Y files)
                const currentIdx = progress.iteration_current_idx || 0;
                const totalFiles = progress.iteration_total_files || 0;
                const fileCount = progress.current_files || 0;

                // Format file progress string
                let fileProgressText;
                if (totalFiles > 0) {
                    fileProgressText = `${currentIdx}/${totalFiles} files`;
                } else if (fileCount > 0) {
                    fileProgressText = `${fileCount} files`;
                } else {
                    fileProgressText = 'loading...';
                }

                // Update current month with file progress
                currentMonthSpan.textContent = `Month ${progress.current_month.month}/${progress.current_month.year} (${fileProgressText})`;

                // Update progress count
                progressCountSpan.textContent = `${progress.completed_months} / ${progress.total_months} months`;

                // Calculate progress percentage based on iterations and current file
                const totalIterations = progress.total_iterations || 1;
                const completedIterations = progress.completed_iterations || 0;
                let percentage;
                if (totalFiles > 0 && currentIdx > 0) {
                    // Include partial progress of current iteration
                    const iterationProgress = currentIdx / totalFiles;
                    percentage = ((completedIterations + iterationProgress) / totalIterations) * 100;
                } else {
                    percentage = (completedIterations / totalIterations) * 100;
                }
                // Show at least 2% to indicate activity
                percentage = Math.max(percentage, progress.status === 'running' ? 2 : 0);
                progressBar.style.width = `${percentage}%`;

                // Show file progress or percentage
                if (totalFiles > 0) {
                    progressPercentage.textContent = `${currentIdx}/${totalFiles}`;
                } else if (completedIterations === 0) {
                    progressPercentage.textContent = 'Starting...';
                } else {
                    progressPercentage.textContent = `${Math.round(percentage)}%`;
                }
            }

            if (progress.status === 'completed') {
                // Bulk download completed
                clearInterval(pollingInterval);
                pollingInterval = null;

                progressBar.style.width = '100%';
                progressPercentage.textContent = '100%';

                showToast('Bulk download completed!', 'success');
                setDownloadButtonState(false);

                // Refresh page after 2 seconds
                setTimeout(() => {
                    location.reload();
                }, 2000);
            } else if (progress.status === 'failed') {
                // Bulk download failed
                clearInterval(pollingInterval);
                pollingInterval = null;

                showToast('Bulk download failed. Check logs for details.', 'error');
                setDownloadButtonState(false);

                // Hide progress after 3 seconds
                setTimeout(() => {
                    progressDiv.classList.add('hidden');
                }, 3000);
            } else if (!progress.running) {
                // Download stopped unexpectedly
                clearInterval(pollingInterval);
                pollingInterval = null;
                setDownloadButtonState(false);
            }
        } catch (error) {
            console.error('Error polling bulk progress:', error);
        }
    }, 3000);
}

/**
 * Import single file to database
 */
async function importFile(filename) {
    // Confirm import
    if (!confirm(`Import "${filename}" to database?\n\nThis will parse the file and store records in the database.`)) {
        return;
    }

    try {
        // Show import progress modal
        showImportModal();

        const response = await fetch(`/import/file/${encodeURIComponent(filename)}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`Import started for ${filename}`, 'success');

            // Start polling import progress
            startImportProgressPolling();
        } else {
            closeImportModal();
            showToast(data.error || 'Failed to start import', 'error');
        }
    } catch (error) {
        console.error('Error importing file:', error);
        closeImportModal();
        showToast('Error starting import', 'error');
    }
}

/**
 * Import all files that haven't been imported yet
 */
async function importAllFiles() {
    // Confirm bulk import
    const pendingCount = document.querySelectorAll('[data-import-status="pending"]').length;

    if (!confirm(
        `Import all ${pendingCount} pending files to database?\n\n` +
        `This may take several minutes depending on file size and count.\n\n` +
        `Progress will be shown in real-time.`
    )) {
        return;
    }

    try {
        // Show import progress modal
        showImportModal();

        const response = await fetch('/import/all', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast('Import started!', 'success');

            // Start polling import progress
            startImportProgressPolling();
        } else {
            closeImportModal();
            showToast(data.error || 'Failed to start import', 'error');
        }
    } catch (error) {
        console.error('Error importing all files:', error);
        closeImportModal();
        showToast('Error starting import', 'error');
    }
}

/**
 * Show import progress modal
 */
function showImportModal() {
    const modal = document.getElementById('import-progress-modal');
    if (modal) {
        modal.classList.remove('hidden');

        // Reset progress
        document.getElementById('import-progress-bar').style.width = '0%';
        document.getElementById('import-progress-percentage').textContent = '0%';
        document.getElementById('import-progress-text').textContent = 'Preparing...';
        document.getElementById('import-file-count').textContent = '0 / 0 files';
        document.getElementById('import-record-count').textContent = '0 records imported';
        document.getElementById('import-current-file').textContent = '-';
    }
}

/**
 * Close import progress modal
 */
function closeImportModal() {
    const modal = document.getElementById('import-progress-modal');
    if (modal) {
        modal.classList.add('hidden');
    }

    // Stop polling
    if (importPollingInterval) {
        clearInterval(importPollingInterval);
        importPollingInterval = null;
    }
}

/**
 * Start polling import progress
 */
function startImportProgressPolling() {
    // Clear any existing interval
    if (importPollingInterval) {
        clearInterval(importPollingInterval);
    }

    // Poll every 2 seconds
    importPollingInterval = setInterval(async () => {
        try {
            const response = await fetch('/import/progress');
            const progress = await response.json();

            updateImportProgressUI(progress);

            if (!progress.running || progress.status === 'completed') {
                // Import completed
                clearInterval(importPollingInterval);
                importPollingInterval = null;

                // Update to 100%
                document.getElementById('import-progress-bar').style.width = '100%';
                document.getElementById('import-progress-percentage').textContent = '100%';
                document.getElementById('import-progress-text').textContent = 'Import completed!';

                showToast('Import completed successfully!', 'success');

                // Close modal and refresh after 2 seconds
                setTimeout(() => {
                    closeImportModal();
                    location.reload();
                }, 2000);
            }
        } catch (error) {
            console.error('Error polling import progress:', error);
        }
    }, 2000);
}

/**
 * Update import progress UI
 */
function updateImportProgressUI(progress) {
    if (!progress || !progress.running) return;

    const completed = progress.completed_files || 0;
    const total = progress.total_files || 1;
    const percentage = Math.round((completed / total) * 100);

    // Update progress bar
    document.getElementById('import-progress-bar').style.width = `${percentage}%`;
    document.getElementById('import-progress-percentage').textContent = `${percentage}%`;

    // Update file count
    document.getElementById('import-file-count').textContent = `${completed} / ${total} files`;

    // Update record count
    const records = progress.total_records_imported || 0;
    document.getElementById('import-record-count').textContent = `${records.toLocaleString()} records imported`;

    // Update current file
    const currentFile = progress.current_file || '-';
    document.getElementById('import-current-file').textContent = currentFile;

    // Update progress text
    if (progress.current_file) {
        document.getElementById('import-progress-text').textContent = `Importing file ${completed + 1} of ${total}...`;
    } else {
        document.getElementById('import-progress-text').textContent = 'Processing...';
    }
}

/**
 * Filter files by import status
 */
function filterFiles(status) {
    const rows = document.querySelectorAll('.file-row');
    const filterButtons = document.querySelectorAll('.filter-btn');

    // Update button styles
    filterButtons.forEach(btn => {
        btn.classList.remove('bg-blue-600', 'text-white');
        btn.classList.add('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
    });

    const activeButton = document.getElementById(`filter-${status}`);
    if (activeButton) {
        activeButton.classList.remove('bg-gray-200', 'text-gray-700', 'hover:bg-gray-300');
        activeButton.classList.add('bg-blue-600', 'text-white');
    }

    // Filter rows
    rows.forEach(row => {
        const rowStatus = row.getAttribute('data-import-status');

        if (status === 'all') {
            row.style.display = '';
        } else if (status === rowStatus) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

/**
 * Check initial download and import status on page load
 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Check download status
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
            // Resume bulk progress polling and disable button
            setDownloadButtonState(true, 'กำลังดาวน์โหลด...');
            startBulkProgressPolling();
        }

        // Check for import in progress
        const importResponse = await fetch('/import/progress');
        const importProgress = await importResponse.json();

        if (importProgress.running && importProgress.status === 'running') {
            // Resume import progress polling
            showImportModal();
            startImportProgressPolling();
        }
    } catch (error) {
        console.error('Error checking initial status:', error);
    }
});

/**
 * Toggle download menu dropdown
 */
function toggleDownloadMenu() {
    const menu = document.getElementById('download-menu');
    menu.classList.toggle('hidden');
    // Close analytics menu if open
    const analyticsMenu = document.getElementById('analytics-menu');
    if (analyticsMenu) analyticsMenu.classList.add('hidden');
}

/**
 * Toggle analytics dropdown menu
 */
function toggleAnalyticsMenu() {
    const menu = document.getElementById('analytics-menu');
    if (menu) menu.classList.toggle('hidden');
    // Close download menu if open
    const downloadMenu = document.getElementById('download-menu');
    if (downloadMenu) downloadMenu.classList.add('hidden');
}

/**
 * Close dropdown menus when clicking outside
 */
document.addEventListener('click', (event) => {
    // Download menu
    const downloadContainer = document.getElementById('download-menu-container');
    const downloadMenu = document.getElementById('download-menu');

    if (downloadContainer && downloadMenu && !downloadContainer.contains(event.target)) {
        downloadMenu.classList.add('hidden');
    }

    // Analytics menu
    const analyticsContainer = document.getElementById('analytics-menu-container');
    const analyticsMenu = document.getElementById('analytics-menu');

    if (analyticsContainer && analyticsMenu && !analyticsContainer.contains(event.target)) {
        analyticsMenu.classList.add('hidden');
    }
});

/**
 * Start download with optional auto-import
 */
async function startDownload() {
    const autoImport = document.getElementById('auto-import-checkbox').checked;
    const menu = document.getElementById('download-menu');

    // Close menu
    menu.classList.add('hidden');

    // Show log viewer
    if (!isLogViewerExpanded) {
        toggleLogViewer();
    }

    try {
        const response = await fetch('/download/trigger', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ auto_import: autoImport })
        });

        const data = await response.json();

        if (data.success) {
            const message = autoImport
                ? 'Download started with auto-import enabled!'
                : 'Download started!';
            showToast(message, 'success');
            startStatusPolling();
        } else {
            showToast(data.error || 'Failed to start download', 'error');
        }
    } catch (error) {
        console.error('Error starting download:', error);
        showToast('Error starting download', 'error');
    }
}

/**
 * Clear all data (files, history, database) with confirmation
 */
async function clearAllData() {
    // Triple confirmation for safety
    const confirm1 = confirm(
        '⚠️ WARNING: This will DELETE ALL data!\n\n' +
        'This action will:\n' +
        '• Delete all downloaded files\n' +
        '• Clear all import history\n' +
        '• Remove all database records\n\n' +
        'This CANNOT be undone!\n\n' +
        'Are you sure you want to continue?'
    );

    if (!confirm1) {
        return;
    }

    // Second confirmation
    const confirm2 = confirm(
        '🚨 FINAL WARNING!\n\n' +
        'You are about to permanently delete ALL data.\n\n' +
        'Type YES in the next prompt to confirm.'
    );

    if (!confirm2) {
        return;
    }

    // Third confirmation with text input
    const userInput = prompt(
        'Please type "DELETE ALL" to confirm (case-sensitive):'
    );

    if (userInput !== 'DELETE ALL') {
        showToast('Cancellation confirmed - no data was deleted', 'info');
        return;
    }

    try {
        showToast('Clearing all data...', 'info');

        const response = await fetch('/api/clear-all', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast(
                `All data cleared successfully! Deleted ${data.deleted_files} files.`,
                'success'
            );

            // Reload page after 2 seconds
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error clearing data:', error);
        showToast('Error clearing data', 'error');
    }
}

// =============================================================================
// SMT FILE MANAGEMENT
// =============================================================================

/**
 * Load SMT files list
 */
async function loadSmtFiles() {
    try {
        const response = await fetch('/api/smt/files');
        const data = await response.json();

        if (data.success) {
            updateSmtStats(data);
            renderSmtFileTable(data.files);
        } else {
            showToast('Error loading SMT files: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error loading SMT files:', error);
        showToast('Error loading SMT files', 'error');
    }
}

/**
 * Update SMT stats display
 */
function updateSmtStats(data) {
    const total = data.files ? data.files.length : 0;
    const imported = data.files ? data.files.filter(f => f.imported).length : 0;
    const pending = total - imported;
    const totalSize = data.total_size || '0 B';

    document.getElementById('smt-stat-total').textContent = total;
    document.getElementById('smt-stat-imported').textContent = imported;
    document.getElementById('smt-stat-pending').textContent = pending;
    document.getElementById('smt-stat-size').textContent = totalSize;
    document.getElementById('smt-file-count').textContent = `แสดง ${total} ไฟล์`;
    document.getElementById('smt-pending-count').textContent = pending;

    // Show/hide buttons
    const importAllBtn = document.getElementById('smt-import-all-btn');
    const clearBtn = document.getElementById('smt-clear-btn');

    if (importAllBtn) {
        if (pending > 0) {
            importAllBtn.classList.remove('hidden');
        } else {
            importAllBtn.classList.add('hidden');
        }
    }
    if (clearBtn) {
        if (total > 0) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
    }
}

/**
 * Render SMT file table using DOM methods for safety
 */
function renderSmtFileTable(files) {
    const tbody = document.getElementById('smt-file-list');
    if (!tbody) return;

    // Clear existing content
    tbody.textContent = '';

    if (!files || files.length === 0) {
        const emptyRow = document.createElement('tr');
        const emptyCell = document.createElement('td');
        emptyCell.setAttribute('colspan', '5');
        emptyCell.className = 'px-4 py-8 text-center text-gray-500';
        emptyCell.textContent = 'ไม่พบไฟล์ SMT - ไปที่ Download tab เพื่อดาวน์โหลดข้อมูล';
        emptyRow.appendChild(emptyCell);
        tbody.appendChild(emptyRow);
        return;
    }

    files.forEach(file => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50';

        // Filename cell
        const filenameCell = document.createElement('td');
        filenameCell.className = 'px-4 py-3';
        const filenameDiv = document.createElement('div');
        filenameDiv.className = 'flex items-center';
        const dot = document.createElement('span');
        dot.className = 'w-2 h-2 bg-green-500 rounded-full mr-2';
        const nameSpan = document.createElement('span');
        nameSpan.className = 'text-sm font-medium text-gray-900';
        nameSpan.textContent = file.filename;
        filenameDiv.appendChild(dot);
        filenameDiv.appendChild(nameSpan);
        filenameCell.appendChild(filenameDiv);
        row.appendChild(filenameCell);

        // Date cell
        const dateCell = document.createElement('td');
        dateCell.className = 'px-4 py-3 text-sm text-gray-500';
        dateCell.textContent = file.modified || '-';
        row.appendChild(dateCell);

        // Size cell
        const sizeCell = document.createElement('td');
        sizeCell.className = 'px-4 py-3 text-sm text-gray-500';
        sizeCell.textContent = file.size || '-';
        row.appendChild(sizeCell);

        // Status cell
        const statusCell = document.createElement('td');
        statusCell.className = 'px-4 py-3';
        const statusBadge = document.createElement('span');
        statusBadge.className = file.imported
            ? 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800'
            : 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800';
        statusBadge.textContent = file.imported ? 'Imported' : 'Pending';
        statusCell.appendChild(statusBadge);
        row.appendChild(statusCell);

        // Actions cell
        const actionsCell = document.createElement('td');
        actionsCell.className = 'px-4 py-3 text-right';
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'flex justify-end gap-2';

        if (!file.imported) {
            const importBtn = document.createElement('button');
            importBtn.className = 'text-blue-600 hover:text-blue-800 text-sm font-medium';
            importBtn.textContent = 'Import';
            importBtn.onclick = () => importSmtFile(file.filename);
            actionsDiv.appendChild(importBtn);
        }

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'text-red-600 hover:text-red-800 text-sm font-medium';
        deleteBtn.textContent = 'Delete';
        deleteBtn.onclick = () => deleteSmtFile(file.filename);
        actionsDiv.appendChild(deleteBtn);

        actionsCell.appendChild(actionsDiv);
        row.appendChild(actionsCell);

        tbody.appendChild(row);
    });
}

/**
 * Import single SMT file
 */
async function importSmtFile(filename) {
    if (!confirm(`นำเข้าไฟล์ ${filename}?`)) return;

    try {
        showToast(`กำลังนำเข้า ${filename}...`, 'info');
        const response = await fetch(`/api/smt/import/${encodeURIComponent(filename)}`, {
            method: 'POST'
        });

        const data = await response.json();
        if (data.success) {
            showToast(data.message || 'Import successful', 'success');
            loadSmtFiles();
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error importing file', 'error');
    }
}

/**
 * Import all pending SMT files
 */
async function importAllSmtFiles() {
    if (!confirm('นำเข้าไฟล์ SMT ทั้งหมดที่รอนำเข้า?')) return;

    try {
        showToast('กำลังนำเข้าไฟล์ทั้งหมด...', 'info');
        const response = await fetch('/api/smt/import-all', {
            method: 'POST'
        });

        const data = await response.json();
        if (data.success) {
            showToast(data.message || 'All files imported', 'success');
            loadSmtFiles();
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error importing files', 'error');
    }
}

/**
 * Delete single SMT file
 */
async function deleteSmtFile(filename) {
    if (!confirm(`ลบไฟล์ ${filename}?`)) return;

    try {
        const response = await fetch(`/api/smt/delete/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });

        const data = await response.json();
        if (data.success) {
            showToast('File deleted', 'success');
            loadSmtFiles();
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error deleting file', 'error');
    }
}

/**
 * Clear all SMT files and database records
 */
async function clearAllSmtFiles() {
    if (!confirm('ลบไฟล์ SMT และข้อมูลในฐานข้อมูลทั้งหมด?\n\nการดำเนินการนี้ไม่สามารถย้อนกลับได้!')) return;
    if (!confirm('ยืนยันอีกครั้ง - ลบไฟล์ SMT และข้อมูลในฐานข้อมูลทั้งหมด?')) return;

    try {
        // 1. Delete database records first
        const dbResponse = await fetch('/api/smt/clear', {
            method: 'POST'
        });
        const dbData = await dbResponse.json();

        // 2. Delete CSV files
        const filesResponse = await fetch('/api/smt/clear-files', {
            method: 'POST'
        });
        const filesData = await filesResponse.json();

        if (dbData.success && filesData.success) {
            showToast(`ลบข้อมูลสำเร็จ: ${dbData.deleted_count || 0} records, ${filesData.deleted_count || 0} files`, 'success');
            loadSmtFiles();
        } else {
            const errors = [];
            if (!dbData.success) errors.push('Database: ' + dbData.error);
            if (!filesData.success) errors.push('Files: ' + filesData.error);
            showToast('Error: ' + errors.join(', '), 'error');
        }
    } catch (error) {
        showToast('Error clearing data: ' + error.message, 'error');
    }
}
