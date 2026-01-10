#!/usr/bin/env python3
"""
Metabase Dashboard Setup Script
สร้าง Dashboard สำเร็จรูปสำหรับวิเคราะห์ข้อมูล E-Claim

Usage:
    python scripts/setup_metabase.py

Requirements:
    - Metabase running at http://localhost:3000
    - PostgreSQL database with E-Claim data
"""

import requests
import time
import sys
import os

# Configuration
METABASE_URL = os.getenv("METABASE_URL", "http://localhost:3000")
ADMIN_EMAIL = os.getenv("METABASE_ADMIN_EMAIL", "admin@eclaim.local")
ADMIN_PASSWORD = os.getenv("METABASE_ADMIN_PASSWORD", "EclaimAdmin123!")
ADMIN_FIRST_NAME = "Admin"
ADMIN_LAST_NAME = "E-Claim"

# Database connection (matches docker-compose.yml)
DB_CONFIG = {
    "host": os.getenv("MB_DB_HOST", "db"),
    "port": int(os.getenv("MB_DB_PORT", "5432")),
    "dbname": os.getenv("MB_DB_DBNAME", "eclaim_db"),
    "user": os.getenv("MB_DB_USER", "eclaim"),
    "password": os.getenv("MB_DB_PASSWORD", "eclaim_password"),
}


class MetabaseSetup:
    def __init__(self):
        self.session = requests.Session()
        self.session_token = None
        self.database_id = None

    def wait_for_metabase(self, timeout=120):
        """Wait for Metabase to be ready"""
        print("⏳ Waiting for Metabase to be ready...")
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp = self.session.get(f"{METABASE_URL}/api/health")
                if resp.status_code == 200 and resp.json().get("status") == "ok":
                    print("✓ Metabase is ready")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(2)
        raise TimeoutError("Metabase did not become ready in time")

    def check_setup_needed(self):
        """Check if initial setup is needed"""
        resp = self.session.get(f"{METABASE_URL}/api/session/properties")
        if resp.status_code == 200:
            props = resp.json()
            return props.get("setup-token") is not None
        return True

    def initial_setup(self):
        """Perform initial Metabase setup"""
        print("🔧 Performing initial setup...")

        # Get setup token
        resp = self.session.get(f"{METABASE_URL}/api/session/properties")
        setup_token = resp.json().get("setup-token")

        if not setup_token:
            print("  Setup already completed, trying to login...")
            return self.login()

        # Complete setup
        setup_data = {
            "token": setup_token,
            "user": {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "first_name": ADMIN_FIRST_NAME,
                "last_name": ADMIN_LAST_NAME,
                "site_name": "E-Claim Analytics"
            },
            "prefs": {
                "site_name": "E-Claim Analytics",
                "site_locale": "th",
                "allow_tracking": False
            },
            "database": None  # We'll add database separately
        }

        resp = self.session.post(f"{METABASE_URL}/api/setup", json=setup_data)
        if resp.status_code == 200:
            self.session_token = resp.json().get("id")
            self.session.headers["X-Metabase-Session"] = self.session_token
            print("✓ Initial setup completed")
            return True
        else:
            # Setup might fail if user already exists, try login
            print(f"  Setup not needed, trying to login...")
            return self.login()

    def login(self):
        """Login to Metabase"""
        print("🔐 Logging in...")
        resp = self.session.post(
            f"{METABASE_URL}/api/session",
            json={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if resp.status_code == 200:
            self.session_token = resp.json().get("id")
            self.session.headers["X-Metabase-Session"] = self.session_token
            print("✓ Logged in successfully")
            return True
        else:
            print(f"✗ Login failed: {resp.text}")
            return False

    def add_database(self):
        """Add PostgreSQL database connection"""
        print("🗄️ Adding database connection...")

        # Check if database already exists
        resp = self.session.get(f"{METABASE_URL}/api/database")
        if resp.status_code == 200:
            databases = resp.json().get("data", [])
            for db in databases:
                if db.get("name") == "E-Claim Database":
                    self.database_id = db["id"]
                    print(f"  Database already exists (ID: {self.database_id})")
                    return True

        # Add new database
        db_data = {
            "name": "E-Claim Database",
            "engine": "postgres",
            "details": {
                "host": DB_CONFIG["host"],
                "port": DB_CONFIG["port"],
                "dbname": DB_CONFIG["dbname"],
                "user": DB_CONFIG["user"],
                "password": DB_CONFIG["password"],
                "ssl": False,
                "tunnel-enabled": False
            },
            "is_full_sync": True,
            "is_on_demand": False
        }

        resp = self.session.post(f"{METABASE_URL}/api/database", json=db_data)
        if resp.status_code == 200:
            self.database_id = resp.json()["id"]
            print(f"✓ Database added (ID: {self.database_id})")
            # Trigger sync
            self.session.post(f"{METABASE_URL}/api/database/{self.database_id}/sync")
            print("  Syncing database schema...")
            time.sleep(5)  # Wait for sync
            return True
        else:
            print(f"✗ Failed to add database: {resp.text}")
            return False

    def create_question(self, name, description, sql_query):
        """Create a saved question (SQL query)"""
        question_data = {
            "name": name,
            "description": description,
            "display": "table",
            "dataset_query": {
                "type": "native",
                "native": {
                    "query": sql_query
                },
                "database": self.database_id
            },
            "visualization_settings": {}
        }

        resp = self.session.post(f"{METABASE_URL}/api/card", json=question_data)
        if resp.status_code == 200:
            card_id = resp.json()["id"]
            print(f"  ✓ Created: {name} (ID: {card_id})")
            return card_id
        else:
            print(f"  ✗ Failed to create {name}: {resp.text}")
            return None

    def create_dashboard(self, name, description):
        """Create a new dashboard"""
        resp = self.session.post(
            f"{METABASE_URL}/api/dashboard",
            json={"name": name, "description": description}
        )
        if resp.status_code == 200:
            dashboard_id = resp.json()["id"]
            print(f"✓ Created dashboard: {name} (ID: {dashboard_id})")
            return dashboard_id
        else:
            print(f"✗ Failed to create dashboard: {resp.text}")
            return None

    def add_card_to_dashboard(self, dashboard_id, card_id, row, col, size_x=6, size_y=4):
        """Add a question card to dashboard"""
        resp = self.session.post(
            f"{METABASE_URL}/api/dashboard/{dashboard_id}/cards",
            json={
                "cardId": card_id,
                "row": row,
                "col": col,
                "size_x": size_x,
                "size_y": size_y
            }
        )
        return resp.status_code == 200

    def setup_dashboards(self):
        """Create all dashboards with questions"""
        print("\n📊 Creating dashboards...")

        # ============================================
        # Dashboard 1: Financial Overview
        # ============================================
        print("\n📈 Creating Financial Overview Dashboard...")

        questions = []

        # KPI: Total Claims
        q1 = self.create_question(
            "ยอดเรียกเก็บรวม (Total Claims)",
            "ยอดเรียกเก็บทั้งหมด",
            """
            SELECT
                COALESCE(SUM(claim_drg), 0) + COALESCE(SUM(claim_central_reimb), 0) as total_claim
            FROM claim_rep_opip_nhso_item
            """
        )
        if q1: questions.append((q1, 0, 0, 4, 3))

        # KPI: Total Reimbursement
        q2 = self.create_question(
            "ยอดชดเชยรวม (Total Reimbursement)",
            "ยอดชดเชยที่ได้รับ",
            """
            SELECT
                COALESCE(SUM(reimb_amt), 0) as total_reimb
            FROM claim_rep_opip_nhso_item
            """
        )
        if q2: questions.append((q2, 0, 4, 4, 3))

        # KPI: Reimbursement Rate
        q3 = self.create_question(
            "อัตราชดเชย (%)",
            "เปอร์เซ็นต์ที่ได้รับชดเชย",
            """
            SELECT
                ROUND(
                    COALESCE(SUM(reimb_amt), 0) * 100.0 /
                    NULLIF(COALESCE(SUM(claim_drg), 0) + COALESCE(SUM(claim_central_reimb), 0), 0)
                , 2) as reimb_rate_percent
            FROM claim_rep_opip_nhso_item
            """
        )
        if q3: questions.append((q3, 0, 8, 4, 3))

        # Monthly Trend
        q4 = self.create_question(
            "แนวโน้มรายเดือน (Monthly Trend)",
            "เปรียบเทียบยอดเรียกเก็บและชดเชยรายเดือน",
            """
            SELECT
                TO_CHAR(dateadm, 'YYYY-MM') as month,
                COALESCE(SUM(claim_drg), 0) + COALESCE(SUM(claim_central_reimb), 0) as total_claim,
                COALESCE(SUM(reimb_amt), 0) as total_reimb
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
            GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT 12
            """
        )
        if q4: questions.append((q4, 3, 0, 12, 5))

        # OP vs IP Comparison
        q5 = self.create_question(
            "เปรียบเทียบ OP vs IP",
            "สัดส่วนผู้ป่วยนอกและผู้ป่วยใน",
            """
            SELECT
                CASE
                    WHEN ptype = '1' THEN 'OP (ผู้ป่วยนอก)'
                    WHEN ptype = '2' THEN 'IP (ผู้ป่วยใน)'
                    ELSE 'Other'
                END as patient_type,
                COUNT(*) as count,
                COALESCE(SUM(reimb_amt), 0) as total_reimb
            FROM claim_rep_opip_nhso_item
            GROUP BY ptype
            ORDER BY count DESC
            """
        )
        if q5: questions.append((q5, 8, 0, 6, 5))

        # Revenue by Fund
        q6 = self.create_question(
            "รายได้แยกตามกองทุน",
            "ยอดชดเชยแยกตามกองทุน",
            """
            SELECT
                COALESCE(main_fund, 'ไม่ระบุ') as fund,
                COUNT(*) as count,
                COALESCE(SUM(reimb_amt), 0) as total_reimb
            FROM claim_rep_opip_nhso_item
            GROUP BY main_fund
            ORDER BY total_reimb DESC
            LIMIT 10
            """
        )
        if q6: questions.append((q6, 8, 6, 6, 5))

        # Create dashboard and add cards
        dashboard_id = self.create_dashboard(
            "Financial Overview - ภาพรวมการเงิน",
            "Dashboard แสดงภาพรวมทางการเงินของ E-Claim"
        )
        if dashboard_id:
            for card_id, row, col, size_x, size_y in questions:
                self.add_card_to_dashboard(dashboard_id, card_id, row, col, size_x, size_y)

        # ============================================
        # Dashboard 2: Error Monitoring
        # ============================================
        print("\n⚠️ Creating Error Monitoring Dashboard...")

        questions = []

        # Error Summary
        q7 = self.create_question(
            "สรุป Error Code",
            "รายการ Error codes ที่พบบ่อย",
            """
            SELECT
                COALESCE(error_code, 'ไม่มี error') as error_code,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage,
                COALESCE(SUM(claim_drg), 0) as claim_amount
            FROM claim_rep_opip_nhso_item
            GROUP BY error_code
            ORDER BY count DESC
            LIMIT 20
            """
        )
        if q7: questions.append((q7, 0, 0, 12, 6))

        # Error Rate by Month
        q8 = self.create_question(
            "Error Rate รายเดือน",
            "อัตรา Error แยกตามเดือน",
            """
            SELECT
                TO_CHAR(dateadm, 'YYYY-MM') as month,
                COUNT(*) as total_records,
                SUM(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 ELSE 0 END) as error_count,
                ROUND(
                    SUM(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 ELSE 0 END) * 100.0 /
                    NULLIF(COUNT(*), 0)
                , 2) as error_rate
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
            GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT 12
            """
        )
        if q8: questions.append((q8, 6, 0, 12, 5))

        dashboard_id = self.create_dashboard(
            "Error Monitoring - ติดตาม Error",
            "Dashboard สำหรับติดตามและวิเคราะห์ Error"
        )
        if dashboard_id:
            for card_id, row, col, size_x, size_y in questions:
                self.add_card_to_dashboard(dashboard_id, card_id, row, col, size_x, size_y)

        # ============================================
        # Dashboard 3: DRG Analysis
        # ============================================
        print("\n🏥 Creating DRG Analysis Dashboard...")

        questions = []

        # Top DRGs by Revenue
        q9 = self.create_question(
            "Top 20 DRG ที่สร้างรายได้สูงสุด",
            "DRG ที่มียอดเรียกเก็บสูงสุด",
            """
            SELECT
                COALESCE(drg, 'ไม่ระบุ') as drg_code,
                COUNT(*) as case_count,
                ROUND(AVG(rw)::numeric, 4) as avg_rw,
                COALESCE(SUM(claim_drg), 0) as total_claim,
                COALESCE(SUM(reimb_amt), 0) as total_reimb
            FROM claim_rep_opip_nhso_item
            WHERE drg IS NOT NULL AND drg != ''
            GROUP BY drg
            ORDER BY total_claim DESC
            LIMIT 20
            """
        )
        if q9: questions.append((q9, 0, 0, 12, 8))

        # RW Distribution
        q10 = self.create_question(
            "การกระจายตัวของ RW",
            "สถิติ Relative Weight",
            """
            SELECT
                CASE
                    WHEN rw < 0.5 THEN '< 0.5'
                    WHEN rw < 1.0 THEN '0.5 - 1.0'
                    WHEN rw < 2.0 THEN '1.0 - 2.0'
                    WHEN rw < 3.0 THEN '2.0 - 3.0'
                    WHEN rw < 5.0 THEN '3.0 - 5.0'
                    ELSE '>= 5.0'
                END as rw_range,
                COUNT(*) as count
            FROM claim_rep_opip_nhso_item
            WHERE rw IS NOT NULL
            GROUP BY
                CASE
                    WHEN rw < 0.5 THEN '< 0.5'
                    WHEN rw < 1.0 THEN '0.5 - 1.0'
                    WHEN rw < 2.0 THEN '1.0 - 2.0'
                    WHEN rw < 3.0 THEN '2.0 - 3.0'
                    WHEN rw < 5.0 THEN '3.0 - 5.0'
                    ELSE '>= 5.0'
                END
            ORDER BY
                CASE
                    WHEN rw < 0.5 THEN 1
                    WHEN rw < 1.0 THEN 2
                    WHEN rw < 2.0 THEN 3
                    WHEN rw < 3.0 THEN 4
                    WHEN rw < 5.0 THEN 5
                    ELSE 6
                END
            """
        )
        if q10: questions.append((q10, 8, 0, 6, 5))

        dashboard_id = self.create_dashboard(
            "DRG Analysis - วิเคราะห์ DRG",
            "Dashboard วิเคราะห์ข้อมูล DRG และ Relative Weight"
        )
        if dashboard_id:
            for card_id, row, col, size_x, size_y in questions:
                self.add_card_to_dashboard(dashboard_id, card_id, row, col, size_x, size_y)

        # ============================================
        # Dashboard 4: Import Status
        # ============================================
        print("\n📁 Creating Import Status Dashboard...")

        questions = []

        # Import Summary
        q11 = self.create_question(
            "สรุปการ Import",
            "สถานะการ import ไฟล์ทั้งหมด",
            """
            SELECT
                COALESCE(file_type, 'Unknown') as file_type,
                status,
                COUNT(*) as file_count,
                COALESCE(SUM(total_records), 0) as total_records,
                COALESCE(SUM(imported_records), 0) as imported_records
            FROM eclaim_imported_files
            GROUP BY file_type, status
            ORDER BY file_count DESC
            """
        )
        if q11: questions.append((q11, 0, 0, 12, 5))

        # Recent Imports
        q12 = self.create_question(
            "การ Import ล่าสุด",
            "รายการ import 20 รายการล่าสุด",
            """
            SELECT
                filename,
                file_type,
                status,
                total_records,
                imported_records,
                error_message,
                created_at
            FROM eclaim_imported_files
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        if q12: questions.append((q12, 5, 0, 12, 6))

        dashboard_id = self.create_dashboard(
            "Import Status - สถานะการ Import",
            "Dashboard ติดตามการ import ข้อมูล"
        )
        if dashboard_id:
            for card_id, row, col, size_x, size_y in questions:
                self.add_card_to_dashboard(dashboard_id, card_id, row, col, size_x, size_y)

        # ============================================
        # Dashboard 5: Drug Analytics
        # ============================================
        print("\n💊 Creating Drug Analytics Dashboard...")

        questions = []

        # Top Drugs by Cost
        q13 = self.create_question(
            "Top 20 ยาที่มียอดเบิกสูงสุด",
            "ยาที่มีการเบิกมากที่สุด",
            """
            SELECT
                COALESCE(tmt_code, 'ไม่ระบุ') as tmt_code,
                COALESCE(generic_name, 'ไม่ระบุ') as generic_name,
                COUNT(*) as prescription_count,
                COALESCE(SUM(quantity), 0) as total_qty,
                COALESCE(SUM(claim_amount), 0) as total_claim,
                COALESCE(SUM(reimb_amount), 0) as total_reimb
            FROM eclaim_drug
            WHERE tmt_code IS NOT NULL
            GROUP BY tmt_code, generic_name
            ORDER BY total_claim DESC
            LIMIT 20
            """
        )
        if q13: questions.append((q13, 0, 0, 12, 8))

        # Drug Type Distribution
        q14 = self.create_question(
            "สัดส่วนประเภทยา",
            "แยกตามประเภทยา (ED, NED, etc.)",
            """
            SELECT
                COALESCE(drug_type, 'ไม่ระบุ') as drug_type,
                COUNT(*) as count,
                COALESCE(SUM(claim_amount), 0) as total_claim
            FROM eclaim_drug
            GROUP BY drug_type
            ORDER BY count DESC
            """
        )
        if q14: questions.append((q14, 8, 0, 6, 5))

        # Drug with Errors
        q15 = self.create_question(
            "ยาที่มี Error",
            "รายการยาที่มี Error Code",
            """
            SELECT
                error_code,
                COUNT(*) as count,
                COALESCE(SUM(claim_amount), 0) as total_claim
            FROM eclaim_drug
            WHERE error_code IS NOT NULL AND error_code != ''
            GROUP BY error_code
            ORDER BY count DESC
            LIMIT 10
            """
        )
        if q15: questions.append((q15, 8, 6, 6, 5))

        dashboard_id = self.create_dashboard(
            "Drug Analytics - วิเคราะห์ยา",
            "Dashboard วิเคราะห์การเบิกยา"
        )
        if dashboard_id:
            for card_id, row, col, size_x, size_y in questions:
                self.add_card_to_dashboard(dashboard_id, card_id, row, col, size_x, size_y)

        # ============================================
        # Dashboard 6: Instrument Analytics
        # ============================================
        print("\n🔧 Creating Instrument Analytics Dashboard...")

        questions = []

        # Top Instruments
        q16 = self.create_question(
            "Top 20 อุปกรณ์ที่เบิกมากที่สุด",
            "อุปกรณ์การแพทย์ที่มียอดเบิกสูงสุด",
            """
            SELECT
                COALESCE(inst_code, 'ไม่ระบุ') as inst_code,
                COALESCE(inst_name, 'ไม่ระบุ') as inst_name,
                COUNT(*) as usage_count,
                COALESCE(SUM(claim_qty), 0) as total_claim_qty,
                COALESCE(SUM(claim_amount), 0) as total_claim,
                COALESCE(SUM(reimb_amount), 0) as total_reimb,
                ROUND(COALESCE(SUM(reimb_amount), 0) * 100.0 / NULLIF(COALESCE(SUM(claim_amount), 0), 0), 2) as approval_rate
            FROM eclaim_instrument
            WHERE inst_code IS NOT NULL
            GROUP BY inst_code, inst_name
            ORDER BY total_claim DESC
            LIMIT 20
            """
        )
        if q16: questions.append((q16, 0, 0, 12, 8))

        # Instrument Approval Summary
        q17 = self.create_question(
            "สรุปการอนุมัติอุปกรณ์",
            "เปรียบเทียบยอดเบิกและอนุมัติ",
            """
            SELECT
                COUNT(*) as total_items,
                COALESCE(SUM(claim_qty), 0) as total_claim_qty,
                COALESCE(SUM(claim_amount), 0) as total_claim,
                COALESCE(SUM(reimb_qty), 0) as total_reimb_qty,
                COALESCE(SUM(reimb_amount), 0) as total_reimb,
                ROUND(COALESCE(SUM(reimb_amount), 0) * 100.0 / NULLIF(COALESCE(SUM(claim_amount), 0), 0), 2) as overall_approval_rate
            FROM eclaim_instrument
            """
        )
        if q17: questions.append((q17, 8, 0, 12, 3))

        dashboard_id = self.create_dashboard(
            "Instrument Analytics - อุปกรณ์การแพทย์",
            "Dashboard วิเคราะห์การเบิกอุปกรณ์การแพทย์"
        )
        if dashboard_id:
            for card_id, row, col, size_x, size_y in questions:
                self.add_card_to_dashboard(dashboard_id, card_id, row, col, size_x, size_y)

        # ============================================
        # Dashboard 7: Denial Analytics
        # ============================================
        print("\n❌ Creating Denial Analytics Dashboard...")

        questions = []

        # Deny Codes Summary
        q18 = self.create_question(
            "สรุป Deny Codes",
            "รหัสปฏิเสธที่พบบ่อย",
            """
            SELECT
                COALESCE(deny_code, 'ไม่ระบุ') as deny_code,
                COALESCE(fund_code, 'ไม่ระบุ') as fund_code,
                COUNT(*) as deny_count,
                COALESCE(SUM(claim_amount), 0) as total_denied_amount,
                COUNT(DISTINCT tran_id) as affected_cases
            FROM eclaim_deny
            GROUP BY deny_code, fund_code
            ORDER BY deny_count DESC
            LIMIT 20
            """
        )
        if q18: questions.append((q18, 0, 0, 12, 6))

        # Zero Paid Summary
        q19 = self.create_question(
            "รายการจ่าย 0 บาท",
            "รายการที่ไม่ได้รับชดเชย",
            """
            SELECT
                COALESCE(fund_code, 'ไม่ระบุ') as fund_code,
                COUNT(*) as count,
                SUM(claim_qty) as total_claim_qty,
                SUM(paid_qty) as total_paid_qty
            FROM eclaim_zero_paid
            GROUP BY fund_code
            ORDER BY count DESC
            LIMIT 20
            """
        )
        if q19: questions.append((q19, 6, 0, 12, 5))

        dashboard_id = self.create_dashboard(
            "Denial Analytics - รายการปฏิเสธ",
            "Dashboard วิเคราะห์รายการที่ถูกปฏิเสธ"
        )
        if dashboard_id:
            for card_id, row, col, size_x, size_y in questions:
                self.add_card_to_dashboard(dashboard_id, card_id, row, col, size_x, size_y)

        print("\n✅ All dashboards created successfully!")

    def run(self):
        """Main setup process"""
        print("=" * 50)
        print("🚀 Metabase Dashboard Setup")
        print("=" * 50)

        try:
            self.wait_for_metabase()

            if self.check_setup_needed():
                if not self.initial_setup():
                    return False
            else:
                if not self.login():
                    return False

            if not self.add_database():
                return False

            self.setup_dashboards()

            print("\n" + "=" * 50)
            print("✅ Setup Complete!")
            print("=" * 50)
            print(f"\n📊 Open Metabase: {METABASE_URL}")
            print(f"👤 Login: {ADMIN_EMAIL}")
            print(f"🔑 Password: {ADMIN_PASSWORD}")
            print("\nDashboards created:")
            print("  1. Financial Overview - ภาพรวมการเงิน")
            print("  2. Error Monitoring - ติดตาม Error")
            print("  3. DRG Analysis - วิเคราะห์ DRG")
            print("  4. Import Status - สถานะการ Import")

            return True

        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False


if __name__ == "__main__":
    setup = MetabaseSetup()
    success = setup.run()
    sys.exit(0 if success else 1)
