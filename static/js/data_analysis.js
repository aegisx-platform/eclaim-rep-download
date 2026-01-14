// Data Analysis Page JavaScript

let currentAnalysisTab = 'summary';

// Initialize fiscal year dropdown
function initFiscalYearDropdown() {
    const select = document.getElementById('summary-fiscal-year');
    if (!select) return;

    // Clear existing options
    select.replaceChildren();

    // Add "All" option
    const allOption = document.createElement('option');
    allOption.value = '';
    allOption.textContent = 'ทุกปี';
    select.appendChild(allOption);

    // Get current Thai Buddhist year
    const currentYear = new Date().getFullYear();
    const currentYearBE = currentYear + 543;
    const currentMonth = new Date().getMonth() + 1;

    // If we're past October, current fiscal year is next year BE
    // e.g., Nov 2024 (BE 2567) is in FY 2568
    const currentFiscalYear = currentMonth >= 10 ? currentYearBE + 1 : currentYearBE;

    // Add fiscal years (current and 5 years back)
    for (let i = 0; i <= 5; i++) {
        const year = currentFiscalYear - i;
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year + ' (' + (year - 543) + ')';
        select.appendChild(option);
    }
}

// Reset filters
function resetSummaryFilters() {
    const fySelect = document.getElementById('summary-fiscal-year');
    const startMonth = document.getElementById('summary-start-month');
    const endMonth = document.getElementById('summary-end-month');
    const scheme = document.getElementById('summary-scheme');
    const serviceType = document.getElementById('summary-service-type');

    // Reset to current fiscal year (index 1), not "all"
    if (fySelect && fySelect.options.length > 1) fySelect.selectedIndex = 1;
    if (startMonth) startMonth.value = '';
    if (endMonth) endMonth.value = '';
    if (scheme) scheme.value = '';
    if (serviceType) serviceType.value = '';

    loadSummary();
}

function switchAnalysisTab(tab) {
    currentAnalysisTab = tab;

    // Update tab buttons
    document.querySelectorAll('.analysis-tab-btn').forEach(btn => {
        btn.classList.remove('border-blue-600', 'text-blue-600');
        btn.classList.add('border-transparent', 'text-gray-500');
    });
    const activeTab = document.getElementById('tab-' + tab);
    if (activeTab) {
        activeTab.classList.remove('border-transparent', 'text-gray-500');
        activeTab.classList.add('border-blue-600', 'text-blue-600');
    }

    // Show/hide content
    document.querySelectorAll('.analysis-tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    const activeContent = document.getElementById('content-' + tab);
    if (activeContent) {
        activeContent.classList.remove('hidden');
    }

    // Load data for tab
    if (tab === 'summary') loadSummary();
    // New tabs don't auto-load - user clicks the button to load
}

async function loadSummary() {
    try {
        // Get filter values
        const fiscalYear = document.getElementById('summary-fiscal-year')?.value || '';
        const startMonth = document.getElementById('summary-start-month')?.value || '';
        const endMonth = document.getElementById('summary-end-month')?.value || '';
        const scheme = document.getElementById('summary-scheme')?.value || '';
        const serviceType = document.getElementById('summary-service-type')?.value || '';

        // Build URL with filters
        let url = '/api/analysis/summary';
        const params = [];
        if (fiscalYear) params.push('fiscal_year=' + fiscalYear);
        if (startMonth) params.push('start_month=' + startMonth);
        if (endMonth) params.push('end_month=' + endMonth);
        if (scheme) params.push('scheme=' + scheme);
        if (serviceType) params.push('service_type=' + serviceType);
        if (params.length > 0) url += '?' + params.join('&');

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            // REP - use formatCurrencyLarge for main display (no decimals)
            setText('rep-total-records', formatNumber(data.rep.total_records || 0));
            setText('rep-total-amount', formatCurrencyLarge(data.rep.total_amount || 0));
            setText('rep-files-count', data.rep.files_count || '0');

            // Statement
            setText('stm-total-records', formatNumber(data.stm.total_records || 0));
            setText('stm-total-amount', formatCurrencyLarge(data.stm.total_amount || 0));
            setText('stm-files-count', data.stm.files_count || '0');

            // SMT
            setText('smt-total-records', formatNumber(data.smt.total_records || 0));
            setText('smt-total-amount', formatCurrencyLarge(data.smt.total_amount || 0));
            setText('smt-files-count', data.smt.files_count || '0');

            // Update filter info text
            updateFilterInfo(data.filters);
        }
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

function updateFilterInfo(filters) {
    const infoEl = document.getElementById('summary-filter-info');
    if (!infoEl) return;

    if (!filters || (!filters.fiscal_year && !filters.start_month && !filters.end_month)) {
        infoEl.textContent = 'แสดงข้อมูลทั้งหมด';
        return;
    }

    const parts = [];
    if (filters.fiscal_year) {
        parts.push('ปีงบ ' + filters.fiscal_year);
    }
    if (filters.start_month && filters.end_month) {
        const monthNames = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
        parts.push(monthNames[filters.start_month] + ' - ' + monthNames[filters.end_month]);
    }

    infoEl.textContent = 'กรองตาม: ' + parts.join(', ');
}

function onReconGroupByChange() {
    const groupBy = document.getElementById('recon-group-by').value;
    const headerRep = document.getElementById('recon-header-rep');
    const headerTran = document.getElementById('recon-header-tran');
    const searchLabel = document.getElementById('recon-search-label');
    const searchInput = document.getElementById('recon-rep-no');

    if (groupBy === 'tran_id') {
        headerRep.classList.add('hidden');
        headerTran.classList.remove('hidden');
        if (searchLabel) searchLabel.textContent = 'TRAN ID / REP No';
        if (searchInput) searchInput.placeholder = 'เช่น 733078003';
    } else {
        headerRep.classList.remove('hidden');
        headerTran.classList.add('hidden');
        if (searchLabel) searchLabel.textContent = 'REP No';
        if (searchInput) searchInput.placeholder = 'เช่น 681000006';
    }
}

async function loadReconciliation() {
    const tbody = document.getElementById('recon-table-body');
    const groupBy = document.getElementById('recon-group-by').value;
    const colSpan = groupBy === 'tran_id' ? 8 : 7;

    tbody.textContent = '';
    const loadingRow = document.createElement('tr');
    const loadingCell = document.createElement('td');
    loadingCell.colSpan = colSpan;
    loadingCell.className = 'px-4 py-8 text-center text-gray-500';
    loadingCell.textContent = 'กำลังโหลด...';
    loadingRow.appendChild(loadingCell);
    tbody.appendChild(loadingRow);

    try {
        const repNo = document.getElementById('recon-rep-no').value;
        const status = document.getElementById('recon-status').value;
        const dateFrom = document.getElementById('recon-date-from')?.value || '';
        const dateTo = document.getElementById('recon-date-to')?.value || '';
        const diffThreshold = document.getElementById('recon-diff-threshold')?.value || '0';
        const hasError = document.getElementById('recon-has-error')?.checked ? 'true' : '';

        let url = '/api/analysis/reconciliation?rep_no=' + encodeURIComponent(repNo) +
                    '&status=' + encodeURIComponent(status) +
                    '&group_by=' + encodeURIComponent(groupBy);
        if (dateFrom) url += '&date_from=' + encodeURIComponent(dateFrom);
        if (dateTo) url += '&date_to=' + encodeURIComponent(dateTo);
        if (diffThreshold && parseFloat(diffThreshold) > 0) url += '&diff_threshold=' + encodeURIComponent(diffThreshold);
        if (hasError) url += '&has_error=' + hasError;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            // Update stats
            setText('recon-matched', formatNumber(data.stats.matched || 0));
            setText('recon-rep-only', formatNumber(data.stats.rep_only || 0));
            setText('recon-stm-only', formatNumber(data.stats.stm_only || 0));
            setText('recon-diff', formatNumber(data.stats.diff_amount || 0));

            // Clear and render table
            tbody.textContent = '';

            if (data.records && data.records.length > 0) {
                data.records.forEach(r => {
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';

                    if (groupBy === 'tran_id') {
                        // Transaction mode columns
                        row.appendChild(createCell(r.tran_id || '-'));
                        row.appendChild(createCell(r.rep_no || '-'));
                        row.appendChild(createCell(r.hn || '-'));
                        row.appendChild(createCell(r.patient_name || '-'));
                    } else {
                        // REP No mode columns
                        row.appendChild(createCell(r.rep_no || '-'));
                        row.appendChild(createCell(formatNumber(r.rep_count), 'text-right'));
                        row.appendChild(createCell(formatNumber(r.stm_count), 'text-right'));
                    }

                    row.appendChild(createCell(formatCurrency(r.rep_amount), 'text-right'));
                    row.appendChild(createCell(formatCurrency(r.stm_amount), 'text-right'));

                    const diffCell = createCell(formatCurrency(r.diff), 'text-right');
                    if (r.diff !== 0) diffCell.classList.add('text-red-600');
                    row.appendChild(diffCell);

                    const statusCell = document.createElement('td');
                    statusCell.className = 'px-4 py-2 text-sm text-center';
                    const statusSpan = document.createElement('span');
                    statusSpan.className = 'px-2 py-1 rounded text-xs ' + getStatusClass(r.status);
                    statusSpan.textContent = r.status;
                    statusCell.appendChild(statusSpan);
                    row.appendChild(statusCell);

                    tbody.appendChild(row);
                });
            } else {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = colSpan;
                emptyCell.className = 'px-4 py-8 text-center text-gray-500';
                emptyCell.textContent = 'ไม่พบข้อมูล';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
            }
        }
    } catch (error) {
        console.error('Error loading reconciliation:', error);
        tbody.textContent = '';
        const errorRow = document.createElement('tr');
        const errorCell = document.createElement('td');
        errorCell.colSpan = colSpan;
        errorCell.className = 'px-4 py-8 text-center text-red-500';
        errorCell.textContent = 'เกิดข้อผิดพลาด';
        errorRow.appendChild(errorCell);
        tbody.appendChild(errorRow);
    }
}

function exportReconciliation() {
    const groupBy = document.getElementById('recon-group-by').value;
    const repNo = document.getElementById('recon-rep-no').value;
    const status = document.getElementById('recon-status').value;
    const dateFrom = document.getElementById('recon-date-from')?.value || '';
    const dateTo = document.getElementById('recon-date-to')?.value || '';
    const diffThreshold = document.getElementById('recon-diff-threshold')?.value || '0';
    const hasError = document.getElementById('recon-has-error')?.checked ? 'true' : '';

    let url = '/api/analysis/export?rep_no=' + encodeURIComponent(repNo) +
                '&status=' + encodeURIComponent(status) +
                '&group_by=' + encodeURIComponent(groupBy);
    if (dateFrom) url += '&date_from=' + encodeURIComponent(dateFrom);
    if (dateTo) url += '&date_to=' + encodeURIComponent(dateTo);
    if (diffThreshold && parseFloat(diffThreshold) > 0) url += '&diff_threshold=' + encodeURIComponent(diffThreshold);
    if (hasError) url += '&has_error=' + hasError;

    // Trigger download
    window.location.href = url;
}

async function searchTransaction() {
    const query = document.getElementById('search-query').value.trim();
    if (!query) {
        alert('กรุณาใส่ค่าที่ต้องการค้นหา');
        return;
    }

    const resultsDiv = document.getElementById('search-results');
    resultsDiv.textContent = '';
    const loadingP = document.createElement('p');
    loadingP.className = 'text-center text-gray-500 py-8';
    loadingP.textContent = 'กำลังค้นหา...';
    resultsDiv.appendChild(loadingP);

    try {
        const response = await fetch('/api/analysis/search?q=' + encodeURIComponent(query));
        const data = await response.json();

        resultsDiv.textContent = '';

        if (data.success) {
            // REP Results
            if (data.rep && data.rep.length > 0) {
                resultsDiv.appendChild(createSearchResultTable('REP Files', 'blue', data.rep, ['tran_id', 'rep_no', 'hn', 'name', 'dateadm', 'reimb_nhso']));
            }

            // Statement Results
            if (data.stm && data.stm.length > 0) {
                resultsDiv.appendChild(createSearchResultTable('Statement', 'purple', data.stm, ['tran_id', 'rep_no', 'hn', 'patient_name', 'date_admit', 'paid_after_deduction']));
            }

            // SMT Results
            if (data.smt && data.smt.length > 0) {
                resultsDiv.appendChild(createSearchResultTable('SMT Budget', 'green', data.smt, ['posting_date', 'ref_doc_no', 'fund_group_desc', 'total_amount', 'payment_status']));
            }

            if (!data.rep?.length && !data.stm?.length && !data.smt?.length) {
                const noDataP = document.createElement('p');
                noDataP.className = 'text-center text-gray-500 py-8';
                noDataP.textContent = 'ไม่พบข้อมูลที่ตรงกับคำค้นหา';
                resultsDiv.appendChild(noDataP);
            }
        }
    } catch (error) {
        console.error('Error searching:', error);
        resultsDiv.textContent = '';
        const errorP = document.createElement('p');
        errorP.className = 'text-center text-red-500 py-8';
        errorP.textContent = 'เกิดข้อผิดพลาดในการค้นหา';
        resultsDiv.appendChild(errorP);
    }
}

function createSearchResultTable(title, color, data, columns) {
    const container = document.createElement('div');
    container.className = 'mb-6';

    const header = document.createElement('h4');
    header.className = 'font-semibold text-' + color + '-700 mb-2';
    header.textContent = title + ' (' + data.length + ' records)';
    container.appendChild(header);

    const tableWrapper = document.createElement('div');
    tableWrapper.className = 'border rounded-lg overflow-hidden';

    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-gray-200';

    const thead = document.createElement('thead');
    thead.className = 'bg-' + color + '-50';
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.className = 'px-3 py-2 text-left text-xs font-medium text-' + color + '-700';
        th.textContent = col.toUpperCase();
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    tbody.className = 'bg-white divide-y divide-gray-200';
    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-gray-50';
        columns.forEach(col => {
            const td = document.createElement('td');
            td.className = 'px-3 py-2 text-sm';
            let value = row[col];
            if (col.includes('amount') || col.includes('reimb')) {
                value = formatCurrency(value);
                td.className += ' text-right';
            }
            td.textContent = value || '-';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    tableWrapper.appendChild(table);
    container.appendChild(tableWrapper);

    return container;
}

async function loadFileList() {
    const dataType = document.getElementById('viewer-data-type').value;
    const fileSelect = document.getElementById('viewer-file');

    // Clear options
    while (fileSelect.options.length > 1) {
        fileSelect.remove(1);
    }

    if (!dataType) return;

    try {
        const response = await fetch('/api/analysis/files?type=' + encodeURIComponent(dataType));
        const data = await response.json();

        if (data.success && data.files) {
            data.files.forEach(f => {
                const option = document.createElement('option');
                option.value = f.id;
                option.textContent = f.filename + ' (' + f.record_count + ' records)';
                fileSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading file list:', error);
    }
}

async function loadFileItems() {
    const dataType = document.getElementById('viewer-data-type').value;
    const fileId = document.getElementById('viewer-file').value;

    if (!dataType || !fileId) return;

    const tbody = document.getElementById('viewer-table-body');
    tbody.textContent = '';
    const loadingRow = document.createElement('tr');
    const loadingCell = document.createElement('td');
    loadingCell.className = 'px-4 py-8 text-center text-gray-500';
    loadingCell.textContent = 'กำลังโหลด...';
    loadingRow.appendChild(loadingCell);
    tbody.appendChild(loadingRow);

    try {
        const response = await fetch('/api/analysis/file-items?type=' + encodeURIComponent(dataType) + '&file_id=' + encodeURIComponent(fileId));
        const data = await response.json();

        if (data.success) {
            // Update table header
            const thead = document.getElementById('viewer-table-head');
            thead.textContent = '';
            const headerRow = document.createElement('tr');
            data.columns.forEach(col => {
                const th = document.createElement('th');
                th.className = 'px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase';
                th.textContent = col;
                headerRow.appendChild(th);
            });
            thead.appendChild(headerRow);

            // Render items
            tbody.textContent = '';
            if (data.items && data.items.length > 0) {
                data.items.forEach(item => {
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';
                    data.columns.forEach(col => {
                        const td = document.createElement('td');
                        td.className = 'px-3 py-2 text-sm';
                        td.textContent = item[col] || '-';
                        row.appendChild(td);
                    });
                    tbody.appendChild(row);
                });
            } else {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = data.columns.length;
                emptyCell.className = 'px-4 py-8 text-center text-gray-500';
                emptyCell.textContent = 'ไม่พบข้อมูล';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
            }
        }
    } catch (error) {
        console.error('Error loading file items:', error);
    }
}

// Utility functions
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function createCell(text, className = '') {
    const td = document.createElement('td');
    td.className = 'px-4 py-2 text-sm ' + className;
    td.textContent = text;
    return td;
}

function formatNumber(value) {
    if (value === null || value === undefined) return '-';
    return parseInt(value).toLocaleString('th-TH');
}

function formatCurrency(value) {
    if (value === null || value === undefined) return '-';
    return parseFloat(value).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Format currency without decimals for large display
function formatCurrencyLarge(value) {
    if (value === null || value === undefined) return '-';
    return Math.round(parseFloat(value)).toLocaleString('th-TH');
}

function getStatusClass(status) {
    switch(status) {
        case 'matched': return 'bg-green-100 text-green-700';
        case 'rep_only': return 'bg-blue-100 text-blue-700';
        case 'stm_only': return 'bg-purple-100 text-purple-700';
        case 'diff_amount': return 'bg-yellow-100 text-yellow-700';
        default: return 'bg-gray-100 text-gray-700';
    }
}

// =============================================================================
// NEW: Claims Detail Functions
// =============================================================================
let currentClaimsPage = 1;

async function loadClaims(page = 1) {
    currentClaimsPage = page;
    const tbody = document.getElementById('claims-table-body');
    tbody.textContent = '';
    const loadingRow = document.createElement('tr');
    const loadingCell = document.createElement('td');
    loadingCell.colSpan = 9;
    loadingCell.className = 'px-4 py-8 text-center text-gray-500';
    loadingCell.textContent = 'กำลังโหลด...';
    loadingRow.appendChild(loadingCell);
    tbody.appendChild(loadingRow);

    try {
        const scheme = document.getElementById('claims-scheme')?.value || '';
        const ptype = document.getElementById('claims-ptype')?.value || '';
        const dateFrom = document.getElementById('claims-date-from')?.value || '';
        const dateTo = document.getElementById('claims-date-to')?.value || '';
        const hasError = document.getElementById('claims-has-error')?.checked ? 'true' : '';

        let url = `/api/analysis/claims?page=${page}`;
        if (scheme) url += `&scheme=${scheme}`;
        if (ptype) url += `&ptype=${ptype}`;
        if (dateFrom) url += `&date_from=${dateFrom}`;
        if (dateTo) url += `&date_to=${dateTo}`;
        if (hasError) url += `&has_error=${hasError}`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            setText('claims-total', formatNumber(data.pagination.total));

            let totalAmount = 0, totalReimb = 0;
            data.claims.forEach(c => {
                totalAmount += c.claim_net || 0;
                totalReimb += c.reimb_nhso || 0;
            });
            setText('claims-amount', formatCurrency(totalAmount));
            setText('claims-reimb', formatCurrency(totalReimb));
            setText('claims-page-info', `${page}/${data.pagination.total_pages}`);
            setText('claims-pagination-text', `หน้า ${page} จาก ${data.pagination.total_pages} (${data.pagination.total} records)`);

            document.getElementById('claims-prev-btn').disabled = page <= 1;
            document.getElementById('claims-next-btn').disabled = page >= data.pagination.total_pages;

            tbody.textContent = '';
            if (data.claims.length > 0) {
                data.claims.forEach(c => {
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';

                    const cells = [
                        { text: c.tran_id || '-', className: 'px-3 py-2 text-sm font-mono' },
                        { text: c.hn || '-', className: 'px-3 py-2 text-sm' },
                        { text: c.name || '-', className: 'px-3 py-2 text-sm' },
                        { text: c.ptype || '-', className: 'px-3 py-2 text-sm', badge: c.ptype === 'IP' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700' },
                        { text: c.scheme || '-', className: 'px-3 py-2 text-sm' },
                        { text: c.dateadm || '-', className: 'px-3 py-2 text-sm' },
                        { text: formatCurrency(c.claim_net), className: 'px-3 py-2 text-sm text-right' },
                        { text: formatCurrency(c.reimb_nhso), className: 'px-3 py-2 text-sm text-right' },
                        { text: c.error_code || '-', className: 'px-3 py-2 text-sm', badge: c.error_code ? 'bg-red-100 text-red-700' : '' }
                    ];

                    cells.forEach(cellData => {
                        const td = document.createElement('td');
                        td.className = cellData.className;
                        if (cellData.badge) {
                            const span = document.createElement('span');
                            span.className = `px-2 py-1 rounded text-xs ${cellData.badge}`;
                            span.textContent = cellData.text;
                            td.appendChild(span);
                        } else {
                            td.textContent = cellData.text;
                        }
                        row.appendChild(td);
                    });

                    tbody.appendChild(row);
                });
            } else {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = 9;
                emptyCell.className = 'px-4 py-8 text-center text-gray-500';
                emptyCell.textContent = 'ไม่พบข้อมูล';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
            }
        }
    } catch (error) {
        console.error('Error loading claims:', error);
        tbody.textContent = '';
        const errorRow = document.createElement('tr');
        const errorCell = document.createElement('td');
        errorCell.colSpan = 9;
        errorCell.className = 'px-4 py-8 text-center text-red-500';
        errorCell.textContent = 'เกิดข้อผิดพลาด';
        errorRow.appendChild(errorCell);
        tbody.appendChild(errorRow);
    }
}

// =============================================================================
// NEW: Financial Breakdown Functions
// =============================================================================
async function loadFinancialBreakdown() {
    const tbody = document.getElementById('financial-table-body');
    tbody.textContent = '';
    const loadingRow = document.createElement('tr');
    const loadingCell = document.createElement('td');
    loadingCell.colSpan = 9;
    loadingCell.className = 'px-4 py-8 text-center text-gray-500';
    loadingCell.textContent = 'กำลังโหลด...';
    loadingRow.appendChild(loadingCell);
    tbody.appendChild(loadingRow);

    try {
        const scheme = document.getElementById('financial-scheme')?.value || '';
        const ptype = document.getElementById('financial-ptype')?.value || '';
        const dateFrom = document.getElementById('financial-date-from')?.value || '';
        const dateTo = document.getElementById('financial-date-to')?.value || '';

        let url = '/api/analysis/financial-breakdown?';
        if (scheme) url += `scheme=${scheme}&`;
        if (ptype) url += `ptype=${ptype}&`;
        if (dateFrom) url += `date_from=${dateFrom}&`;
        if (dateTo) url += `date_to=${dateTo}&`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            setText('financial-total-cases', formatNumber(data.totals.total_cases));
            setText('financial-total-claimed', formatCurrency(data.totals.total_claimed));
            setText('financial-total-reimb', formatCurrency(data.totals.total_reimbursed));

            const reimbRate = data.totals.total_claimed > 0
                ? ((data.totals.total_reimbursed / data.totals.total_claimed) * 100).toFixed(1) + '%'
                : '-';
            setText('financial-reimb-rate', reimbRate);

            tbody.textContent = '';
            if (data.breakdown.length > 0) {
                data.breakdown.forEach(b => {
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';

                    const cells = [
                        { text: b.scheme, className: 'px-3 py-2 text-sm font-medium' },
                        { text: b.ptype, className: 'px-3 py-2 text-sm', badge: b.ptype === 'IP' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700' },
                        { text: formatNumber(b.total_cases), className: 'px-3 py-2 text-sm text-right' },
                        { text: formatCurrency(b.high_cost_care), className: 'px-3 py-2 text-sm text-right' },
                        { text: formatCurrency(b.emergency), className: 'px-3 py-2 text-sm text-right' },
                        { text: formatCurrency(b.prosthetics), className: 'px-3 py-2 text-sm text-right' },
                        { text: formatCurrency(b.drug_costs), className: 'px-3 py-2 text-sm text-right' },
                        { text: formatCurrency(b.total_claimed), className: 'px-3 py-2 text-sm text-right font-medium' },
                        { text: formatCurrency(b.total_reimbursed), className: 'px-3 py-2 text-sm text-right font-medium text-green-600' }
                    ];

                    cells.forEach(cellData => {
                        const td = document.createElement('td');
                        td.className = cellData.className;
                        if (cellData.badge) {
                            const span = document.createElement('span');
                            span.className = `px-2 py-1 rounded text-xs ${cellData.badge}`;
                            span.textContent = cellData.text;
                            td.appendChild(span);
                        } else {
                            td.textContent = cellData.text;
                        }
                        row.appendChild(td);
                    });

                    tbody.appendChild(row);
                });
            } else {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = 9;
                emptyCell.className = 'px-4 py-8 text-center text-gray-500';
                emptyCell.textContent = 'ไม่พบข้อมูล';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
            }
        }
    } catch (error) {
        console.error('Error loading financial breakdown:', error);
        tbody.textContent = '';
        const errorRow = document.createElement('tr');
        const errorCell = document.createElement('td');
        errorCell.colSpan = 9;
        errorCell.className = 'px-4 py-8 text-center text-red-500';
        errorCell.textContent = 'เกิดข้อผิดพลาด';
        errorRow.appendChild(errorCell);
        tbody.appendChild(errorRow);
    }
}

// =============================================================================
// NEW: Error Analytics Functions
// =============================================================================
async function loadErrorAnalytics() {
    const tbody = document.getElementById('errors-table-body');
    tbody.textContent = '';
    const loadingRow = document.createElement('tr');
    const loadingCell = document.createElement('td');
    loadingCell.colSpan = 4;
    loadingCell.className = 'px-4 py-8 text-center text-gray-500';
    loadingCell.textContent = 'กำลังโหลด...';
    loadingRow.appendChild(loadingCell);
    tbody.appendChild(loadingRow);

    try {
        const scheme = document.getElementById('errors-scheme')?.value || '';
        const ptype = document.getElementById('errors-ptype')?.value || '';
        const dateFrom = document.getElementById('errors-date-from')?.value || '';
        const dateTo = document.getElementById('errors-date-to')?.value || '';

        let url = '/api/analysis/errors?';
        if (scheme) url += `scheme=${scheme}&`;
        if (ptype) url += `ptype=${ptype}&`;
        if (dateFrom) url += `date_from=${dateFrom}&`;
        if (dateTo) url += `date_to=${dateTo}&`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            setText('errors-total-records', formatNumber(data.stats.total_records));
            setText('errors-error-count', formatNumber(data.stats.error_count));
            setText('errors-error-amount', formatCurrency(data.stats.error_amount));
            setText('errors-error-rate', data.stats.error_rate + '%');

            tbody.textContent = '';
            if (data.top_errors.length > 0) {
                const totalErrors = data.stats.error_count || 1;
                data.top_errors.forEach(e => {
                    const percentage = ((e.count / totalErrors) * 100).toFixed(1);
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';

                    // Error code cell
                    const codeCell = document.createElement('td');
                    codeCell.className = 'px-4 py-2 text-sm font-mono font-medium';
                    codeCell.textContent = e.error_code;
                    row.appendChild(codeCell);

                    // Count cell
                    const countCell = document.createElement('td');
                    countCell.className = 'px-4 py-2 text-sm text-right';
                    countCell.textContent = formatNumber(e.count);
                    row.appendChild(countCell);

                    // Amount cell
                    const amountCell = document.createElement('td');
                    amountCell.className = 'px-4 py-2 text-sm text-right';
                    amountCell.textContent = formatCurrency(e.affected_amount);
                    row.appendChild(amountCell);

                    // Progress bar cell
                    const progressCell = document.createElement('td');
                    progressCell.className = 'px-4 py-2 text-sm';
                    const progressContainer = document.createElement('div');
                    progressContainer.className = 'flex items-center';
                    const progressBg = document.createElement('div');
                    progressBg.className = 'w-24 bg-gray-200 rounded-full h-2 mr-2';
                    const progressBar = document.createElement('div');
                    progressBar.className = 'bg-red-500 h-2 rounded-full';
                    progressBar.style.width = percentage + '%';
                    progressBg.appendChild(progressBar);
                    progressContainer.appendChild(progressBg);
                    const percentText = document.createElement('span');
                    percentText.className = 'text-xs';
                    percentText.textContent = percentage + '%';
                    progressContainer.appendChild(percentText);
                    progressCell.appendChild(progressContainer);
                    row.appendChild(progressCell);

                    tbody.appendChild(row);
                });
            } else {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = 4;
                emptyCell.className = 'px-4 py-8 text-center text-gray-500';
                emptyCell.textContent = 'ไม่พบ Error';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
            }
        }
    } catch (error) {
        console.error('Error loading error analytics:', error);
        tbody.textContent = '';
        const errorRow = document.createElement('tr');
        const errorCell = document.createElement('td');
        errorCell.colSpan = 4;
        errorCell.className = 'px-4 py-8 text-center text-red-500';
        errorCell.textContent = 'เกิดข้อผิดพลาด';
        errorRow.appendChild(errorCell);
        tbody.appendChild(errorRow);
    }
}

// =============================================================================
// NEW: Facility Analysis Functions
// =============================================================================
async function loadFacilityAnalysis() {
    const tbody = document.getElementById('facilities-table-body');
    tbody.textContent = '';
    const loadingRow = document.createElement('tr');
    const loadingCell = document.createElement('td');
    loadingCell.colSpan = 10;
    loadingCell.className = 'px-4 py-8 text-center text-gray-500';
    loadingCell.textContent = 'กำลังโหลด...';
    loadingRow.appendChild(loadingCell);
    tbody.appendChild(loadingRow);

    try {
        const scheme = document.getElementById('facilities-scheme')?.value || '';
        const ptype = document.getElementById('facilities-ptype')?.value || '';
        const dateFrom = document.getElementById('facilities-date-from')?.value || '';
        const dateTo = document.getElementById('facilities-date-to')?.value || '';
        const limit = document.getElementById('facilities-limit')?.value || '50';

        let url = '/api/analysis/facilities?';
        if (scheme) url += `scheme=${scheme}&`;
        if (ptype) url += `ptype=${ptype}&`;
        if (dateFrom) url += `date_from=${dateFrom}&`;
        if (dateTo) url += `date_to=${dateTo}&`;
        url += `limit=${limit}`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            // Update stats cards
            setText('facilities-count', formatNumber(data.totals.facility_count));
            setText('facilities-total-cases', formatNumber(data.totals.total_cases));
            setText('facilities-total-claimed', formatCurrency(data.totals.total_claimed));
            setText('facilities-total-reimbursed', formatCurrency(data.totals.total_reimbursed));

            // Render table
            tbody.textContent = '';
            if (data.facilities.length > 0) {
                data.facilities.forEach(f => {
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';

                    // hcode
                    const hcodeCell = document.createElement('td');
                    hcodeCell.className = 'px-4 py-2 text-sm font-mono';
                    hcodeCell.textContent = f.hcode;
                    row.appendChild(hcodeCell);

                    // facility name
                    const nameCell = document.createElement('td');
                    nameCell.className = 'px-4 py-2 text-sm';
                    nameCell.textContent = f.facility_name;
                    row.appendChild(nameCell);

                    // province
                    const provCell = document.createElement('td');
                    provCell.className = 'px-4 py-2 text-sm';
                    provCell.textContent = f.province;
                    row.appendChild(provCell);

                    // total cases
                    const casesCell = document.createElement('td');
                    casesCell.className = 'px-4 py-2 text-sm text-right font-medium';
                    casesCell.textContent = formatNumber(f.total_cases);
                    row.appendChild(casesCell);

                    // OP cases
                    const opCell = document.createElement('td');
                    opCell.className = 'px-4 py-2 text-sm text-right';
                    opCell.textContent = formatNumber(f.op_cases);
                    row.appendChild(opCell);

                    // IP cases
                    const ipCell = document.createElement('td');
                    ipCell.className = 'px-4 py-2 text-sm text-right';
                    ipCell.textContent = formatNumber(f.ip_cases);
                    row.appendChild(ipCell);

                    // claimed
                    const claimedCell = document.createElement('td');
                    claimedCell.className = 'px-4 py-2 text-sm text-right';
                    claimedCell.textContent = formatCurrency(f.total_claimed);
                    row.appendChild(claimedCell);

                    // reimbursed
                    const reimbCell = document.createElement('td');
                    reimbCell.className = 'px-4 py-2 text-sm text-right';
                    reimbCell.textContent = formatCurrency(f.total_reimbursed);
                    row.appendChild(reimbCell);

                    // errors
                    const errCell = document.createElement('td');
                    errCell.className = 'px-4 py-2 text-sm text-right';
                    errCell.textContent = formatNumber(f.error_count);
                    row.appendChild(errCell);

                    // error rate
                    const rateCell = document.createElement('td');
                    rateCell.className = 'px-4 py-2 text-sm text-right';
                    const rateVal = f.error_rate || 0;
                    rateCell.textContent = rateVal.toFixed(2) + '%';
                    if (rateVal > 10) rateCell.classList.add('text-red-600', 'font-medium');
                    row.appendChild(rateCell);

                    tbody.appendChild(row);
                });
            } else {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = 10;
                emptyCell.className = 'px-4 py-8 text-center text-gray-500';
                emptyCell.textContent = 'ไม่พบข้อมูลสถานพยาบาล';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
            }
        }
    } catch (error) {
        console.error('Error loading facility analysis:', error);
        tbody.textContent = '';
        const errorRow = document.createElement('tr');
        const errorCell = document.createElement('td');
        errorCell.colSpan = 10;
        errorCell.className = 'px-4 py-8 text-center text-red-500';
        errorCell.textContent = 'เกิดข้อผิดพลาด';
        errorRow.appendChild(errorCell);
        tbody.appendChild(errorRow);
    }
}

// =============================================================================
// NEW: HIS Reconciliation Functions
// =============================================================================
let hisCurrentPage = 1;

async function loadHisReconciliation(page = 1) {
    hisCurrentPage = page;
    const tbody = document.getElementById('his-table-body');
    tbody.textContent = '';
    const loadingRow = document.createElement('tr');
    const loadingCell = document.createElement('td');
    loadingCell.colSpan = 10;
    loadingCell.className = 'px-4 py-8 text-center text-gray-500';
    loadingCell.textContent = 'กำลังโหลด...';
    loadingRow.appendChild(loadingCell);
    tbody.appendChild(loadingRow);

    try {
        const scheme = document.getElementById('his-scheme')?.value || '';
        const status = document.getElementById('his-status')?.value || '';
        const dateFrom = document.getElementById('his-date-from')?.value || '';
        const dateTo = document.getElementById('his-date-to')?.value || '';
        const diffThreshold = document.getElementById('his-diff-threshold')?.value || '0';

        let url = `/api/analysis/his-reconciliation?page=${page}&per_page=50`;
        if (scheme) url += `&scheme=${scheme}`;
        if (status) url += `&status=${status}`;
        if (dateFrom) url += `&date_from=${dateFrom}`;
        if (dateTo) url += `&date_to=${dateTo}`;
        if (diffThreshold && parseFloat(diffThreshold) > 0) {
            url += `&diff_threshold=${diffThreshold}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        if (data.success) {
            // Update status cards
            const statusMap = {
                'pending': { countEl: 'his-pending-count', amountEl: 'his-pending-amount' },
                'matched': { countEl: 'his-matched-count', amountEl: 'his-matched-amount' },
                'mismatched': { countEl: 'his-mismatched-count', amountEl: 'his-mismatched-amount' },
                'manual': { countEl: 'his-manual-count', amountEl: 'his-manual-amount' }
            };

            // Reset all to 0
            Object.values(statusMap).forEach(m => {
                setText(m.countEl, '0');
                setText(m.amountEl, '฿0');
            });

            // Update from data
            data.summary.forEach(s => {
                const map = statusMap[s.status];
                if (map) {
                    setText(map.countEl, formatNumber(s.count));
                    setText(map.amountEl, formatCurrency(s.total_amount));
                }
            });

            // Render table
            tbody.textContent = '';
            if (data.records.length > 0) {
                data.records.forEach(r => {
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';

                    // tran_id
                    const tranCell = document.createElement('td');
                    tranCell.className = 'px-3 py-2 text-xs font-mono';
                    tranCell.textContent = r.tran_id || '-';
                    row.appendChild(tranCell);

                    // hn
                    const hnCell = document.createElement('td');
                    hnCell.className = 'px-3 py-2 text-xs';
                    hnCell.textContent = r.hn || '-';
                    row.appendChild(hnCell);

                    // name
                    const nameCell = document.createElement('td');
                    nameCell.className = 'px-3 py-2 text-xs';
                    nameCell.textContent = r.name || '-';
                    row.appendChild(nameCell);

                    // ptype
                    const ptypeCell = document.createElement('td');
                    ptypeCell.className = 'px-3 py-2 text-xs text-center';
                    const ptypeBadge = document.createElement('span');
                    ptypeBadge.className = r.ptype === 'IP'
                        ? 'px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs'
                        : 'px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs';
                    ptypeBadge.textContent = r.ptype || '-';
                    ptypeCell.appendChild(ptypeBadge);
                    row.appendChild(ptypeCell);

                    // dateadm
                    const dateCell = document.createElement('td');
                    dateCell.className = 'px-3 py-2 text-xs';
                    dateCell.textContent = r.dateadm || '-';
                    row.appendChild(dateCell);

                    // claim_net
                    const claimCell = document.createElement('td');
                    claimCell.className = 'px-3 py-2 text-xs text-right';
                    claimCell.textContent = formatCurrency(r.claim_net);
                    row.appendChild(claimCell);

                    // reimb_nhso
                    const reimbCell = document.createElement('td');
                    reimbCell.className = 'px-3 py-2 text-xs text-right';
                    reimbCell.textContent = formatCurrency(r.reimb_nhso);
                    row.appendChild(reimbCell);

                    // his_vn
                    const vnCell = document.createElement('td');
                    vnCell.className = 'px-3 py-2 text-xs';
                    vnCell.textContent = r.his_vn || '-';
                    row.appendChild(vnCell);

                    // his_amount_diff
                    const diffCell = document.createElement('td');
                    diffCell.className = 'px-3 py-2 text-xs text-right font-medium';
                    const diff = r.his_amount_diff || 0;
                    if (diff !== 0) {
                        diffCell.className += diff > 0 ? ' text-green-600' : ' text-red-600';
                        diffCell.textContent = (diff > 0 ? '+' : '') + formatCurrency(diff);
                    } else {
                        diffCell.textContent = '-';
                    }
                    row.appendChild(diffCell);

                    // reconcile_status
                    const statusCell = document.createElement('td');
                    statusCell.className = 'px-3 py-2 text-xs text-center';
                    const statusBadge = document.createElement('span');
                    const statusClasses = {
                        'pending': 'bg-gray-100 text-gray-700',
                        'matched': 'bg-green-100 text-green-700',
                        'mismatched': 'bg-red-100 text-red-700',
                        'manual': 'bg-yellow-100 text-yellow-700'
                    };
                    const statusLabels = {
                        'pending': 'รอตรวจ',
                        'matched': 'ตรงกัน',
                        'mismatched': 'ไม่ตรง',
                        'manual': 'ตรวจเอง'
                    };
                    statusBadge.className = `px-2 py-1 rounded text-xs ${statusClasses[r.reconcile_status] || 'bg-gray-100 text-gray-700'}`;
                    statusBadge.textContent = statusLabels[r.reconcile_status] || r.reconcile_status;
                    statusCell.appendChild(statusBadge);
                    row.appendChild(statusCell);

                    tbody.appendChild(row);
                });

                // Update pagination
                const pagination = data.pagination;
                document.getElementById('his-pagination').classList.remove('hidden');
                document.getElementById('his-showing-from').textContent = ((pagination.page - 1) * pagination.per_page) + 1;
                document.getElementById('his-showing-to').textContent = Math.min(pagination.page * pagination.per_page, pagination.total);
                document.getElementById('his-total-records').textContent = formatNumber(pagination.total);
                document.getElementById('his-page-info').textContent = `หน้า ${pagination.page} / ${pagination.total_pages}`;
                document.getElementById('his-prev-btn').disabled = pagination.page <= 1;
                document.getElementById('his-next-btn').disabled = pagination.page >= pagination.total_pages;
            } else {
                const emptyRow = document.createElement('tr');
                const emptyCell = document.createElement('td');
                emptyCell.colSpan = 10;
                emptyCell.className = 'px-4 py-8 text-center text-gray-500';
                emptyCell.textContent = 'ไม่พบข้อมูล';
                emptyRow.appendChild(emptyCell);
                tbody.appendChild(emptyRow);
                document.getElementById('his-pagination').classList.add('hidden');
            }
        }
    } catch (error) {
        console.error('Error loading HIS reconciliation:', error);
        tbody.textContent = '';
        const errorRow = document.createElement('tr');
        const errorCell = document.createElement('td');
        errorCell.colSpan = 10;
        errorCell.className = 'px-4 py-8 text-center text-red-500';
        errorCell.textContent = 'เกิดข้อผิดพลาด';
        errorRow.appendChild(errorCell);
        tbody.appendChild(errorRow);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initFiscalYearDropdown();

    // Set default to current fiscal year (not "ทุกปี")
    const fySelect = document.getElementById('summary-fiscal-year');
    if (fySelect && fySelect.options.length > 1) {
        fySelect.selectedIndex = 1; // Current fiscal year
    }

    loadSummary();
});
