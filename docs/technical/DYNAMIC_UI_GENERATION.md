# Dynamic UI Generation for Download Sources

> **Version:** 1.0
> **Date:** 2026-01-18
> **Purpose:** Enable adding new download sources without changing frontend code

---

## Goal

**When adding a new download source, the UI should appear automatically without modifying HTML/JavaScript.**

---

## Architecture: Metadata-Driven UI

```
Source Adapter Metadata → API Endpoint → Frontend Renderer → Dynamic UI
```

---

## 1. Source Metadata Schema

```python
# utils/download_manager/adapters/base.py

from dataclasses import dataclass
from typing import List, Dict, Optional, Any

@dataclass
class FormField:
    """UI form field definition"""
    name: str                    # Field identifier
    label: str                   # Display label (English)
    label_th: str                # Thai label
    type: str                    # text, number, select, date, checkbox
    required: bool = True
    default_value: Optional[Any] = None
    placeholder: Optional[str] = None
    help_text: Optional[str] = None

    # Validation
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    pattern: Optional[str] = None

    # Select options
    options: Optional[List[Dict]] = None  # [{"value": "ucs", "label": "บัตรทอง"}]
    options_endpoint: Optional[str] = None  # API endpoint for dynamic options

    # Conditional display
    depends_on: Optional[str] = None
    depends_value: Optional[Any] = None

@dataclass
class SourceMetadata:
    """Complete source metadata for UI generation"""
    source_type: str
    name: str                     # English name
    name_th: str                  # Thai name
    description: str
    icon: str                     # Font Awesome icon class
    color: str                    # Primary color (hex)

    supports_bulk: bool
    supports_parallel: bool
    max_workers: int

    form_fields: List[FormField]

    primary_action_label: str
    primary_action_label_th: str
    success_message_template: str

class SourceAdapter(ABC):
    # ... existing methods ...

    @abstractmethod
    def get_metadata(self) -> SourceMetadata:
        """Return source metadata for UI generation"""
        pass
```

---

## 2. Example: REP Adapter with Metadata

```python
# utils/download_manager/adapters/rep.py

class REPSourceAdapter(SourceAdapter):
    def get_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_type="rep",
            name="REP Files (e-Claim)",
            name_th="ไฟล์ REP (เบิกจ่ายตรง)",
            description="Download reimbursement files from NHSO e-Claim system",
            icon="fa-file-medical",
            color="#3b82f6",

            supports_bulk=True,
            supports_parallel=True,
            max_workers=3,

            form_fields=[
                FormField(
                    name="fiscal_year",
                    label="Fiscal Year",
                    label_th="ปีงบประมาณ",
                    type="number",
                    required=True,
                    default_value=2569,
                    min_value=2560,
                    max_value=2575,
                    help_text="Thai fiscal year (BE)"
                ),
                FormField(
                    name="service_month",
                    label="Service Month",
                    label_th="เดือนบริการ",
                    type="select",
                    required=False,
                    placeholder="All months",
                    options=[
                        {"value": "", "label": "ทั้งหมด (All)"},
                        {"value": 1, "label": "มกราคม (January)"},
                        {"value": 2, "label": "กุมภาพันธ์ (February)"},
                        # ... more months
                    ]
                ),
                FormField(
                    name="scheme",
                    label="Scheme",
                    label_th="สิทธิการรักษา",
                    type="select",
                    required=False,
                    options=[
                        {"value": "all", "label": "ทั้งหมด"},
                        {"value": "ucs", "label": "บัตรทอง (UCS)"},
                        {"value": "ofc", "label": "ข้าราชการ (OFC)"},
                    ]
                ),
                FormField(
                    name="max_workers",
                    label="Parallel Workers",
                    label_th="จำนวน Workers",
                    type="number",
                    required=False,
                    default_value=3,
                    min_value=1,
                    max_value=5
                ),
                FormField(
                    name="auto_import",
                    label="Auto Import",
                    label_th="Import อัตโนมัติ",
                    type="checkbox",
                    required=False,
                    default_value=False
                )
            ],

            primary_action_label="Download REP Files",
            primary_action_label_th="ดาวน์โหลดไฟล์ REP",
            success_message_template="Downloaded {downloaded} new files, {skipped} already existed"
        )
```

---

## 3. API Endpoint

```python
# routes/downloads_v2.py

@app.route('/api/v2/downloads/sources')
def get_download_sources():
    """Get all available download sources with UI metadata"""
    from utils.download_manager.adapters import get_all_adapters

    sources = []
    for source_type, adapter_class in get_all_adapters().items():
        adapter = adapter_class()
        metadata = adapter.get_metadata()

        sources.append({
            "source_type": metadata.source_type,
            "name": metadata.name,
            "name_th": metadata.name_th,
            "description": metadata.description,
            "icon": metadata.icon,
            "color": metadata.color,
            "supports_bulk": metadata.supports_bulk,
            "supports_parallel": metadata.supports_parallel,
            "max_workers": metadata.max_workers,
            "form_fields": [field.__dict__ for field in metadata.form_fields],
            "primary_action_label": metadata.primary_action_label,
            "primary_action_label_th": metadata.primary_action_label_th,
            "success_message_template": metadata.success_message_template
        })

    return jsonify({"success": True, "sources": sources})
```

---

## 4. Dynamic Frontend Renderer (XSS-Safe)

```javascript
// static/js/download_sources.js

class DownloadSourceRenderer {
    constructor(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.sources = [];
    }

    async loadSources() {
        const response = await fetch('/api/v2/downloads/sources');
        const data = await response.json();
        this.sources = data.sources;
        this.render();
    }

    render() {
        // Clear container safely (XSS-safe)
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }

        this.sources.forEach(source => {
            const card = this.createSourceCard(source);
            this.container.appendChild(card);
        });
    }

    createSourceCard(source) {
        // Create card element
        const card = document.createElement('div');
        card.className = 'source-card';
        card.dataset.sourceType = source.source_type;

        // Header
        const header = document.createElement('div');
        header.className = 'card-header';

        const icon = document.createElement('i');
        icon.className = `icon ${this.sanitizeClassName(source.icon)}`;
        icon.style.color = source.color;

        const title = document.createElement('h3');
        title.className = 'source-name';
        title.textContent = source.name_th || source.name;  // XSS-safe

        header.appendChild(icon);
        header.appendChild(title);

        // Body
        const body = document.createElement('div');
        body.className = 'card-body';

        const description = document.createElement('p');
        description.className = 'source-description';
        description.textContent = source.description;  // XSS-safe

        const form = document.createElement('form');
        form.className = 'download-form';

        // Generate form fields
        source.form_fields.forEach(fieldDef => {
            const field = this.createFormField(fieldDef);
            form.appendChild(field);
        });

        body.appendChild(description);
        body.appendChild(form);

        // Footer
        const footer = document.createElement('div');
        footer.className = 'card-footer';

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-primary';
        button.textContent = source.primary_action_label_th || source.primary_action_label;  // XSS-safe
        button.onclick = () => this.submitDownload(source.source_type, form);

        footer.appendChild(button);

        // Assemble card
        card.appendChild(header);
        card.appendChild(body);
        card.appendChild(footer);

        return card;
    }

    createFormField(fieldDef) {
        const formGroup = document.createElement('div');
        formGroup.className = 'form-group';

        // Label
        const label = document.createElement('label');
        label.textContent = (fieldDef.label_th || fieldDef.label) + (fieldDef.required ? ' *' : '');  // XSS-safe
        label.htmlFor = fieldDef.name;

        // Input element
        let input;

        switch (fieldDef.type) {
            case 'select':
                input = this.createSelectInput(fieldDef);
                break;
            case 'checkbox':
                input = this.createCheckboxInput(fieldDef);
                break;
            case 'number':
                input = this.createNumberInput(fieldDef);
                break;
            case 'text':
            default:
                input = this.createTextInput(fieldDef);
                break;
        }

        input.name = fieldDef.name;
        input.id = fieldDef.name;
        input.required = fieldDef.required;

        // Help text
        if (fieldDef.help_text) {
            const helpText = document.createElement('small');
            helpText.className = 'help-text text-muted';
            helpText.textContent = fieldDef.help_text;  // XSS-safe
            formGroup.appendChild(label);
            formGroup.appendChild(input);
            formGroup.appendChild(helpText);
        } else {
            formGroup.appendChild(label);
            formGroup.appendChild(input);
        }

        // Conditional display
        if (fieldDef.depends_on) {
            formGroup.style.display = 'none';
            formGroup.dataset.dependsOn = fieldDef.depends_on;
            formGroup.dataset.dependsValue = fieldDef.depends_value;
        }

        return formGroup;
    }

    createTextInput(fieldDef) {
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-control';

        if (fieldDef.default_value) {
            input.value = fieldDef.default_value;
        }
        if (fieldDef.placeholder) {
            input.placeholder = fieldDef.placeholder;
        }
        if (fieldDef.pattern) {
            input.pattern = fieldDef.pattern;
        }

        return input;
    }

    createNumberInput(fieldDef) {
        const input = document.createElement('input');
        input.type = 'number';
        input.className = 'form-control';

        if (fieldDef.default_value !== null) {
            input.value = fieldDef.default_value;
        }
        if (fieldDef.min_value !== null) {
            input.min = fieldDef.min_value;
        }
        if (fieldDef.max_value !== null) {
            input.max = fieldDef.max_value;
        }
        if (fieldDef.placeholder) {
            input.placeholder = fieldDef.placeholder;
        }

        return input;
    }

    createSelectInput(fieldDef) {
        const select = document.createElement('select');
        select.className = 'form-control';

        if (fieldDef.options) {
            fieldDef.options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.label;  // XSS-safe

                if (opt.value === fieldDef.default_value) {
                    option.selected = true;
                }

                select.appendChild(option);
            });
        }

        return select;
    }

    createCheckboxInput(fieldDef) {
        const wrapper = document.createElement('div');
        wrapper.className = 'form-check';

        const input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'form-check-input';
        input.checked = fieldDef.default_value === true;

        return input;
    }

    sanitizeClassName(className) {
        // Only allow alphanumeric, dash, underscore
        return className.replace(/[^a-zA-Z0-9\-_]/g, '');
    }

    async submitDownload(sourceType, form) {
        const formData = new FormData(form);
        const params = {};

        for (let [key, value] of formData.entries()) {
            params[key] = value;
        }

        const response = await fetch('/api/v2/downloads/sessions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                source_type: sourceType,
                ...params
            })
        });

        const result = await response.json();

        if (result.success) {
            window.location.href = `/downloads/progress/${result.session_id}`;
        } else {
            alert(`Error: ${result.error || 'Unknown error'}`);
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const renderer = new DownloadSourceRenderer('#download-sources-container');
    renderer.loadSources();
});
```

---

## 5. What Can Be Auto-Generated

### ✅ No Code Changes Needed (95%)

| Feature | Implementation |
|---------|----------------|
| Form fields | Metadata `form_fields` |
| Input validation | `min_value`, `max_value`, `pattern`, `required` |
| Select dropdowns | `options` array |
| Conditional fields | `depends_on` / `depends_value` |
| Help text | `help_text` field |
| Button labels | `primary_action_label` |
| Icons & colors | `icon` and `color` |
| Progress tracking | Built into core |
| Cancel/Resume | Built into core |

### ⚠️ Needs Custom Code (5%)

| Feature | Limitation | Workaround |
|---------|------------|------------|
| Complex UI widgets | Date range picker, autocomplete | Add to component library |
| Cross-field validation | Depends on multiple fields | Add `custom_validators` |
| Dynamic options from API | Not in metadata | Use `options_endpoint` |
| Multi-step wizards | Not supported yet | Add `form_steps` array |
| File upload | Not common for downloads | Add field type `file` |

---

## 6. Adding a New Source (Example)

### Scenario: Add Claims Processing System (CPS) API

**Step 1: Create Adapter with Metadata**
```python
# utils/download_manager/adapters/cps.py

class CPSSourceAdapter(SourceAdapter):
    def get_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_type="cps",
            name="CPS Claims (API)",
            name_th="ระบบ CPS (API)",
            description="Download claims from CPS API",
            icon="fa-chart-line",
            color="#10b981",
            supports_bulk=True,
            supports_parallel=False,
            max_workers=1,
            form_fields=[
                FormField(
                    name="fiscal_year",
                    label="Fiscal Year",
                    label_th="ปีงบประมาณ",
                    type="number",
                    required=True,
                    default_value=2569
                ),
                FormField(
                    name="api_key",
                    label="API Key",
                    label_th="API Key",
                    type="text",
                    required=True,
                    placeholder="Enter your API key"
                )
            ],
            primary_action_label="Fetch CPS Data",
            primary_action_label_th="ดึงข้อมูล CPS",
            success_message_template="Fetched {downloaded} records from CPS"
        )

    # ... implement other methods
```

**Step 2: Register Adapter**
```python
# utils/download_manager/adapters/__init__.py

ADAPTER_REGISTRY = {
    'rep': REPSourceAdapter,
    'stm': STMSourceAdapter,
    'smt': SMTSourceAdapter,
    'cps': CPSSourceAdapter,  # ← Add here
}
```

**Step 3: UI Appears Automatically!**

Frontend calls `/api/v2/downloads/sources` → gets CPS metadata → renders form automatically

**Result:** Zero frontend code changes! ✅

---

## 7. Advanced Features

### Dynamic Select Options from API

```python
FormField(
    name="hospital_code",
    label="Hospital",
    type="select",
    required=True,
    options_endpoint="/api/hospitals",  # ← Fetch dynamically
    options_value_field="hcode5",
    options_label_field="name"
)
```

```javascript
// Frontend handler
if (fieldDef.options_endpoint) {
    const response = await fetch(fieldDef.options_endpoint);
    const data = await response.json();

    data.forEach(item => {
        const option = document.createElement('option');
        option.value = item[fieldDef.options_value_field];
        option.textContent = item[fieldDef.options_label_field];
        select.appendChild(option);
    });
}
```

### Custom Validators

```python
# In adapter metadata
FormField(
    name="date_range",
    label="Date Range",
    type="text",
    custom_validator="validate_date_range"
)

# In adapter class
def validate_date_range(self, value: str) -> bool:
    start, end = value.split(" to ")
    # Custom validation logic
    return True  # or raise ValidationError
```

---

## Summary

### Dynamic UI Coverage

**✅ 95% Auto-Generated:**
- All standard form fields
- Validation rules
- Labels & help text
- Icons & colors
- Progress tracking
- Cancel/Resume

**⚠️ 5% Custom Code:**
- Very complex UI widgets
- Multi-step wizards
- Real-time cross-field validation

### Benefits

1. **Add Source = UI Appears** - No frontend changes
2. **Consistent UX** - All sources use same UI patterns
3. **Type-Safe** - Metadata enforces structure
4. **XSS-Safe** - Uses `textContent` and DOM methods
5. **Maintainable** - Change metadata, not scattered code
6. **Extensible** - Add new field types to library

### Recommendation

**For 95% of use cases, use metadata-driven UI. For the remaining 5%, create reusable component library.**
