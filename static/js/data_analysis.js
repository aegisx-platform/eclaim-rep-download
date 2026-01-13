// Data Analysis Page JavaScript

let currentAnalysisTab = 'summary';

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
}

async function loadSummary() {
    try {
        const response = await fetch('/api/analysis/summary');
        const data = await response.json();

        if (data.success) {
            // REP
            setText('rep-total-records', formatNumber(data.rep.total_records || 0));
            setText('rep-total-amount', formatCurrency(data.rep.total_amount || 0));
            setText('rep-files-count', data.rep.files_count || '0');

            // Statement
            setText('stm-total-records', formatNumber(data.stm.total_records || 0));
            setText('stm-total-amount', formatCurrency(data.stm.total_amount || 0));
            setText('stm-files-count', data.stm.files_count || '0');

            // SMT
            setText('smt-total-records', formatNumber(data.smt.total_records || 0));
            setText('smt-total-amount', formatCurrency(data.smt.total_amount || 0));
            setText('smt-files-count', data.smt.files_count || '0');
        }
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

function onReconGroupByChange() {
    const groupBy = document.getElementById('recon-group-by').value;
    const headerRep = document.getElementById('recon-header-rep');
    const headerTran = document.getElementById('recon-header-tran');

    if (groupBy === 'tran_id') {
        headerRep.classList.add('hidden');
        headerTran.classList.remove('hidden');
    } else {
        headerRep.classList.remove('hidden');
        headerTran.classList.add('hidden');
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

        const url = '/api/analysis/reconciliation?rep_no=' + encodeURIComponent(repNo) +
                    '&status=' + encodeURIComponent(status) +
                    '&group_by=' + encodeURIComponent(groupBy);
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

function getStatusClass(status) {
    switch(status) {
        case 'matched': return 'bg-green-100 text-green-700';
        case 'rep_only': return 'bg-blue-100 text-blue-700';
        case 'stm_only': return 'bg-purple-100 text-purple-700';
        case 'diff_amount': return 'bg-yellow-100 text-yellow-700';
        default: return 'bg-gray-100 text-gray-700';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadSummary();
});
