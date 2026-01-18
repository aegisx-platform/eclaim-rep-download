// Upload Multiple Files Script
let selectedType = '';
let selectedFiles = [];
let duplicateFiles = [];

function selectFileType(type) {
    selectedType = type;

    // Update button styles
    document.querySelectorAll('.file-type-btn').forEach(btn => {
        btn.classList.remove('border-blue-500', 'bg-blue-50');
        btn.classList.add('border-gray-300');
    });
    document.getElementById(`btn-${type}`).classList.add('border-blue-500', 'bg-blue-50');
    document.getElementById(`btn-${type}`).classList.remove('border-gray-300');

    // Update file type hidden input
    document.getElementById('file-type').value = type;

    // Show upload zone
    document.getElementById('upload-zone-container').style.display = 'block';

    // Update accepted file types
    const fileInput = document.getElementById('file-input');
    const formatHint = document.getElementById('file-format-hint');

    if (type === 'smt') {
        fileInput.accept = '.xlsx,.xls,.csv';
        formatHint.textContent = 'รองรับ: .xlsx, .xls, .csv';
    } else {
        fileInput.accept = '.xls';
        formatHint.textContent = 'รองรับ: .xls';
    }

    // Clear previous selection
    clearAllFiles();
}

// Drag & Drop handlers
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('border-blue-500', 'bg-blue-50');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('border-blue-500', 'bg-blue-50');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('border-blue-500', 'bg-blue-50');

    if (e.dataTransfer.files.length > 0) {
        handleFilesSelect(Array.from(e.dataTransfer.files));
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFilesSelect(Array.from(e.target.files));
    }
});

function handleFilesSelect(files) {
    const acceptedExts = fileInput.accept.split(',');
    const validFiles = [];
    const invalidFiles = [];

    files.forEach(file => {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (acceptedExts.includes(ext)) {
            validFiles.push(file);
        } else {
            invalidFiles.push(file.name);
        }
    });

    if (invalidFiles.length > 0) {
        alert(`ไฟล์ต่อไปนี้ไม่รองรับและจะไม่ถูกเพิ่ม:\n${invalidFiles.join('\n')}\n\nรองรับเฉพาะ: ${fileInput.accept}`);
    }

    if (validFiles.length > 0) {
        selectedFiles = validFiles;
        displaySelectedFiles();
    }
}

function displaySelectedFiles() {
    const container = document.getElementById('files-container');
    const filesList = document.getElementById('selected-files-list');
    const filesCount = document.getElementById('files-count');

    // Clear container safely (no XSS risk)
    while (container.firstChild) {
        container.removeChild(container.firstChild);
    }

    filesCount.textContent = selectedFiles.length;

    selectedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-lg';

        const fileInfo = document.createElement('div');
        fileInfo.className = 'flex items-center flex-1';

        const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        icon.setAttribute('class', 'w-5 h-5 text-gray-600 mr-2');
        icon.setAttribute('fill', 'none');
        icon.setAttribute('stroke', 'currentColor');
        icon.setAttribute('viewBox', '0 0 24 24');
        const iconPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        iconPath.setAttribute('stroke-linecap', 'round');
        iconPath.setAttribute('stroke-linejoin', 'round');
        iconPath.setAttribute('stroke-width', '2');
        iconPath.setAttribute('d', 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z');
        icon.appendChild(iconPath);

        const textDiv = document.createElement('div');
        const fileName = document.createElement('div');
        fileName.className = 'text-sm font-medium text-gray-800';
        fileName.textContent = file.name;

        const fileSize = document.createElement('div');
        fileSize.className = 'text-xs text-gray-500';
        fileSize.textContent = formatFileSize(file.size);

        textDiv.appendChild(fileName);
        textDiv.appendChild(fileSize);

        fileInfo.appendChild(icon);
        fileInfo.appendChild(textDiv);

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'text-red-600 hover:text-red-800';
        removeBtn.onclick = () => removeFile(index);

        const removeSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        removeSvg.setAttribute('class', 'w-4 h-4');
        removeSvg.setAttribute('fill', 'none');
        removeSvg.setAttribute('stroke', 'currentColor');
        removeSvg.setAttribute('viewBox', '0 0 24 24');
        const removePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        removePath.setAttribute('stroke-linecap', 'round');
        removePath.setAttribute('stroke-linejoin', 'round');
        removePath.setAttribute('stroke-width', '2');
        removePath.setAttribute('d', 'M6 18L18 6M6 6l12 12');
        removeSvg.appendChild(removePath);
        removeBtn.appendChild(removeSvg);

        fileItem.appendChild(fileInfo);
        fileItem.appendChild(removeBtn);
        container.appendChild(fileItem);
    });

    filesList.classList.remove('hidden');
    document.getElementById('upload-btn').disabled = selectedFiles.length === 0;
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    if (selectedFiles.length > 0) {
        displaySelectedFiles();
    } else {
        clearAllFiles();
    }
}

function clearAllFiles() {
    selectedFiles = [];
    fileInput.value = '';
    document.getElementById('selected-files-list').classList.add('hidden');
    document.getElementById('upload-btn').disabled = true;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

async function uploadBatch() {
    if (!selectedType || selectedFiles.length === 0) {
        alert('กรุณาเลือกประเภทไฟล์และเลือกไฟล์ที่ต้องการอัปโหลด');
        return;
    }

    // Step 1: Check all files for duplicates
    duplicateFiles = [];

    document.getElementById('upload-progress').classList.remove('hidden');
    document.getElementById('upload-result').classList.add('hidden');
    document.getElementById('upload-btn').disabled = true;
    document.getElementById('progress-text').textContent = 'กำลังตรวจสอบไฟล์ซ้ำ...';

    for (const file of selectedFiles) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('type', selectedType);
        formData.append('auto_import', 'false');
        formData.append('replace', 'false');

        try {
            const response = await fetch('/api/files/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (response.status === 409 && result.error === 'file_exists') {
                duplicateFiles.push({ file, filename: file.name });
            } else if (!result.success) {
                console.error(`Error checking ${file.name}:`, result.error);
            }
        } catch (error) {
            console.error(`Error checking ${file.name}:`, error);
        }
    }

    // Step 2: Show duplicate confirmation if needed
    if (duplicateFiles.length > 0) {
        document.getElementById('upload-progress').classList.add('hidden');
        document.getElementById('upload-btn').disabled = false;
        showDuplicateModal();
    } else {
        // No duplicates, proceed with upload
        await performBatchUpload(selectedFiles.map(f => ({ file: f, replace: false })));
    }
}

function showDuplicateModal() {
    const modal = document.getElementById('duplicate-modal');
    const listContainer = document.getElementById('duplicate-files-list');

    // Clear list safely
    while (listContainer.firstChild) {
        listContainer.removeChild(listContainer.firstChild);
    }

    duplicateFiles.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'flex items-center p-3 bg-gray-50 rounded-lg';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `dup-${index}`;
        checkbox.className = 'w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500';
        checkbox.checked = false;

        const label = document.createElement('label');
        label.htmlFor = `dup-${index}`;
        label.className = 'ml-3 flex-1 text-sm text-gray-700 cursor-pointer';
        label.textContent = item.filename;

        div.appendChild(checkbox);
        div.appendChild(label);
        listContainer.appendChild(div);
    });

    modal.classList.remove('hidden');
}

function closeDuplicateModal() {
    document.getElementById('duplicate-modal').classList.add('hidden');
    document.getElementById('upload-btn').disabled = false;
}

async function proceedWithDuplicates() {
    const modal = document.getElementById('duplicate-modal');
    modal.classList.add('hidden');

    // Build upload queue with replace flags
    const uploadQueue = [];

    // Add non-duplicate files
    selectedFiles.forEach(file => {
        const isDuplicate = duplicateFiles.some(d => d.filename === file.name);
        if (!isDuplicate) {
            uploadQueue.push({ file, replace: false });
        }
    });

    // Add selected duplicate files with replace=true
    duplicateFiles.forEach((item, index) => {
        const checkbox = document.getElementById(`dup-${index}`);
        if (checkbox && checkbox.checked) {
            uploadQueue.push({ file: item.file, replace: true });
        }
    });

    if (uploadQueue.length === 0) {
        alert('ไม่มีไฟล์ที่จะอัปโหลด');
        document.getElementById('upload-btn').disabled = false;
        return;
    }

    await performBatchUpload(uploadQueue);
}

async function performBatchUpload(uploadQueue) {
    document.getElementById('upload-progress').classList.remove('hidden');
    document.getElementById('upload-result').classList.add('hidden');
    document.getElementById('upload-btn').disabled = true;

    const total = uploadQueue.length;
    let completed = 0;
    let succeeded = 0;
    let failed = 0;
    const errors = [];

    for (const { file, replace } of uploadQueue) {
        document.getElementById('progress-text').textContent = `กำลังอัปโหลดไฟล์ ${completed + 1} จาก ${total}: ${file.name}`;
        document.getElementById('progress-percent').textContent = `${Math.round((completed / total) * 100)}%`;
        document.getElementById('progress-bar').style.width = `${(completed / total) * 100}%`;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('type', selectedType);
        formData.append('auto_import', document.getElementById('auto-import').checked ? 'true' : 'false');
        formData.append('replace', replace ? 'true' : 'false');

        try {
            const response = await fetch('/api/files/upload', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                succeeded++;
            } else {
                failed++;
                errors.push({ filename: file.name, error: result.error || 'Unknown error' });
            }
        } catch (error) {
            failed++;
            errors.push({ filename: file.name, error: error.message });
        }

        completed++;
    }

    // Update to 100%
    document.getElementById('progress-bar').style.width = '100%';
    document.getElementById('progress-percent').textContent = '100%';
    document.getElementById('progress-text').textContent = 'อัปโหลดเสร็จสิ้น';

    // Wait a bit then show result
    setTimeout(() => {
        showBatchResult(succeeded, failed, errors);
    }, 1000);
}

function showBatchResult(succeeded, failed, errors) {
    document.getElementById('upload-progress').classList.add('hidden');

    const resultDiv = document.getElementById('upload-result');
    resultDiv.classList.remove('hidden');
    resultDiv.className = succeeded > 0 && failed === 0 ? 'bg-green-50 border border-green-200 rounded-lg p-6' : 'bg-yellow-50 border border-yellow-200 rounded-lg p-6';

    // Clear result div safely
    while (resultDiv.firstChild) {
        resultDiv.removeChild(resultDiv.firstChild);
    }

    const message = document.createElement('div');
    message.className = 'flex items-start';

    // Icon
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('class', succeeded > 0 && failed === 0 ? 'w-6 h-6 text-green-600 mr-3 mt-0.5' : 'w-6 h-6 text-yellow-600 mr-3 mt-0.5');
    icon.setAttribute('fill', 'none');
    icon.setAttribute('stroke', 'currentColor');
    icon.setAttribute('viewBox', '0 0 24 24');
    const iconPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    iconPath.setAttribute('stroke-linecap', 'round');
    iconPath.setAttribute('stroke-linejoin', 'round');
    iconPath.setAttribute('stroke-width', '2');
    iconPath.setAttribute('d', succeeded > 0 && failed === 0 ? 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' : 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z');
    icon.appendChild(iconPath);

    const content = document.createElement('div');
    content.className = 'flex-1';

    const title = document.createElement('h3');
    title.className = succeeded > 0 && failed === 0 ? 'font-semibold text-green-800 mb-2' : 'font-semibold text-yellow-800 mb-2';
    title.textContent = `อัปโหลดเสร็จสิ้น: สำเร็จ ${succeeded} ไฟล์${failed > 0 ? `, ล้มเหลว ${failed} ไฟล์` : ''}`;

    content.appendChild(title);

    if (failed > 0 && errors.length > 0) {
        const errorList = document.createElement('div');
        errorList.className = 'mt-2 text-sm text-red-700';
        const errorTitle = document.createElement('div');
        errorTitle.className = 'font-medium mb-1';
        errorTitle.textContent = 'ข้อผิดพลาด:';
        errorList.appendChild(errorTitle);

        errors.forEach(err => {
            const errorItem = document.createElement('div');
            errorItem.className = 'ml-2';
            errorItem.textContent = `• ${err.filename}: ${err.error}`;
            errorList.appendChild(errorItem);
        });

        content.appendChild(errorList);
    }

    const actions = document.createElement('div');
    actions.className = 'mt-4 flex gap-3';

    const viewFilesBtn = document.createElement('button');
    viewFilesBtn.className = 'text-sm text-blue-600 hover:text-blue-800';
    viewFilesBtn.textContent = 'ดูรายการไฟล์';
    viewFilesBtn.onclick = () => window.location.href = '/files';

    const uploadAgainBtn = document.createElement('button');
    uploadAgainBtn.className = 'text-sm text-gray-600 hover:text-gray-800';
    uploadAgainBtn.textContent = 'อัปโหลดไฟล์ใหม่';
    uploadAgainBtn.onclick = () => location.reload();

    actions.appendChild(viewFilesBtn);
    actions.appendChild(uploadAgainBtn);
    content.appendChild(actions);

    message.appendChild(icon);
    message.appendChild(content);
    resultDiv.appendChild(message);
}
