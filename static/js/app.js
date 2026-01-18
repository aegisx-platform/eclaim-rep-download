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
        const response = await fetch('/api/downloads/single', {
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
            const response = await fetch('/api/downloads/status');
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
        const response = await fetch('/api/downloads/month', {
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
    const statementAutoImportSection = document.getElementById('dl-statement-auto-import-section');
    const bulkAutoImportSection = document.getElementById('dl-bulk-auto-import-section');
    const dateRangeSection = document.getElementById('dl-date-range-section');
    const estimateSection = document.getElementById('dl-estimate-section');
    const allMonthsOption = document.getElementById('opt-all-months');
    const monthSelect = document.getElementById('bulk-start-month');
    const repHint = document.getElementById('dl-rep-hint');

    // Hide all type-specific sections first
    if (patientTypeSection) patientTypeSection.classList.add('hidden');
    if (vendorSection) vendorSection.classList.add('hidden');
    if (schemesSection) schemesSection.classList.add('hidden');
    if (statementSchemeSection) statementSchemeSection.classList.add('hidden');
    if (statementAutoImportSection) statementAutoImportSection.classList.add('hidden');
    if (bulkAutoImportSection) bulkAutoImportSection.classList.add('hidden');
    if (repHint) repHint.classList.add('hidden');

    // Show relevant sections based on type
    if (type === 'rep') {
        if (yearMonthSection) yearMonthSection.classList.remove('hidden');
        if (schemesSection) schemesSection.classList.remove('hidden');
        if (dateRangeSection) dateRangeSection.classList.remove('hidden');
        if (estimateSection) estimateSection.classList.remove('hidden');
        if (bulkAutoImportSection) bulkAutoImportSection.classList.remove('hidden');
        if (repHint) repHint.classList.remove('hidden');
        // Hide "All months" option for REP (REP downloads one month at a time)
        if (allMonthsOption) allMonthsOption.classList.add('hidden');
        // Reset to current month if currently "all"
        if (monthSelect && monthSelect.value === '') {
            const currentMonth = new Date().getMonth() + 1;  // 1-12
            monthSelect.value = currentMonth.toString();
        }
    } else if (type === 'statement') {
        if (yearMonthSection) yearMonthSection.classList.remove('hidden');
        if (patientTypeSection) patientTypeSection.classList.remove('hidden');
        if (statementSchemeSection) statementSchemeSection.classList.remove('hidden');
        if (statementAutoImportSection) statementAutoImportSection.classList.remove('hidden');
        if (dateRangeSection) dateRangeSection.classList.add('hidden');
        if (estimateSection) estimateSection.classList.add('hidden');
        // Show "All months" option for Statement and set as default
        if (allMonthsOption) allMonthsOption.classList.remove('hidden');
        if (monthSelect) monthSelect.value = '';  // Default to "ทุกเดือน"
    } else if (type === 'smt') {
        // SMT: Hide year/month, show SMT-specific options
        if (yearMonthSection) yearMonthSection.classList.add('hidden');
        if (vendorSection) vendorSection.classList.remove('hidden');
        if (dateRangeSection) dateRangeSection.classList.add('hidden');
        if (estimateSection) estimateSection.classList.add('hidden');
        // Hide "All months" option for SMT
        if (allMonthsOption) allMonthsOption.classList.add('hidden');
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
    const fiscalYearSelect = document.getElementById('dl-smt-fiscal-year');
    const startDateInput = document.getElementById('dl-smt-start-date');
    const endDateInput = document.getElementById('dl-smt-end-date');

    const now = new Date();
    const currentMonth = now.getMonth() + 1; // 1-12
    const thaiYear = now.getFullYear() + 543;
    const currentFiscalYear = currentMonth >= 10 ? thaiYear + 1 : thaiYear;

    // Populate fiscal year dropdown (from 2565 to current fiscal year)
    // SMT data starts from fiscal year 2565
    const minFiscalYear = 2565;
    if (fiscalYearSelect) {
        fiscalYearSelect.innerHTML = '';
        for (let fy = currentFiscalYear; fy >= minFiscalYear; fy--) {
            const option = document.createElement('option');
            option.value = fy;
            option.textContent = 'ปีงบ ' + fy;
            fiscalYearSelect.appendChild(option);
        }
        // Set current fiscal year as default
        fiscalYearSelect.value = currentFiscalYear;
    }

    // Set date range based on selected fiscal year
    onSmtDownloadFiscalYearChange();

    // Load hospital code from settings for Vendor ID
    loadHospitalCodeForVendor();
}

/**
 * Handle fiscal year change for SMT download form
 */
function onSmtDownloadFiscalYearChange() {
    const fiscalYearSelect = document.getElementById('dl-smt-fiscal-year');
    const startDateInput = document.getElementById('dl-smt-start-date');
    const endDateInput = document.getElementById('dl-smt-end-date');

    if (!fiscalYearSelect || !startDateInput || !endDateInput) return;

    const fiscalYear = parseInt(fiscalYearSelect.value);
    if (!fiscalYear) return;

    const now = new Date();
    const currentMonth = now.getMonth() + 1;
    const thaiYear = now.getFullYear() + 543;
    const currentFiscalYear = currentMonth >= 10 ? thaiYear + 1 : thaiYear;

    // Fiscal year 2569 = Oct 1, 2025 (2568 BE = 2025 CE) to Sep 30, 2026 (2569 BE)
    // Start: Oct 1 of (fiscalYear - 1 - 543) CE
    // End: Sep 30 of (fiscalYear - 543) CE or today if current fiscal year
    const startYearCE = fiscalYear - 1 - 543;
    const endYearCE = fiscalYear - 543;

    const fiscalYearStart = new Date(startYearCE, 9, 1); // Oct 1

    // Format as YYYY-MM-DD for input[type=date]
    const formatDate = (d) => {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    startDateInput.value = formatDate(fiscalYearStart);

    // If current fiscal year, end date = today; otherwise Sep 30
    if (fiscalYear === currentFiscalYear) {
        endDateInput.value = formatDate(now);
    } else {
        const fiscalYearEnd = new Date(endYearCE, 8, 30); // Sep 30
        endDateInput.value = formatDate(fiscalYearEnd);
    }
}

/**
 * Populate year dropdowns with current year as default
 * Used for REP and Statement download forms
 */
function populateYearDropdowns() {
    const currentYear = new Date().getFullYear();
    const currentYearBE = currentYear + 543;
    const currentMonth = new Date().getMonth() + 1;

    // Determine current fiscal year (fiscal year starts in October)
    // If we're in Oct-Dec, fiscal year is next year BE
    // If we're in Jan-Sep, fiscal year is current year BE
    const currentFiscalYear = currentMonth >= 10 ? currentYearBE + 1 : currentYearBE;

    const yearSelects = ['bulk-start-year', 'bulk-end-year', 'smt-fiscal-year'];

    yearSelects.forEach(function(id) {
        const select = document.getElementById(id);
        if (!select) return;

        // Clear existing options
        while (select.firstChild) {
            select.removeChild(select.firstChild);
        }

        // Add years (current fiscal year - 8 years)
        for (let i = 0; i <= 8; i++) {
            const yearBE = currentFiscalYear - i;
            const option = document.createElement('option');
            option.value = yearBE;
            option.textContent = yearBE;
            if (i === 0) option.selected = true;  // Current fiscal year as default
            select.appendChild(option);
        }
    });

    // REP: Default to current month (REP downloads one month at a time, no "ทุกเดือน")
    // Statement: Default to "ทุกเดือน" (all months)
    const monthSelect = document.getElementById('bulk-start-month');
    const allMonthsOption = document.getElementById('opt-all-months');

    // On initial load, REP is default - hide "ทุกเดือน" and set current month
    if (allMonthsOption) allMonthsOption.classList.add('hidden');
    if (monthSelect) monthSelect.value = currentMonth.toString();

    const bulkEndMonth = document.getElementById('bulk-end-month');
    if (bulkEndMonth) bulkEndMonth.value = '';
}

/**
 * Load hospital code from settings and populate Vendor ID field
 * Makes the field readonly since it should come from hospital settings
 */
async function loadHospitalCodeForVendor() {
    try {
        const response = await fetch('/api/settings/hospital-code');
        const result = await response.json();

        const vendorInput = document.getElementById('dl-vendor-id');
        const scheduleVendorInput = document.getElementById('schedule-smt-vendor-id');

        if (result.success && result.hospital_code) {
            const hospitalCode = result.hospital_code;

            // Set vendor ID from hospital code (readonly)
            if (vendorInput) {
                vendorInput.value = hospitalCode;
                vendorInput.readOnly = true;
                vendorInput.classList.add('bg-gray-100', 'cursor-not-allowed');
                vendorInput.placeholder = 'จาก Hospital Settings';
            }

            // Also set schedule vendor ID if exists
            if (scheduleVendorInput) {
                scheduleVendorInput.value = hospitalCode;
                scheduleVendorInput.readOnly = true;
                scheduleVendorInput.classList.add('bg-gray-100', 'cursor-not-allowed');
                scheduleVendorInput.placeholder = 'จาก Hospital Settings';
            }
        } else {
            // No hospital code set - show message
            if (vendorInput) {
                vendorInput.value = '';
                vendorInput.readOnly = true;
                vendorInput.classList.add('bg-gray-100', 'cursor-not-allowed');
                vendorInput.placeholder = 'กรุณาตั้งค่า Hospital Code ที่ Settings';
            }
            if (scheduleVendorInput) {
                scheduleVendorInput.value = '';
                scheduleVendorInput.readOnly = true;
                scheduleVendorInput.classList.add('bg-gray-100', 'cursor-not-allowed');
                scheduleVendorInput.placeholder = 'กรุณาตั้งค่า Hospital Code ที่ Settings';
            }
        }
    } catch (error) {
        console.error('Failed to load hospital code:', error);
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
 * Convert datetime to time ago format in Thai
 * Returns: "X วัน Y ชั่วโมง ที่แล้ว" or "เมื่อสักครู่"
 */
function timeAgo(dateStr) {
    if (!dateStr) return '-';

    const now = new Date();
    const past = new Date(dateStr);
    const diffMs = now - past;

    // If invalid date
    if (isNaN(diffMs)) return '-';

    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    // Less than 1 minute
    if (diffMin < 1) return 'เมื่อสักครู่';

    // Less than 1 hour
    if (diffHour < 1) return `${diffMin} นาที ที่แล้ว`;

    // Less than 1 day
    if (diffDay < 1) return `${diffHour} ชั่วโมง ที่แล้ว`;

    // Less than 7 days
    if (diffDay < 7) {
        const remainHours = diffHour % 24;
        if (remainHours > 0) {
            return `${diffDay} วัน ${remainHours} ชั่วโมง ที่แล้ว`;
        }
        return `${diffDay} วัน ที่แล้ว`;
    }

    // Less than 30 days
    if (diffDay < 30) {
        const weeks = Math.floor(diffDay / 7);
        const remainDays = diffDay % 7;
        if (remainDays > 0) {
            return `${weeks} สัปดาห์ ${remainDays} วัน ที่แล้ว`;
        }
        return `${weeks} สัปดาห์ ที่แล้ว`;
    }

    // More than 30 days - show actual date instead
    return toThaiDateFormat(dateStr);
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

    // Vendor ID is now optional - empty means all in region

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
            // Reload files list based on current page context
            if (typeof loadSmtFiles === 'function' && document.getElementById('smt-files-table')) {
                // Only call loadSmtFiles if on data management page (has smt-files-table element)
                loadSmtFiles();
            } else if (typeof loadUpdateStatus === 'function') {
                // On schedule page, refresh status cards instead
                loadUpdateStatus();
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

    const startMonthVal = document.getElementById('bulk-start-month').value;
    const startYearVal = document.getElementById('bulk-start-year').value;
    const endMonthVal = document.getElementById('bulk-end-month').value;
    const endYearVal = document.getElementById('bulk-end-year').value;
    const autoImport = document.getElementById('bulk-auto-import')?.checked || false;
    const parallelEnabled = document.getElementById('parallel-download')?.checked || false;
    const parallelWorkers = parseInt(document.getElementById('parallel-workers')?.value || '3');

    // Handle "ทุกเดือน" (all months) - download full fiscal year
    // Fiscal year: October to September
    let startMonth, startYear, endMonth, endYear;

    if (startMonthVal === '' || startMonthVal === null) {
        // All months in fiscal year: Oct (year-1) to Sep (year)
        startMonth = 10;  // October
        startYear = parseInt(startYearVal) - 1;  // Previous year BE
        endMonth = 9;  // September
        endYear = parseInt(startYearVal);  // Fiscal year BE
    } else {
        startMonth = parseInt(startMonthVal);
        startYear = parseInt(startYearVal);
        endMonth = endMonthVal ? parseInt(endMonthVal) : startMonth;
        endYear = endYearVal ? parseInt(endYearVal) : startYear;
    }

    // Calculate total months
    const totalMonths = calculateMonthsBetween(startMonth, startYear, endMonth, endYear);

    // Format display text
    const monthNames = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
    const fromText = `${monthNames[startMonth]} ${startYear}`;
    const toText = `${monthNames[endMonth]} ${endYear}`;
    const fiscalYearText = startMonthVal === '' ? ` (ปีงบ ${startYearVal})` : '';

    // Different estimate for parallel vs sequential
    const estimatedTime = parallelEnabled ? Math.ceil(totalMonths / parallelWorkers) : totalMonths;
    const modeText = parallelEnabled ? `Parallel (${parallelWorkers} workers)` : 'Sequential';

    // Confirm with user
    if (!confirm(
        `ดาวน์โหลด ${totalMonths} เดือน${fiscalYearText}\n\n` +
        `จาก: ${fromText} ถึง ${toText}\n` +
        `Mode: ${modeText}\n` +
        `เวลาโดยประมาณ: ~${estimatedTime} นาที\n` +
        `Auto-import: ${autoImport ? 'YES' : 'NO'}\n\n` +
        `ดำเนินการ?`
    )) {
        return;
    }

    // Disable button
    setDownloadButtonState(true, 'กำลังเริ่มต้น...');

    try {
        // Use parallel or sequential based on setting
        if (parallelEnabled) {
            // Parallel download - one month at a time but files in parallel
            const response = await fetch('/api/download/parallel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    month: startMonth,
                    year: startYear,
                    scheme: 'ucs',
                    max_workers: parallelWorkers,
                    auto_import: autoImport
                })
            });

            const data = await response.json();

            if (data.success) {
                showToast(`Parallel download started (${parallelWorkers} workers)!`, 'success');
                setDownloadButtonState(true, `กำลังดาวน์โหลด (${parallelWorkers}x)...`);
                startParallelProgressPolling();
            } else {
                showToast(data.error || 'Failed to start parallel download', 'error');
                setDownloadButtonState(false);
            }
        } else {
            // Sequential download
            const response = await fetch('/api/downloads/bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
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
        }
    } catch (error) {
        console.error('Error starting download:', error);
        showToast('Error starting download', 'error');
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
 * Cancel bulk download in progress
 */
async function cancelBulkDownload() {
    if (!confirm('ยืนยันยกเลิกการดาวน์โหลด?')) {
        return;
    }

    const cancelBtn = document.getElementById('cancel-download-btn');
    if (cancelBtn) {
        cancelBtn.disabled = true;
        cancelBtn.textContent = 'กำลังยกเลิก...';
    }

    try {
        const response = await fetch('/api/downloads/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            showToast('ยกเลิกการดาวน์โหลดแล้ว', 'success');

            // Stop polling
            if (pollingInterval) {
                clearInterval(pollingInterval);
                pollingInterval = null;
            }

            // Hide progress and reset button
            const progressDiv = document.getElementById('bulk-progress');
            if (progressDiv) {
                progressDiv.classList.add('hidden');
            }

            setDownloadButtonState(false);
        } else {
            showToast('เกิดข้อผิดพลาด: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error cancelling download:', error);
        showToast('เกิดข้อผิดพลาด: ' + error.message, 'error');
    } finally {
        if (cancelBtn) {
            cancelBtn.disabled = false;
            cancelBtn.innerHTML = `
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                ยกเลิก
            `;
        }
    }
}

/**
 * Force clean stale/interrupted download and reset UI
 */
async function forceCleanDownload() {
    const cancelBtn = document.getElementById('cancel-download-btn');
    if (cancelBtn) {
        cancelBtn.disabled = true;
        cancelBtn.textContent = 'กำลังล้าง...';
    }

    try {
        const response = await fetch('/api/download/parallel/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ force: true })
        });

        const result = await response.json();

        if (result.success) {
            showToast('ล้างสถานะแล้ว พร้อมดาวน์โหลดใหม่', 'success');

            // Hide progress
            const progressDiv = document.getElementById('bulk-progress');
            if (progressDiv) {
                progressDiv.classList.add('hidden');
            }

            // Reset download button
            setDownloadButtonState(false);
        } else {
            showToast('เกิดข้อผิดพลาด: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error force cleaning download:', error);
        showToast('เกิดข้อผิดพลาด: ' + error.message, 'error');
    } finally {
        if (cancelBtn) {
            cancelBtn.disabled = false;
        }
    }
}

/**
 * Toggle parallel workers section visibility
 */
function toggleParallelWorkersSection() {
    const checkbox = document.getElementById('parallel-download');
    const workersSection = document.getElementById('parallel-workers-section');

    if (checkbox && workersSection) {
        if (checkbox.checked) {
            workersSection.classList.remove('hidden');
        } else {
            workersSection.classList.add('hidden');
        }
    }
}

// Parallel download progress polling interval
let parallelPollingInterval = null;

/**
 * Start polling parallel download progress
 */
function startParallelProgressPolling() {
    const progressDiv = document.getElementById('bulk-progress');
    const currentMonthSpan = document.getElementById('current-month');
    const progressCountSpan = document.getElementById('progress-count');
    const progressBar = document.getElementById('progress-bar');
    const progressPercentage = document.getElementById('progress-percentage');

    // Show progress display
    if (progressDiv) progressDiv.classList.remove('hidden');

    // Clear any existing interval
    if (parallelPollingInterval) {
        clearInterval(parallelPollingInterval);
    }

    // Poll every 2 seconds
    parallelPollingInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/download/parallel/progress');
            const progress = await response.json();

            if (progress.running || progress.status === 'downloading') {
                // Update display
                const completed = progress.completed || 0;
                const skipped = progress.skipped || 0;
                const total = progress.total || 0;
                const failed = progress.failed || 0;
                const workers = progress.workers || [];

                // Calculate processed (completed + skipped)
                const processed = completed + skipped;

                // Update current status
                if (currentMonthSpan) {
                    const workerInfo = workers.length > 0
                        ? workers.map(w => w.name.split('/')[0]).join(', ')
                        : `${Object.keys(progress.current_files || {}).length} active`;
                    currentMonthSpan.textContent = `Parallel: ${workerInfo}`;
                }

                // Update progress count with detailed breakdown
                if (progressCountSpan) {
                    if (skipped > 0 || completed > 0) {
                        progressCountSpan.textContent = `${processed} / ${total} files (${completed} new, ${skipped} skipped)`;
                    } else {
                        progressCountSpan.textContent = `${processed} / ${total} files`;
                    }
                }

                // Update progress bar (use processed instead of completed)
                const percentage = total > 0 ? (processed / total) * 100 : 0;
                if (progressBar) {
                    progressBar.style.width = `${Math.max(percentage, 2)}%`;
                }

                // Update percentage text
                if (progressPercentage) {
                    progressPercentage.textContent = `${processed}/${total}`;
                }

            } else if (progress.status === 'stale' || progress.status === 'interrupted') {
                // Stale or interrupted download - show warning and allow force cancel
                clearInterval(parallelPollingInterval);
                parallelPollingInterval = null;

                const reason = progress.stale_reason || progress.interrupted_reason || 'Process stopped unexpectedly';

                // Update UI to show stale state
                if (currentMonthSpan) {
                    currentMonthSpan.textContent = progress.status === 'stale' ? '⚠️ Process not responding' : '⚠️ Interrupted';
                }

                // Change cancel button to "Clear & Retry"
                const cancelBtn = document.getElementById('cancel-download-btn');
                if (cancelBtn) {
                    cancelBtn.textContent = '🔄 ล้างแล้วลองใหม่';
                    cancelBtn.className = 'px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium rounded-md transition-colors flex items-center gap-2';
                    cancelBtn.onclick = () => forceCleanDownload();
                }

                // Show warning toast
                showToast('⚠️ Download ' + progress.status + ': ' + reason, 'warning');

            } else if (progress.status === 'completed' || progress.status === 'error') {
                // Download completed
                clearInterval(parallelPollingInterval);
                parallelPollingInterval = null;

                if (progress.status === 'completed') {
                    showToast('Parallel download completed! ' + (progress.completed || 0) + ' files', 'success');
                } else {
                    showToast('Download error: ' + (progress.error || 'Unknown'), 'error');
                }

                // Reset button
                setDownloadButtonState(false);

                // Update progress to 100%
                if (progressBar) progressBar.style.width = '100%';
                if (progressPercentage) progressPercentage.textContent = '✓ Done';

                // Hide progress after delay
                setTimeout(() => {
                    if (progressDiv) progressDiv.classList.add('hidden');
                }, 3000);
            }

        } catch (error) {
            console.error('Error polling parallel progress:', error);
        }
    }, 2000);
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
            const response = await fetch('/api/downloads/bulk/progress');
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

        const response = await fetch('/api/imports/rep', {
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
            const response = await fetch('/api/imports/progress');
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
 * Clear download history from database
 * @param {string} downloadType - 'rep', 'stm', 'smt', or 'all'
 */
async function clearDownloadHistory(downloadType) {
    const typeNames = {
        'rep': 'REP',
        'stm': 'Statement',
        'smt': 'SMT',
        'all': 'ทั้งหมด'
    };

    const typeName = typeNames[downloadType] || downloadType;

    if (!confirm(`ต้องการล้าง Download History ของ ${typeName} หรือไม่?\n\nหมายเหตุ: จะไม่ลบไฟล์ที่ดาวน์โหลดไว้แล้ว เพียงแค่ลบประวัติ เพื่อให้ระบบดาวน์โหลดใหม่`)) {
        return;
    }

    try {
        const response = await fetch('/api/download-history/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ download_type: downloadType })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`ล้าง ${typeName} history สำเร็จ: ${result.deleted_count} records`, 'success');
        } else {
            showToast('Error: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

/**
 * Load and display failed downloads
 */
async function loadFailedDownloads() {
    const summaryEl = document.getElementById('failed-downloads-summary');
    const listEl = document.getElementById('failed-downloads-list');

    if (!summaryEl) return;

    summaryEl.textContent = 'กำลังโหลด...';

    try {
        const response = await fetch('/api/download-history/failed');
        const result = await response.json();

        if (!result.success) {
            summaryEl.textContent = 'เกิดข้อผิดพลาด: ' + result.error;
            return;
        }

        const failed = result.failed || [];
        const count = result.count || 0;

        if (count === 0) {
            summaryEl.textContent = 'ไม่มีรายการ download ที่ล้มเหลว';
            summaryEl.className = 'mb-3 p-3 bg-green-50 rounded-lg text-sm text-green-600';
            if (listEl) listEl.classList.add('hidden');
            return;
        }

        // Count by type
        const typeCounts = { rep: 0, stm: 0, smt: 0 };
        failed.forEach(item => {
            if (typeCounts.hasOwnProperty(item.download_type)) {
                typeCounts[item.download_type]++;
            }
        });

        summaryEl.textContent = `พบ ${count} รายการที่ล้มเหลว (REP: ${typeCounts.rep}, STM: ${typeCounts.stm}, SMT: ${typeCounts.smt})`;
        summaryEl.className = 'mb-3 p-3 bg-orange-50 rounded-lg text-sm text-orange-600 font-medium';

        // Build list using safe DOM methods
        if (listEl && failed.length > 0) {
            listEl.replaceChildren(); // Clear existing content

            const container = document.createElement('div');
            container.className = 'divide-y divide-gray-200';

            failed.slice(0, 20).forEach(item => {
                const row = document.createElement('div');
                row.className = 'p-3 hover:bg-gray-50';

                // Header row
                const header = document.createElement('div');
                header.className = 'flex items-center justify-between mb-1';

                const headerLeft = document.createElement('div');
                headerLeft.className = 'flex items-center gap-2';

                const typeSpan = document.createElement('span');
                const typeColors = {
                    rep: 'bg-blue-100 text-blue-800',
                    stm: 'bg-purple-100 text-purple-800',
                    smt: 'bg-green-100 text-green-800'
                };
                typeSpan.className = 'px-2 py-0.5 text-xs rounded ' + (typeColors[item.download_type] || 'bg-gray-100 text-gray-800');
                typeSpan.textContent = item.download_type.toUpperCase();

                const filenameSpan = document.createElement('span');
                filenameSpan.className = 'font-medium text-sm text-gray-800';
                filenameSpan.textContent = item.filename;

                headerLeft.appendChild(typeSpan);
                headerLeft.appendChild(filenameSpan);

                const resetBtn = document.createElement('button');
                resetBtn.className = 'text-xs px-2 py-1 bg-yellow-100 hover:bg-yellow-200 text-yellow-800 rounded';
                resetBtn.textContent = 'Reset';
                resetBtn.onclick = () => resetSingleFailedDownload(item.download_type, item.filename);

                header.appendChild(headerLeft);
                header.appendChild(resetBtn);

                // Error row
                const errorDiv = document.createElement('div');
                errorDiv.className = 'text-xs text-gray-500';
                const errorMsg = item.error_message || 'Unknown error';
                errorDiv.textContent = 'Error: ' + (errorMsg.length > 50 ? errorMsg.substring(0, 50) + '...' : errorMsg);
                errorDiv.title = errorMsg;

                // Info row
                const infoDiv = document.createElement('div');
                infoDiv.className = 'text-xs text-gray-400 mt-1';
                const lastAttempt = item.last_attempt_at ? new Date(item.last_attempt_at).toLocaleString('th-TH') : '-';
                infoDiv.textContent = `Retries: ${item.retry_count || 0} | Last: ${lastAttempt}`;

                row.appendChild(header);
                row.appendChild(errorDiv);
                row.appendChild(infoDiv);
                container.appendChild(row);
            });

            if (failed.length > 20) {
                const moreDiv = document.createElement('div');
                moreDiv.className = 'p-3 text-center text-sm text-gray-500';
                moreDiv.textContent = `... และอีก ${failed.length - 20} รายการ`;
                container.appendChild(moreDiv);
            }

            listEl.appendChild(container);
            listEl.classList.remove('hidden');
        }

    } catch (error) {
        summaryEl.textContent = 'เกิดข้อผิดพลาด: ' + error.message;
        summaryEl.className = 'mb-3 p-3 bg-red-50 rounded-lg text-sm text-red-600';
    }
}

/**
 * Reset all failed downloads for retry
 * @param {string} downloadType - Optional: 'rep', 'stm', or undefined for all
 */
async function resetFailedDownloads(downloadType) {
    const typeNames = {
        'rep': 'REP',
        'stm': 'Statement',
        'smt': 'SMT'
    };
    const typeName = downloadType ? typeNames[downloadType] : 'ทั้งหมด';

    if (!confirm(`Reset failed downloads ของ ${typeName} หรือไม่?\n\nระบบจะเปลี่ยนสถานะเป็น "pending" เพื่อให้ดาวน์โหลดใหม่ได้`)) {
        return;
    }

    try {
        const response = await fetch('/api/download-history/reset-failed', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ download_type: downloadType || null })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Reset สำเร็จ: ${result.count} รายการ`, 'success');
            loadFailedDownloads(); // Refresh list
        } else {
            showToast('Error: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

/**
 * Reset a single failed download for retry
 * @param {string} downloadType - 'rep', 'stm', 'smt'
 * @param {string} filename - Filename to reset
 */
async function resetSingleFailedDownload(downloadType, filename) {
    try {
        const response = await fetch(`/api/download-history/reset/${downloadType}/${encodeURIComponent(filename)}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showToast(`Reset ${filename} สำเร็จ`, 'success');
            loadFailedDownloads(); // Refresh list
        } else {
            showToast('Error: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

/**
 * Delete all failed download records
 * @param {string} downloadType - Optional: 'rep', 'stm', or undefined for all
 */
async function deleteFailedDownloads(downloadType) {
    if (!confirm('ลบรายการ failed downloads ทั้งหมดหรือไม่?\n\nการดำเนินการนี้ไม่สามารถย้อนกลับได้!')) {
        return;
    }

    if (!confirm('ยืนยันอีกครั้ง - ลบ failed downloads ทั้งหมด?')) {
        return;
    }

    try {
        const response = await fetch('/api/download-history/failed', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ download_type: downloadType || null })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`ลบสำเร็จ: ${result.count} รายการ`, 'success');
            loadFailedDownloads(); // Refresh list
        } else {
            showToast('Error: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

/**
 * Check initial download and import status on page load
 */
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Setup parallel download checkbox listener
        const parallelCheckbox = document.getElementById('parallel-download');
        if (parallelCheckbox) {
            parallelCheckbox.addEventListener('change', toggleParallelWorkersSection);
        }

        // Check download status
        const response = await fetch('/api/downloads/status');
        const status = await response.json();

        if (status.running) {
            // Start polling if already running
            startStatusPolling();
        }

        // Check for bulk download in progress
        const bulkResponse = await fetch('/api/downloads/bulk/progress');
        const bulkProgress = await bulkResponse.json();

        if (bulkProgress.running && bulkProgress.status === 'running') {
            // Resume bulk progress polling and disable button
            setDownloadButtonState(true, 'กำลังดาวน์โหลด...');
            startBulkProgressPolling();
        }

        // Check for parallel download in progress
        const parallelResponse = await fetch('/api/download/parallel/progress');
        const parallelProgress = await parallelResponse.json();

        if (parallelProgress.running || parallelProgress.status === 'downloading') {
            // Resume parallel progress polling
            setDownloadButtonState(true, 'กำลังดาวน์โหลด (parallel)...');
            startParallelProgressPolling();
        } else if (parallelProgress.status === 'stale' || parallelProgress.status === 'interrupted') {
            // Show stale/interrupted download recovery UI
            const progressDiv = document.getElementById('bulk-progress');
            const currentMonthSpan = document.getElementById('current-month');
            const progressCountSpan = document.getElementById('progress-count');
            const cancelBtn = document.getElementById('cancel-download-btn');

            if (progressDiv) progressDiv.classList.remove('hidden');
            if (currentMonthSpan) {
                currentMonthSpan.textContent = parallelProgress.status === 'stale'
                    ? '⚠️ Process not responding'
                    : '⚠️ Interrupted by server restart';
            }
            if (progressCountSpan) {
                const completed = parallelProgress.completed || 0;
                const skipped = parallelProgress.skipped || 0;
                const total = parallelProgress.total || 0;
                const processed = completed + skipped;

                if (skipped > 0 || completed > 0) {
                    progressCountSpan.textContent = `${processed} / ${total} files (${completed} new, ${skipped} skipped)`;
                } else {
                    progressCountSpan.textContent = `${processed} / ${total} files`;
                }
            }
            if (cancelBtn) {
                cancelBtn.textContent = '🔄 ล้างแล้วลองใหม่';
                cancelBtn.className = 'px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium rounded-md transition-colors flex items-center gap-2';
                cancelBtn.onclick = () => forceCleanDownload();
            }

            const reason = parallelProgress.stale_reason || parallelProgress.interrupted_reason || 'Download was interrupted';
            showToast('⚠️ พบการดาวน์โหลดค้างอยู่: ' + reason, 'warning');
        }

        // Check for import in progress
        const importResponse = await fetch('/api/imports/progress');
        const importProgress = await importResponse.json();

        if (importProgress.running && importProgress.status === 'running') {
            // Resume import progress polling
            showImportModal();
            startImportProgressPolling();
        }

        // Populate year dropdowns with current year as default
        populateYearDropdowns();
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
        const response = await fetch('/api/downloads/single', {
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
 * Clear all REP files only (not database)
 */
async function clearAllRepFiles() {
    if (!confirm('ยืนยันล้างไฟล์ REP ทั้งหมด?\n\nไฟล์จะถูกลบ แต่ข้อมูลในฐานข้อมูลจะยังคงอยู่')) {
        return;
    }

    try {
        showToast('กำลังล้างไฟล์...', 'info');

        const response = await fetch('/api/rep/clear-files', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            showToast(`ล้างไฟล์สำเร็จ! ลบ ${data.deleted_files} ไฟล์`, 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error clearing REP files:', error);
        showToast('Error clearing files', 'error');
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

let currentSmtFilesPage = 1;

// Store current SMT filter params
let currentSmtFilterParams = null;

/**
 * Load SMT files list and database records
 * @param {URLSearchParams} filterParams - Optional filter parameters
 */
async function loadSmtFiles(filterParams) {
    currentSmtFilterParams = filterParams || null;
    loadSmtFilesPage(1, filterParams);
    // Load fiscal years dropdown
    loadSmtFiscalYears();
    // Also load database records
    loadSmtDbRecords(1);
}

/**
 * Load SMT files with pagination
 * @param {number} page - Page number
 * @param {URLSearchParams} filterParams - Optional filter parameters
 */
async function loadSmtFilesPage(page = 1, filterParams = null) {
    if (page < 1) return;
    currentSmtFilesPage = page;

    // Use stored filter params if not provided
    if (!filterParams && currentSmtFilterParams) {
        filterParams = currentSmtFilterParams;
    }

    try {
        let url = `/api/smt/files?page=${page}&per_page=10`;
        if (filterParams && filterParams.toString()) {
            url += '&' + filterParams.toString();
        }

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            updateSmtStats(data);
            renderSmtFileTable(data.files);

            // Update pagination
            const paginationEl = document.getElementById('smt-files-pagination');
            if (paginationEl && data.total_pages > 1) {
                paginationEl.classList.remove('hidden');
                document.getElementById('smt-files-page').textContent = data.page;
                document.getElementById('smt-files-total-pages').textContent = data.total_pages;

                const prevBtn = document.getElementById('smt-files-prev');
                const nextBtn = document.getElementById('smt-files-next');

                if (prevBtn) prevBtn.disabled = data.page <= 1;
                if (nextBtn) nextBtn.disabled = data.page >= data.total_pages;
            } else if (paginationEl) {
                paginationEl.classList.add('hidden');
            }
        } else {
            // Handle special error: No hospital code configured
            if (data.error_code === 'NO_HOSPITAL_CODE') {
                showSmtNoHospitalCodeWarning(data.error, data.redirect_url);
            } else {
                showToast('Error loading SMT files: ' + data.error, 'error');
            }
        }
    } catch (error) {
        console.error('Error loading SMT files:', error);
        // Check if error response has error_code
        if (error.response) {
            error.response.json().then(data => {
                if (data.error_code === 'NO_HOSPITAL_CODE') {
                    showSmtNoHospitalCodeWarning(data.error, data.redirect_url);
                } else {
                    showToast('Error loading SMT files', 'error');
                }
            }).catch(() => {
                showToast('Error loading SMT files', 'error');
            });
        } else {
            showToast('Error loading SMT files', 'error');
        }
    }
}

/**
 * Show warning when hospital code is not configured
 */
function showSmtNoHospitalCodeWarning(message, redirectUrl) {
    const tableContainer = document.getElementById('smt-files-table');
    if (!tableContainer) return;

    tableContainer.innerHTML = '';

    const warningDiv = document.createElement('div');
    warningDiv.className = 'text-center py-12';

    const iconDiv = document.createElement('div');
    iconDiv.className = 'text-6xl mb-4';
    iconDiv.textContent = '⚠️';

    const title = document.createElement('h3');
    title.className = 'text-xl font-semibold text-gray-800 mb-2';
    title.textContent = 'กรุณาตั้งค่า Hospital Code';

    const desc = document.createElement('p');
    desc.className = 'text-gray-600 mb-6';
    desc.textContent = message || 'ต้องตั้งค่า Hospital Code ก่อนใช้งาน SMT Budget';

    const link = document.createElement('a');
    link.href = redirectUrl || '/settings/hospital';
    link.className = 'inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors';
    link.innerHTML = '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path></svg> ไปตั้งค่า Hospital Code';

    warningDiv.appendChild(iconDiv);
    warningDiv.appendChild(title);
    warningDiv.appendChild(desc);
    warningDiv.appendChild(link);

    tableContainer.appendChild(warningDiv);

    // Also hide stats section
    const statsSection = document.getElementById('smt-stats');
    if (statsSection) {
        statsSection.classList.add('hidden');
    }
}

/**
 * Update SMT stats display
 */
function updateSmtStats(data) {
    // Use stats from API if available (filtered totals), otherwise calculate from page data
    const stats = data.stats || {};
    const total = stats.total !== undefined ? stats.total : (data.total || 0);
    const imported = stats.imported !== undefined ? stats.imported : 0;
    const pending = stats.pending !== undefined ? stats.pending : (total - imported);
    const totalSize = data.total_size || '0 B';
    const filesOnPage = data.files ? data.files.length : 0;

    document.getElementById('smt-stat-total').textContent = total;
    document.getElementById('smt-stat-imported').textContent = imported;
    document.getElementById('smt-stat-pending').textContent = pending;
    document.getElementById('smt-stat-size').textContent = totalSize;
    document.getElementById('smt-file-count').textContent = `แสดง ${filesOnPage} จาก ${total} ไฟล์`;
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

/**
 * Refresh SMT database records
 */
function refreshSmtDbRecords() {
    loadSmtDbRecords(1);
}

/**
 * Clear all SMT database records
 */
async function clearSmtDatabase() {
    if (!confirm('ลบข้อมูล SMT ในฐานข้อมูลทั้งหมด?\n\nการดำเนินการนี้ไม่สามารถย้อนกลับได้!')) return;
    if (!confirm('ยืนยันอีกครั้ง - ลบข้อมูล SMT ทั้งหมด?')) return;

    try {
        showToast('กำลังลบข้อมูล...', 'info');

        const response = await fetch('/api/smt/clear', {
            method: 'POST'
        });

        const data = await response.json();
        if (data.success) {
            showToast(`ลบข้อมูลสำเร็จ: ${data.deleted_count || 0} records`, 'success');
            // Reload SMT data
            loadSmtDbRecords(1);
            loadSmtFiscalYears();
        } else {
            showToast('Error: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('Error clearing database: ' + error.message, 'error');
    }
}

// =============================================================================
// SMT DATABASE RECORDS VIEWER
// =============================================================================

let currentSmtDbPage = 1;

/**
 * Load available fiscal years and populate dropdown
 * Always defaults to current fiscal year
 */
async function loadSmtFiscalYears() {
    const select = document.getElementById('smt-db-fiscal-year');
    const infoEl = document.getElementById('smt-db-available-years');

    // Calculate current fiscal year (Thai: Oct-Sep)
    const now = new Date();
    const thaiYear = now.getFullYear() + 543;
    const currentMonth = now.getMonth() + 1; // 1-12
    const currentFiscalYear = currentMonth >= 10 ? thaiYear + 1 : thaiYear;

    // Always populate with current and past 5 fiscal years
    if (select) {
        // Remove existing options except "ทั้งหมด"
        const options = select.querySelectorAll('option:not([value=""])');
        options.forEach(opt => opt.remove());

        for (let i = 0; i <= 5; i++) {
            const year = currentFiscalYear - i;
            const option = document.createElement('option');
            option.value = year;
            option.textContent = 'ปี ' + year;
            select.appendChild(option);
        }

        // Always default to current fiscal year
        select.value = currentFiscalYear;

        // Trigger change to set date range
        onSmtFiscalYearChange();
    }

    // Fetch available years from database for info display
    try {
        const response = await fetch('/api/smt/fiscal-years');
        const data = await response.json();

        if (data.success && data.fiscal_years && data.fiscal_years.length > 0 && infoEl) {
            infoEl.textContent = 'ปี ' + data.fiscal_years.join(', ');
        } else if (infoEl) {
            infoEl.textContent = 'ยังไม่มีข้อมูล';
        }
    } catch (error) {
        console.error('Error loading fiscal years:', error);
        if (infoEl) infoEl.textContent = '-';
    }
}

/**
 * Handle fiscal year change - auto-fill date range
 */
function onSmtFiscalYearChange() {
    const select = document.getElementById('smt-db-fiscal-year');
    const startInput = document.getElementById('smt-db-start-date');
    const endInput = document.getElementById('smt-db-end-date');

    if (!select || !startInput || !endInput) return;

    const fiscalYear = select.value;

    if (fiscalYear) {
        // Fiscal year 2569 = Oct 2568 to Sep 2569 (BE)
        // Start: 01/10/(fiscalYear-1), End: today or 30/09/fiscalYear (whichever is earlier)
        const fy = parseInt(fiscalYear);
        const startYear = fy - 1;
        const endYear = fy;

        // Calculate current fiscal year
        const now = new Date();
        const thaiYear = now.getFullYear() + 543;
        const currentMonth = now.getMonth() + 1;
        const currentFiscalYear = currentMonth >= 10 ? thaiYear + 1 : thaiYear;

        startInput.value = '01/10/' + startYear;

        // If viewing current fiscal year, end date = today
        // Otherwise, end date = 30/09/fiscalYear
        if (fy === currentFiscalYear) {
            const day = String(now.getDate()).padStart(2, '0');
            const month = String(currentMonth).padStart(2, '0');
            endInput.value = day + '/' + month + '/' + thaiYear;
        } else {
            endInput.value = '30/09/' + endYear;
        }
    } else {
        startInput.value = '';
        endInput.value = '';
    }
}

/**
 * Clear SMT database filter - reset to current fiscal year
 */
function clearSmtDbFilter() {
    const select = document.getElementById('smt-db-fiscal-year');
    const startInput = document.getElementById('smt-db-start-date');
    const endInput = document.getElementById('smt-db-end-date');

    // Reset to current fiscal year (not "ทั้งหมด")
    const now = new Date();
    const thaiYear = now.getFullYear() + 543;
    const currentMonth = now.getMonth() + 1;
    const currentFiscalYear = currentMonth >= 10 ? thaiYear + 1 : thaiYear;

    if (select) select.value = currentFiscalYear;
    onSmtFiscalYearChange(); // This will set the date range

    loadSmtDbRecords(1);
}

/**
 * Load SMT database records with pagination and filters
 */
async function loadSmtDbRecords(page = 1) {
    if (page < 1) return;

    currentSmtDbPage = page;
    const tbody = document.getElementById('smt-db-records');
    const countEl = document.getElementById('smt-db-count');
    const paginationEl = document.getElementById('smt-db-pagination');

    // Get filter values
    const startDate = document.getElementById('smt-db-start-date')?.value || '';
    const endDate = document.getElementById('smt-db-end-date')?.value || '';

    // Show loading
    if (tbody) {
        tbody.textContent = '';
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 7;
        td.className = 'px-4 py-8 text-center text-gray-500';
        td.textContent = 'Loading...';
        tr.appendChild(td);
        tbody.appendChild(tr);
    }

    try {
        let url = `/api/smt/data?page=${page}&per_page=20`;
        if (startDate) url += `&start_date=${encodeURIComponent(startDate)}`;
        if (endDate) url += `&end_date=${encodeURIComponent(endDate)}`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            renderSmtDbRecords(data.data);

            // Update count
            if (countEl) {
                countEl.textContent = `${data.total} records`;
            }

            // Update pagination
            if (paginationEl) {
                paginationEl.classList.remove('hidden');
                document.getElementById('smt-db-page').textContent = data.page;
                document.getElementById('smt-db-total-pages').textContent = data.total_pages;

                const prevBtn = document.getElementById('smt-db-prev');
                const nextBtn = document.getElementById('smt-db-next');

                if (prevBtn) prevBtn.disabled = data.page <= 1;
                if (nextBtn) nextBtn.disabled = data.page >= data.total_pages;
            }
        } else {
            showToast('Error loading records: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error loading SMT records:', error);
        showToast('Error loading records', 'error');
    }
}

/**
 * Render SMT database records table
 */
function renderSmtDbRecords(records) {
    const tbody = document.getElementById('smt-db-records');
    if (!tbody) return;

    tbody.textContent = '';

    if (!records || records.length === 0) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = 8;
        td.className = 'px-4 py-8 text-center text-gray-500';
        td.textContent = 'No records found';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    records.forEach(r => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50';

        // Posting Date (วันที่ Posting)
        const tdDate = document.createElement('td');
        tdDate.className = 'px-3 py-2 text-gray-900';
        tdDate.textContent = r.posting_date || '-';
        tr.appendChild(tdDate);

        // Run Date (วันที่โอน) - Format: YYYY-MM-DD to DD/MM/YYYY BE
        const tdRunDate = document.createElement('td');
        tdRunDate.className = 'px-3 py-2 text-gray-600 text-sm';
        if (r.run_date) {
            // Convert YYYY-MM-DD to DD/MM/YYYY BE
            const parts = r.run_date.split('-');
            if (parts.length === 3) {
                const beYear = parseInt(parts[0]) + 543;
                tdRunDate.textContent = parts[2] + '/' + parts[1] + '/' + beYear;
            } else {
                tdRunDate.textContent = r.run_date;
            }
        } else {
            tdRunDate.textContent = '-';
        }
        tr.appendChild(tdRunDate);

        // Ref Doc
        const tdRef = document.createElement('td');
        tdRef.className = 'px-3 py-2 text-gray-600 font-mono text-xs';
        tdRef.textContent = r.ref_doc_no || '-';
        tr.appendChild(tdRef);

        // Fund Group
        const tdFund = document.createElement('td');
        tdFund.className = 'px-3 py-2 text-gray-600';
        tdFund.textContent = r.fund_group_desc || '-';
        tr.appendChild(tdFund);

        // Amount
        const tdAmount = document.createElement('td');
        tdAmount.className = 'px-3 py-2 text-right text-gray-900';
        tdAmount.textContent = r.amount ? r.amount.toLocaleString('th-TH', {minimumFractionDigits: 2}) : '0.00';
        tr.appendChild(tdAmount);

        // Total
        const tdTotal = document.createElement('td');
        tdTotal.className = 'px-3 py-2 text-right font-medium text-green-700';
        tdTotal.textContent = r.total_amount ? r.total_amount.toLocaleString('th-TH', {minimumFractionDigits: 2}) : '0.00';
        tr.appendChild(tdTotal);

        // Status
        const tdStatus = document.createElement('td');
        tdStatus.className = 'px-3 py-2 text-center';
        const statusSpan = document.createElement('span');
        statusSpan.className = r.payment_status === 'C'
            ? 'px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800'
            : 'px-2 py-0.5 text-xs rounded-full bg-yellow-100 text-yellow-800';
        statusSpan.textContent = r.payment_status || '-';
        tdStatus.appendChild(statusSpan);
        tr.appendChild(tdStatus);

        // Imported date
        const tdImported = document.createElement('td');
        tdImported.className = 'px-3 py-2 text-gray-500 text-xs';
        if (r.created_at) {
            const date = new Date(r.created_at);
            tdImported.textContent = date.toLocaleDateString('th-TH') + ' ' + date.toLocaleTimeString('th-TH', {hour: '2-digit', minute: '2-digit'});
        } else {
            tdImported.textContent = '-';
        }
        tr.appendChild(tdImported);

        tbody.appendChild(tr);
    });
}

// ==================== Alert System Functions ====================

let alertsRefreshInterval = null;

/**
 * Toggle alerts panel visibility
 */
function toggleAlertsPanel() {
    const panel = document.getElementById('alerts-panel');
    if (!panel) return;

    const isHidden = panel.classList.contains('hidden');
    if (isHidden) {
        panel.classList.remove('hidden');
        loadAlerts();
    } else {
        panel.classList.add('hidden');
    }
}

/**
 * Load alerts from API
 */
async function loadAlerts() {
    const list = document.getElementById('alerts-list');
    if (!list) return;

    try {
        const response = await fetch('/api/alerts?limit=20');
        const data = await response.json();

        if (!data.success) {
            list.textContent = '';
            const div = document.createElement('div');
            div.className = 'p-4 text-center text-red-500';
            div.textContent = 'Error loading alerts';
            list.appendChild(div);
            return;
        }

        list.textContent = '';

        if (!data.alerts || data.alerts.length === 0) {
            const div = document.createElement('div');
            div.className = 'p-4 text-center text-gray-500';
            div.textContent = 'No alerts';
            list.appendChild(div);
            return;
        }

        data.alerts.forEach(function(alert) {
            const div = document.createElement('div');
            div.className = 'p-3 border-b hover:bg-gray-50 ' + (alert.is_read ? 'bg-white' : 'bg-blue-50');
            div.id = 'alert-' + alert.id;

            // Severity icon
            const iconMap = {
                'critical': '🔴',
                'warning': '⚠️',
                'info': 'ℹ️'
            };

            const header = document.createElement('div');
            header.className = 'flex items-start justify-between';

            const titleDiv = document.createElement('div');
            titleDiv.className = 'flex items-center gap-2';

            const icon = document.createElement('span');
            icon.textContent = iconMap[alert.severity] || 'ℹ️';
            titleDiv.appendChild(icon);

            const title = document.createElement('span');
            title.className = 'font-medium text-sm text-gray-800';
            title.textContent = alert.title;
            titleDiv.appendChild(title);

            header.appendChild(titleDiv);

            // Dismiss button
            const dismissBtn = document.createElement('button');
            dismissBtn.className = 'text-gray-400 hover:text-gray-600 text-xs';
            dismissBtn.textContent = '✕';
            dismissBtn.onclick = function(e) {
                e.stopPropagation();
                dismissAlert(alert.id);
            };
            header.appendChild(dismissBtn);

            div.appendChild(header);

            // Message
            if (alert.message) {
                const msg = document.createElement('p');
                msg.className = 'text-xs text-gray-600 mt-1 ml-6';
                msg.textContent = alert.message.length > 100 ? alert.message.substring(0, 100) + '...' : alert.message;
                div.appendChild(msg);
            }

            // Time
            const time = document.createElement('p');
            time.className = 'text-xs text-gray-400 mt-1 ml-6';
            if (alert.created_at) {
                const date = new Date(alert.created_at);
                time.textContent = date.toLocaleString('th-TH');
            }
            div.appendChild(time);

            // Click to mark as read
            div.onclick = function() {
                markAlertRead(alert.id);
            };

            list.appendChild(div);
        });

    } catch (error) {
        console.error('Error loading alerts:', error);
        list.textContent = '';
        const div = document.createElement('div');
        div.className = 'p-4 text-center text-red-500';
        div.textContent = 'Error loading alerts';
        list.appendChild(div);
    }
}

/**
 * Update alerts badge count
 */
async function updateAlertsBadge() {
    const badge = document.getElementById('alerts-badge');
    if (!badge) return;

    try {
        const response = await fetch('/api/alerts/unread-count');
        const data = await response.json();

        if (data.success) {
            const count = data.count || 0;
            badge.textContent = count > 99 ? '99+' : count;
            if (count > 0) {
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    } catch (error) {
        console.error('Error updating alerts badge:', error);
    }
}

/**
 * Mark single alert as read
 */
async function markAlertRead(alertId) {
    try {
        await fetch('/api/alerts/' + alertId + '/read', { method: 'POST' });
        // Update UI
        const alertEl = document.getElementById('alert-' + alertId);
        if (alertEl) {
            alertEl.classList.remove('bg-blue-50');
            alertEl.classList.add('bg-white');
        }
        updateAlertsBadge();
    } catch (error) {
        console.error('Error marking alert as read:', error);
    }
}

/**
 * Mark all alerts as read
 */
async function markAllAlertsRead() {
    try {
        await fetch('/api/alerts/read-all', { method: 'POST' });
        loadAlerts();
        updateAlertsBadge();
    } catch (error) {
        console.error('Error marking all alerts as read:', error);
    }
}

/**
 * Dismiss single alert
 */
async function dismissAlert(alertId) {
    try {
        await fetch('/api/alerts/' + alertId + '/dismiss', { method: 'POST' });
        // Remove from UI
        const alertEl = document.getElementById('alert-' + alertId);
        if (alertEl) {
            alertEl.remove();
        }
        updateAlertsBadge();
    } catch (error) {
        console.error('Error dismissing alert:', error);
    }
}

/**
 * Dismiss all alerts
 */
async function dismissAllAlerts() {
    if (!confirm('Dismiss all alerts?')) return;

    try {
        await fetch('/api/alerts/dismiss-all', { method: 'POST' });
        loadAlerts();
        updateAlertsBadge();
    } catch (error) {
        console.error('Error dismissing all alerts:', error);
    }
}

/**
 * Start polling for new alerts
 */
function startAlertsPolling() {
    // Update immediately
    updateAlertsBadge();

    // Poll every 60 seconds
    if (alertsRefreshInterval) {
        clearInterval(alertsRefreshInterval);
    }
    alertsRefreshInterval = setInterval(updateAlertsBadge, 60000);
}

// Close alerts panel when clicking outside
document.addEventListener('click', function(event) {
    const container = document.getElementById('alerts-container');
    const panel = document.getElementById('alerts-panel');
    if (container && panel && !container.contains(event.target)) {
        panel.classList.add('hidden');
    }
});

// Start alerts polling on page load
document.addEventListener('DOMContentLoaded', function() {
    startAlertsPolling();
});
