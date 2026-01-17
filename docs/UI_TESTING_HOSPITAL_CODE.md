# UI Testing Guide: Hospital Code Validation

คู่มือทดสอบ UI สำหรับระบบตรวจสอบรหัสโรงพยาบาลใน License

## 📋 สิ่งที่เปลี่ยนแปลง

### 1. License Page (`/license`)
- ✅ เพิ่ม **Alert Notification Component** แสดงผลแบบ banner สวยงาม
- ✅ แสดง **Error Message เฉพาะ** สำหรับกรณี hospital code ไม่ตรงกัน
- ✅ **Auto-close** สำหรับ success messages (10 วินาที)

### 2. Dashboard Page (`/dashboard`)
- ✅ แสดง **Warning Banner** เมื่อ license error มี hospital code mismatch
- ✅ แสดง error message 🚫 พร้อมรายละเอียดเต็ม

---

## 🧪 ขั้นตอนการทดสอบ

### Scenario 1: ติดตั้ง License ที่ Hospital Code **ตรงกัน** ✅

**ขั้นตอน:**

1. **ตั้งค่ารหัสโรงพยาบาล**
   ```bash
   # เปิด web browser ไปที่ /setup
   http://localhost:5001/setup
   # ตั้งค่า hospital code เป็น: 10670
   ```

2. **ติดตั้ง License**
   ```bash
   # เปิด /license
   http://localhost:5001/license
   # คลิก "Show Form"
   # Copy ข้อมูลจาก config/test_licenses.json → professional tier
   # - license_key
   # - license_token
   # - public_key
   # คลิก "Install License"
   ```

3. **ผลลัพธ์ที่คาดหวัง:**
   - ✅ แสดง **green success banner** ที่ด้านบน
   - ✅ ข้อความ: "ติดตั้ง License สำเร็จ! License ระดับ professional ถูกติดตั้งเรียบร้อยแล้ว..."
   - ✅ Banner หายไปเองหลัง 10 วินาที
   - ✅ License Status Card อัพเดทเป็น "มืออาชีพ" + "ใช้งานได้"

4. **ตรวจสอบ Dashboard:**
   ```bash
   # เปิด /dashboard
   http://localhost:5001/dashboard
   ```
   - ✅ License Widget แสดง **green badge**: "ใช้งานได้"
   - ✅ แสดง Max users, Records/import ถูกต้อง

---

### Scenario 2: ติดตั้ง License ที่ Hospital Code **ไม่ตรงกัน** ❌

**ขั้นตอน:**

1. **เปลี่ยนรหัสโรงพยาบาล**
   ```bash
   # ไปที่ /setup
   http://localhost:5001/setup
   # เปลี่ยน hospital code เป็น: 99999 (ต่างจาก license ที่เป็น 10670)
   ```

2. **ลบ License เก่า** (ถ้ามี)
   ```bash
   # ไปที่ /license
   http://localhost:5001/license
   # คลิก "Remove License"
   # ยืนยัน
   ```

3. **ติดตั้ง License ที่ออกให้ 10670**
   ```bash
   # ไปที่ /license
   # คลิก "Show Form"
   # Copy ข้อมูลจาก config/test_licenses.json → professional tier (hospital_code: 10670)
   # คลิก "Install License"
   ```

4. **ผลลัพธ์ที่คาดหวัง:**
   - ❌ แสดง **red error banner** ที่ด้านบน
   - ❌ **Title**: "รหัส รพ. ไม่ตรงกัน"
   - ❌ **Message**:
     ```
     License mismatch: This license is issued for hospital code '10670'
     but your system is configured for '99999'.
     Please contact your vendor for the correct license.
     กรุณาติดต่อผู้ให้บริการเพื่อขอ license ที่ถูกต้องสำหรับรหัสโรงพยาบาลของท่าน
     ```
   - ❌ Banner **ไม่หายไป** (ต้องกด X ปิดเอง)
   - ❌ License Status Card **ยังไม่อัพเดท** (ยังเป็น Trial หรือไม่มี license)

5. **ตรวจสอบ Dashboard:**
   ```bash
   # เปิด /dashboard
   http://localhost:5001/dashboard
   ```
   - ❌ License Widget แสดง **amber/yellow badge**: "Trial Mode" หรือ "ไม่ถูกต้อง"
   - ❌ แสดงข้อความ:
     ```
     🚫 License mismatch: This license is issued for hospital code '10670'...
     ```

---

### Scenario 3: ข้อมูลไม่ครบ ⚠️

**ขั้นตอน:**

1. **ไปที่ /license**
2. **คลิก "Show Form"**
3. **กรอกเฉพาะ License Key** (ไม่กรอก Token และ Public Key)
4. **คลิก "Install License"**

**ผลลัพธ์ที่คาดหวัง:**
- ⚠️ แสดง **yellow warning banner**
- ⚠️ **Title**: "ข้อมูลไม่ครบ"
- ⚠️ **Message**: "กรุณากรอกข้อมูลให้ครบทุกช่อง (License Key, Token และ Public Key)"

---

## 🎨 UI Components ที่เปลี่ยน

### Alert Notification Component

```html
<!-- Success Alert -->
<div class="bg-green-50 border-l-4 border-green-500 rounded-lg p-4 shadow-md">
  <div class="flex items-start gap-3">
    <svg class="w-6 h-6 text-green-600">...</svg>
    <div>
      <h3 class="font-semibold text-green-800">ติดตั้ง License สำเร็จ!</h3>
      <p class="text-sm text-green-700">License ระดับ professional...</p>
    </div>
    <button onclick="closeAlert()">×</button>
  </div>
</div>

<!-- Error Alert (Hospital Code Mismatch) -->
<div class="bg-red-50 border-l-4 border-red-500 rounded-lg p-4 shadow-md">
  <div class="flex items-start gap-3">
    <svg class="w-6 h-6 text-red-600">...</svg>
    <div>
      <h3 class="font-semibold text-red-800">รหัส รพ. ไม่ตรงกัน</h3>
      <p class="text-sm text-red-700">License mismatch: This license is issued for...</p>
    </div>
    <button onclick="closeAlert()">×</button>
  </div>
</div>

<!-- Warning Alert -->
<div class="bg-yellow-50 border-l-4 border-yellow-500 rounded-lg p-4 shadow-md">
  <div class="flex items-start gap-3">
    <svg class="w-6 h-6 text-yellow-600">...</svg>
    <div>
      <h3 class="font-semibold text-yellow-800">ข้อมูลไม่ครบ</h3>
      <p class="text-sm text-yellow-700">กรุณากรอกข้อมูลให้ครบทุกช่อง...</p>
    </div>
    <button onclick="closeAlert()">×</button>
  </div>
</div>
```

### Dashboard License Widget

```html
<!-- Invalid License with Hospital Code Error -->
<div class="bg-amber-50 border-l-4 border-amber-500 rounded-lg p-4">
  ...
  <p class="text-sm text-amber-700">
    🚫 License mismatch: This license is issued for hospital code '10670'...
  </p>
  ...
</div>
```

---

## 📝 Checklist การทดสอบ

### License Page (`/license`)
- [ ] ✅ Success alert แสดงสีเขียว พร้อม checkmark icon
- [ ] ✅ Success alert หายไปเองหลัง 10 วินาที
- [ ] ❌ Error alert (hospital mismatch) แสดงสีแดง พร้อม warning icon
- [ ] ❌ Error message มีคำว่า "รหัส รพ. ไม่ตรงกัน" และรายละเอียดชัดเจน
- [ ] ❌ Error alert ไม่หายไป (ต้องกด X)
- [ ] ⚠️ Warning alert แสดงสีเหลือง เมื่อข้อมูลไม่ครบ
- [ ] Alert มีปุ่ม X สำหรับปิด
- [ ] Scroll ขึ้นด้านบนอัตโนมัติเมื่อแสดง alert

### Dashboard (`/dashboard`)
- [ ] ✅ License widget แสดงสีเขียวเมื่อ valid
- [ ] ❌ License widget แสดงสีเหลือง/ส้มเมื่อ invalid
- [ ] ❌ แสดง 🚫 icon กับ error message เมื่อ hospital code mismatch
- [ ] ปุ่ม "ติดตั้ง License" หรือ "จัดการ License" ทำงานถูกต้อง

---

## 🔍 การ Debug

### ตรวจสอบ License Error Message

**Browser Console:**
```javascript
// เปิด DevTools (F12)
// ไปที่ Console tab

// ตรวจสอบ response จาก API
fetch('/api/settings/license')
  .then(r => r.json())
  .then(d => console.log(d));

// ดู license.error ว่ามี hospital code mismatch หรือไม่
```

**Expected Output (Hospital Mismatch):**
```json
{
  "success": false,
  "license": {
    "is_valid": false,
    "status": "invalid",
    "error": "License mismatch: This license is issued for hospital code '10670' but your system is configured for '99999'. Please contact your vendor for the correct license.",
    "tier": "trial",
    ...
  }
}
```

### ตรวจสอบ Settings

```bash
# ดูรหัส รพ. ปัจจุบัน
docker-compose exec -T web python3 -c "
from utils.settings_manager import SettingsManager
sm = SettingsManager()
print('Hospital Code:', sm.get_hospital_code())
"
```

---

## 📸 Screenshots ที่ควรมี

1. **Success Alert** - Green banner หลังติดตั้งสำเร็จ
2. **Error Alert (Hospital Mismatch)** - Red banner กับข้อความ "รหัส รพ. ไม่ตรงกัน"
3. **Warning Alert** - Yellow banner กับ "ข้อมูลไม่ครบ"
4. **Dashboard Warning** - License widget แสดง hospital code mismatch error

---

## ✅ สรุป

การเพิ่ม UI Alerts สำหรับ Hospital Code Validation ช่วยให้:
1. **User Experience ดีขึ้น** - ไม่ต้องใช้ alert() แบบเดิม
2. **Error Message ชัดเจน** - บอกว่าทำไม license ไม่ valid
3. **Visual Feedback** - สีและ icon แจ้งเตือนชัดเจน
4. **Accessibility** - ใช้ ARIA role="alert" สำหรับ screen readers

---

**Last Updated**: 2026-01-17
