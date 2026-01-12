# PROJECT.md
## E-Claim Download & Import System - Architecture Separation

---

## Vision

แยกระบบ E-Claim Download ออกเป็น 2 products:
1. **eclaim-downloader-core (FREE)** - Standalone download system ที่ใครก็ใช้ได้
2. **eclaim-platform-pro (PAID)** - Full platform with import, reconciliation, analytics

ทั้ง 2 repos ใช้ core download logic ร่วมกันผ่าน git submodule หรือ pip package

---

## Goals

1. **แยก Free Version** - Download system ที่สามารถใช้งานแบบ standalone
2. **Paid Version** - Full features (import, reconciliation, analytics, scheduling)
3. **Shared Core** - Logic ที่ใช้ร่วมกันได้ทั้ง 2 repos
4. **API Ready** - มี REST API สำหรับ integration กับระบบอื่น

---

## Current State

ระบบปัจจุบันมี 3 ประเภทการ download ที่รวมอยู่ใน monolithic repo:

| ประเภท | แหล่งข้อมูล | ประเภทไฟล์ | ต้อง Login |
|--------|------------|-----------|-----------|
| **REP** (Representative) | NHSO E-Claim Portal | Excel (.xls) | Yes |
| **STM** (Statement) | NHSO E-Claim Portal | Excel (.xls) | Yes |
| **SMT** (Budget Report) | SMT API (Public) | JSON/CSV | No |

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│           REPO 1: eclaim-downloader-core (FREE)                  │
├─────────────────────────────────────────────────────────────────┤
│   Features:                                                      │
│   ├─ REP Download (OP, IP, ORF files)                           │
│   ├─ STM Download (Statement files)                             │
│   ├─ SMT Fetch (Budget API - no auth needed)                    │
│   ├─ History Tracking (JSON-based)                              │
│   ├─ CLI Tools                                                  │
│   ├─ Simple Web UI (view/download only)                         │
│   └─ REST API (read-only)                                       │
│                                                                  │
│   Limitations: No DB import, No scheduler, No reconciliation    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ pip install / git submodule
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│          REPO 2: eclaim-platform-pro (PAID)                      │
├─────────────────────────────────────────────────────────────────┤
│   Includes all FREE features PLUS:                               │
│   ├─ Database Import System (REP, STM, SMT)                     │
│   ├─ Scheduler (APScheduler) with auto-import                   │
│   ├─ Reconciliation Dashboard (REP vs STM)                      │
│   ├─ Analytics & Reports                                        │
│   └─ Advanced API (write operations)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Constraints

- **Python 3.10+** - ใช้ type hints และ dataclasses
- **Flask** - Web framework (เดิมใช้อยู่แล้ว)
- **No breaking changes** - Pro version ต้องทำงานเหมือนเดิม
- **Backward compatible API** - API endpoints ที่มีอยู่ต้องไม่เปลี่ยน

---

## Success Criteria

1. **Core repo works standalone** - `pip install eclaim-downloader-core` ใช้งานได้
2. **Pro repo uses core** - Import จาก core โดยไม่ duplicate code
3. **All 3 download types work** - REP, STM, SMT ทำงานได้ทั้ง 2 versions
4. **API documented** - OpenAPI spec สำหรับ integration
5. **Docker support** - ทั้ง 2 repos มี Dockerfile

---

## References

- **Detailed Spec:** `SYSTEM_REDESIGN_SPEC.md`
- **Current Codebase Analysis:** `.planning/codebase/`
