-- =============================================================================
-- E-Claim Database Schema - Merged Version (User's Structure + Tracking)
-- Based on existing hospital schema with added tracking capabilities
-- Created: 2026-01-08
-- =============================================================================

-- ============================================================================
-- 1. IMPORT TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_imported_files (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    -- File identification
    filename            VARCHAR(255) NOT NULL UNIQUE,
    file_type           VARCHAR(20) NOT NULL,  -- 'OP', 'IP', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO'
    hospital_code       VARCHAR(10) NOT NULL,

    -- File metadata
    file_date           DATE,
    file_sequence       VARCHAR(20),

    -- Import status
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_records       INT DEFAULT 0,
    imported_records    INT DEFAULT 0,
    failed_records      INT DEFAULT 0,

    -- Timestamps
    file_created_at     TIMESTAMP NULL,
    import_started_at   TIMESTAMP NULL,
    import_completed_at TIMESTAMP NULL,

    -- Error tracking
    error_message       TEXT,

    -- Audit
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT chk_file_type CHECK (file_type IN ('OP', 'IP', 'OPLGO', 'IPLGO', 'OPSSS', 'IPSSS', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO', 'OP_APPEAL', 'OP_APPEAL_CD')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial')),

    INDEX idx_file_type (file_type),
    INDEX idx_status (status),
    INDEX idx_file_date (file_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Track all imported E-Claim files from NHSO';

-- ============================================================================
-- 2. OP/IP CLAIMS TABLE (Based on claim_rep_opip_nhso_item)
-- ============================================================================
CREATE TABLE `claim_rep_opip_nhso_item` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,

  -- NEW: Tracking fields
  `file_id` INT UNSIGNED NULL COMMENT 'Reference to eclaim_imported_files',
  `row_number` INT NULL COMMENT 'Row number in original file',

  -- ORIGINAL: All existing fields from user's schema
  `rep_no` VARCHAR(15) DEFAULT NULL COMMENT 'REP No.',
  `seq` INT DEFAULT NULL COMMENT 'ลำดับที่',
  `tran_id` VARCHAR(15) DEFAULT NULL COMMENT 'TRAN_ID',
  `hn` VARCHAR(15) DEFAULT NULL COMMENT 'HN',
  `an` VARCHAR(15) DEFAULT NULL COMMENT 'AN',
  `pid` VARCHAR(20) DEFAULT NULL COMMENT 'เลขประจำตัวประชาชน',
  `name` VARCHAR(100) DEFAULT NULL COMMENT 'ชื่อ-สกุล',
  `ptype` CHAR(5) DEFAULT NULL COMMENT 'ประเภทผู้ป่วย (OP/IP/ORF)',
  `dateadm` DATETIME DEFAULT NULL COMMENT 'วันเข้ารักษา',
  `datedsc` DATETIME DEFAULT NULL COMMENT 'วันจำหน่าย',
  `reimb_nhso` DOUBLE(10,2) DEFAULT NULL COMMENT 'ชดเชยสุทธิจาก สปสช.',
  `reimb_agency` DOUBLE(10,2) DEFAULT NULL COMMENT 'ชดเชยสุทธิจากต้นสังกัด',
  `claim_from` VARCHAR(50) DEFAULT NULL COMMENT 'ชดเชยจาก',
  `error_code` VARCHAR(100) DEFAULT NULL COMMENT 'Error Code',
  `main_fund` VARCHAR(100) DEFAULT NULL COMMENT 'กองทุนหลัก',
  `sub_fund` VARCHAR(100) DEFAULT NULL COMMENT 'กองทุนย่อย',
  `service_type` CHAR(2) DEFAULT NULL COMMENT 'ประเภทบริการ',
  `chk_refer` CHAR(1) DEFAULT NULL COMMENT 'การรับส่งต่อ',
  `chk_right` CHAR(1) DEFAULT NULL COMMENT 'การมีสิทธิ',
  `chk_use_right` CHAR(1) DEFAULT NULL COMMENT 'การใช้สิทธิ',
  `chk` CHAR(1) DEFAULT NULL COMMENT 'ผลการตรวจสอบสิทธิ',
  `main_inscl` VARCHAR(5) DEFAULT NULL COMMENT 'สิทธิหลัก',
  `sub_inscl` VARCHAR(5) DEFAULT NULL COMMENT 'สิทธิย่อย',
  `href` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการ ที่ส่งต่อผู้ป่วยมา',
  `hcode` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการที่ให้การรักษา',
  `hmain` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการประจำ ตามข้อมูลของ รพ.',
  `prov1` VARCHAR(5) DEFAULT NULL COMMENT 'รหัสจังหวัดของหน่วยบริการที่ให้การรักษา',
  `rg1` VARCHAR(5) DEFAULT NULL COMMENT 'รหัสเขตหน่วยบริการ',
  `hmain2` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการประจำ ตามการตรวจสอบของ สปสช.',
  `prov2` VARCHAR(5) DEFAULT NULL COMMENT 'รหัสจังหวัดของหน่วยบริการประจำ',
  `rg2` VARCHAR(5) DEFAULT NULL COMMENT 'รหัสเขตของหน่วยบริการประจำ',
  `hmain3` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการ DMIS',
  `da` CHAR(1) DEFAULT NULL COMMENT 'โรคที่รักษาเกี่ยวเนื่องกับ DMIS',
  `projcode` VARCHAR(100) DEFAULT NULL COMMENT 'รหัสโครงการพิเศษ',
  `pa` CHAR(1) DEFAULT NULL COMMENT 'รหัสการขอแก้ไขข้อมูล',
  `drg` VARCHAR(10) DEFAULT NULL COMMENT 'DRG',
  `rw` DOUBLE(7,4) DEFAULT NULL COMMENT 'RW',
  `ca_type` CHAR(5) DEFAULT NULL COMMENT 'ประเภทการเบิกของมะเร็ง',
  `claim_drg` DOUBLE(10,2) DEFAULT NULL COMMENT 'ยอดเรียกเก็บ DRG',
  `claim_xdrg` DOUBLE(10,2) DEFAULT NULL COMMENT 'ยอดเรียกเก็บนอก DRG',
  `claim_net` DOUBLE(10,2) DEFAULT NULL COMMENT 'ยอดเรียกเก็บรวม',
  `claim_central_reimb` DOUBLE(10,2) DEFAULT NULL COMMENT 'เรียกเก็บ central reimburse',
  `paid` DOUBLE(10,2) DEFAULT NULL COMMENT 'ชำระเงินเอง',
  `pay_point` DOUBLE(10,2) DEFAULT NULL COMMENT 'อัตราจ่าย/Point',
  `ps_chk` CHAR(1) DEFAULT NULL COMMENT 'รหัสการส่งข้อมูลล่าช้า',
  `ps_percent` VARCHAR(5) DEFAULT NULL COMMENT 'ล่าช้า',
  `ccuf` DOUBLE(7,4) DEFAULT NULL COMMENT 'Cancer Chemotherapy Unbundling Factor',
  `adjrw_nhso` DOUBLE(7,4) DEFAULT NULL COMMENT 'Adj.RW จาก สปสช.',
  `adjrw2` DOUBLE(7,4) DEFAULT NULL COMMENT 'AdjRW2',
  `reimb_amt` DOUBLE(10,2) DEFAULT NULL COMMENT 'จ่ายชดเชย',
  `act_amt` DOUBLE(10,2) DEFAULT NULL COMMENT 'ค่าพรบ.',
  `salary_rate` VARCHAR(5) DEFAULT NULL COMMENT 'หักเงินเดือนร้อยละ',
  `salary_amt` DOUBLE(10,2) DEFAULT NULL COMMENT 'จำนวนที่หักเงินเดือน',
  `reimb_diff_salary` DOUBLE(10,2) DEFAULT NULL COMMENT 'ยอดชดเชยหลังหักเงินเดือน',

  -- High Cost
  `iphc` DOUBLE(10,2) DEFAULT NULL COMMENT 'ค่าใช้จ่ายสูง (IP)',
  `ophc` DOUBLE(10,2) DEFAULT NULL COMMENT 'ค่าใช้จ่ายสูง (OP)',

  -- Accident & Emergency
  `ae_opae` DOUBLE(10,2) DEFAULT NULL COMMENT 'อุบัติเหตุฉุกเฉิน OP',
  `ae_ipnb` DOUBLE(10,2) DEFAULT NULL COMMENT 'AE - เด็กแรกเกิด',
  `ae_ipuc` DOUBLE(10,2) DEFAULT NULL COMMENT 'AE - สิทธิว่าง',
  `ae_ip3sss` DOUBLE(10,2) DEFAULT NULL COMMENT 'AE - ประกันสังคม 3 เดือน',
  `ae_ip7sss` DOUBLE(10,2) DEFAULT NULL COMMENT 'AE - ประกันสังคม 7 เดือน',
  `ae_carae` DOUBLE(10,2) DEFAULT NULL COMMENT 'AE - คลอด',
  `ae_caref` DOUBLE(10,2) DEFAULT NULL COMMENT 'AE - refer ปกติ',
  `ae_caref_puc` DOUBLE(10,2) DEFAULT NULL COMMENT 'AE - refer สิทธิว่าง',

  -- Prosthetics/Equipment
  `opinst` DOUBLE(10,2) DEFAULT NULL COMMENT 'อวัยวะเทียม OP',
  `inst` DOUBLE(10,2) DEFAULT NULL COMMENT 'อวัยวะเทียม IP',

  -- Inpatient
  `ipaec` DOUBLE(10,2) DEFAULT NULL,
  `ipaer` DOUBLE(10,2) DEFAULT NULL,
  `ipinrgc` DOUBLE(10,2) DEFAULT NULL,
  `ipinrgr` DOUBLE(10,2) DEFAULT NULL,
  `ipinspsn` DOUBLE(10,2) DEFAULT NULL,
  `ipprcc` DOUBLE(10,2) DEFAULT NULL,
  `ipprcc_puc` DOUBLE(10,2) DEFAULT NULL,
  `ipbkk_inst` DOUBLE(10,2) DEFAULT NULL,
  `ip_ontop` DOUBLE(10,2) DEFAULT NULL,

  -- DMIS
  `cataract_amt` DOUBLE(10,2) DEFAULT NULL COMMENT 'ยอด cataract',
  `cataract_oth` DOUBLE(10,2) DEFAULT NULL COMMENT 'cataract - ค่าภาระงาน(สสจ.)',
  `cataract_hosp` DOUBLE(10,2) DEFAULT NULL COMMENT 'cataract - ค่าภาระงาน(รพ.)',
  `dmis_catinst` DOUBLE(10,2) DEFAULT NULL,
  `dmisrc_amt` DOUBLE(10,2) DEFAULT NULL,
  `dmisrc_workload` DOUBLE(10,2) DEFAULT NULL,
  `rcuhosc_amt` DOUBLE(10,2) DEFAULT NULL,
  `rcuhosc_workload` DOUBLE(10,2) DEFAULT NULL,
  `rcuhosr_amt` DOUBLE(10,2) DEFAULT NULL,
  `rcuhosr_workload` DOUBLE(10,2) DEFAULT NULL,
  `dmis_llop` DOUBLE(10,2) DEFAULT NULL,
  `dmis_llrgc` DOUBLE(10,2) DEFAULT NULL,
  `dmis_llrgr` DOUBLE(10,2) DEFAULT NULL,
  `dmis_lp` DOUBLE(10,2) DEFAULT NULL,
  `dmis_stroke_drug` DOUBLE(10,2) DEFAULT NULL,
  `dmis_dmidml` DOUBLE(10,2) DEFAULT NULL,
  `dmis_pp` DOUBLE(10,2) DEFAULT NULL,
  `dmis_dmishd` DOUBLE(10,2) DEFAULT NULL,
  `dmis_dmicnt` DOUBLE(10,2) DEFAULT NULL,
  `dmis_paliative` DOUBLE(10,2) DEFAULT NULL,
  `dmis_dm` DOUBLE(10,2) DEFAULT NULL,

  -- Drug
  `drug` DOUBLE(10,2) DEFAULT NULL,

  -- OP Bangkok
  `opbkk_hc` DOUBLE(10,2) DEFAULT NULL,
  `opbkk_dent` DOUBLE(10,2) DEFAULT NULL,
  `opbkk_drug` DOUBLE(10,2) DEFAULT NULL,
  `opbkk_fs` DOUBLE(10,2) DEFAULT NULL,
  `opbkk_others` DOUBLE(10,2) DEFAULT NULL,
  `opbkk_hsub` VARCHAR(100) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,
  `opbkk_nhso` VARCHAR(100) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,

  -- Denial
  `deny_hc` VARCHAR(10) DEFAULT NULL,
  `deny_ae` VARCHAR(10) DEFAULT NULL,
  `deny_inst` VARCHAR(10) DEFAULT NULL,
  `deny_ip` VARCHAR(10) DEFAULT NULL,
  `deny_dmis` VARCHAR(10) DEFAULT NULL,

  -- Base Rate
  `baserate_old` DOUBLE(10,2) DEFAULT NULL,
  `baserate_add` DOUBLE(10,2) DEFAULT NULL,
  `baserate_total` DOUBLE(10,2) DEFAULT NULL,

  -- Other
  `fs` DOUBLE(10,2) DEFAULT NULL,
  `va` DOUBLE(10,2) DEFAULT NULL,
  `remark` VARCHAR(100) DEFAULT NULL,
  `audit_results` VARCHAR(255) DEFAULT NULL,
  `payment_type` VARCHAR(255) DEFAULT NULL,
  `seq_no` VARCHAR(15) DEFAULT NULL,
  `invoice_no` VARCHAR(20) DEFAULT NULL,
  `invoice_lt` VARCHAR(20) DEFAULT NULL,
  `scheme` VARCHAR(10) DEFAULT NULL COMMENT 'Insurance scheme: UCS, LGO, SSS, OFC',

  -- ORIGINAL: Hospital internal fields
  `inp_id` INT DEFAULT NULL,
  `inp_date` DATETIME DEFAULT NULL,
  `lastupdate` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  -- NEW: HIS Reconciliation Fields
  `his_matched` BOOLEAN DEFAULT FALSE COMMENT 'Matched with HIS data',
  `his_matched_at` DATETIME NULL COMMENT 'When matched',
  `his_vn` VARCHAR(20) NULL COMMENT 'VN from HIS',
  `his_amount_diff` DOUBLE(10,2) NULL COMMENT 'Difference in amount (e-claim vs HIS)',
  `reconcile_status` VARCHAR(20) NULL COMMENT 'pending/matched/mismatched/manual',
  `reconcile_note` TEXT NULL COMMENT 'Reconciliation notes',

  PRIMARY KEY (`id`),

  -- NEW: Foreign key to tracking table
  FOREIGN KEY (`file_id`) REFERENCES `eclaim_imported_files`(`id`) ON DELETE SET NULL,

  -- ORIGINAL: All existing indexes
  KEY `rep_no` (`rep_no`,`tran_id`) USING BTREE,
  KEY `hn` (`hn`) USING BTREE,
  KEY `pid` (`pid`) USING BTREE,
  KEY `dateadm` (`dateadm`) USING BTREE,
  KEY `an` (`an`) USING BTREE,
  KEY `tran_id` (`tran_id`),
  KEY `error_code` (`error_code`),

  -- NEW: Additional indexes
  KEY `idx_file_id` (`file_id`),
  KEY `idx_scheme` (`scheme`),
  KEY `idx_reconcile` (`his_matched`, `reconcile_status`),

  -- NEW: Unique constraint for UPSERT
  UNIQUE KEY `uq_tran_file` (`tran_id`, `file_id`)

) ENGINE=InnoDB DEFAULT CHARSET=tis620
COMMENT='OP/IP Claims from NHSO E-Claim (merged with tracking)';

-- ============================================================================
-- 3. OP REFER TABLE (Based on claim_rep_orf_nhso_item)
-- ============================================================================
CREATE TABLE `claim_rep_orf_nhso_item` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,

  -- NEW: Tracking fields
  `file_id` INT UNSIGNED NULL COMMENT 'Reference to eclaim_imported_files',
  `row_number` INT NULL COMMENT 'Row number in original file',

  -- ORIGINAL: All existing fields from user's schema
  `rep_no` VARCHAR(15) DEFAULT NULL COMMENT 'REP No.',
  `no` INT DEFAULT NULL COMMENT 'NO.',
  `tran_id` VARCHAR(15) DEFAULT NULL COMMENT 'TRAN_ID',
  `hn` VARCHAR(15) DEFAULT NULL COMMENT 'HN',
  `pid` VARCHAR(20) DEFAULT NULL COMMENT 'เลขประจำตัวประชาชน',
  `name` VARCHAR(100) DEFAULT NULL COMMENT 'ชื่อ-สกุล',
  `service_date` DATETIME DEFAULT NULL COMMENT 'ว/ด/ป ที่รับบริการ',
  `refer_no` VARCHAR(20) DEFAULT NULL COMMENT 'เลขที่ใบส่งต่อ',

  -- Hospital codes
  `htype1` VARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Htype1)',
  `prov1` VARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Prov1)',
  `hcode` VARCHAR(100) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Hcode)',
  `htype2` VARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Htype2)',
  `prov2` VARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Prov2)',
  `hmain2` VARCHAR(100) DEFAULT NULL COMMENT 'หน่วยบริการประจำ(Hmain2)',
  `href` VARCHAR(100) DEFAULT NULL COMMENT 'หน่วยบริการรับส่งต่อ(Href)',

  -- Diagnosis & Procedure
  `dx` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสโรคที่ refer',
  `proc` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหัตถการที่ refer',
  `dmis` VARCHAR(100) DEFAULT NULL,
  `hmain3` VARCHAR(100) DEFAULT NULL,
  `dar` VARCHAR(100) DEFAULT NULL,
  `ca_type` CHAR(5) DEFAULT NULL COMMENT 'ประเภทการเบิกของมะเร็ง',

  -- Billing Amounts
  `claim_amt` DOUBLE(10,2) DEFAULT NULL COMMENT 'ยอดรวมค่าใช้จ่าย(เฉพาะเบิกได้)',
  `central_reimb_case` VARCHAR(20) DEFAULT NULL COMMENT 'เข้าเกณฑ์ central reimburse กรณี',
  `central_reimb_amt` DOUBLE(10,2) DEFAULT NULL COMMENT 'จำนวนเงินเข้าเกณฑ์ central reimburse',
  `paid` DOUBLE(10,2) DEFAULT NULL COMMENT 'ชำระเอง',
  `act_amt` DOUBLE(10,2) DEFAULT NULL COMMENT 'พรบ.',

  -- OP Refer Amounts
  `opref_list` DOUBLE(10,2) DEFAULT NULL COMMENT 'รายการ OPREF',
  `opref_bef_adj` DOUBLE(10,2) DEFAULT NULL COMMENT 'ค่ารักษาอื่นๆ ก่อนปรับลด',
  `opref_aft_adj` DOUBLE(10,2) DEFAULT NULL COMMENT 'ค่ารักษาอื่นๆ หลังปรับลด',
  `total` DOUBLE(10,2) DEFAULT NULL COMMENT 'ผลรวมทั้ง Case',

  -- Responsible Parties
  `respon_cup` DOUBLE(10,2) DEFAULT NULL COMMENT 'CUP / จังหวัด (<=1600)',
  `respon_nhso` DOUBLE(10,2) DEFAULT NULL COMMENT 'สปสช (>1600)',

  -- Net Reimbursement
  `reimb_total` DOUBLE(10,2) DEFAULT NULL COMMENT 'ชดเชยสุทธิ (บาท)',
  `pay_by` VARCHAR(50) DEFAULT NULL COMMENT 'ชำระบัญชีโดย',
  `ps` CHAR(1) DEFAULT NULL COMMENT 'รหัสการส่งข้อมูลล่าช้า',

  -- Central Reimburse Detail - OPHC
  `cr_ophc_hc01` DOUBLE(10,2) DEFAULT NULL,
  `cr_ophc_hc02` DOUBLE(10,2) DEFAULT NULL,
  `cr_ophc_hc03` DOUBLE(10,2) DEFAULT NULL,
  `cr_ophc_hc04` DOUBLE(10,2) DEFAULT NULL,
  `cr_ophc_hc05` DOUBLE(10,2) DEFAULT NULL,
  `cr_ophc_hc06` DOUBLE(10,2) DEFAULT NULL,
  `cr_ophc_hc07` DOUBLE(10,2) DEFAULT NULL,
  `cr_ophc_hc08` DOUBLE(10,2) DEFAULT NULL,

  -- Other Funds
  `cr_ae04` DOUBLE(10,2) DEFAULT NULL,
  `cr_carae_ae08` DOUBLE(10,2) DEFAULT NULL,
  `cr_opinst_hc09` DOUBLE(10,2) DEFAULT NULL,
  `cr_dmisrc_amt` DOUBLE(10,2) DEFAULT NULL,
  `cr_dmisrc_workload` DOUBLE(10,2) DEFAULT NULL,
  `cr_rcuhosc_amt` DOUBLE(10,2) DEFAULT NULL,
  `cr_rcuhosc_workload` DOUBLE(10,2) DEFAULT NULL,
  `cr_rcuhosr_amt` DOUBLE(10,2) DEFAULT NULL,
  `cr_rcuhosr_workload` DOUBLE(10,2) DEFAULT NULL,
  `cr_llop` DOUBLE(10,2) DEFAULT NULL,
  `cr_lp` DOUBLE(10,2) DEFAULT NULL,
  `cr_stroke_drug` DOUBLE(10,2) DEFAULT NULL,
  `cr_dmidml` DOUBLE(10,2) DEFAULT NULL,
  `cr_pp` DOUBLE(10,2) DEFAULT NULL,
  `cr_dmishd` DOUBLE(10,2) DEFAULT NULL,
  `cr_paliative` DOUBLE(10,2) DEFAULT NULL,
  `cr_drug` DOUBLE(10,2) DEFAULT NULL,
  `cr_ontop` DOUBLE(10,2) DEFAULT NULL,
  `cr_total` DOUBLE(10,2) DEFAULT NULL,
  `cr_by` VARCHAR(100) DEFAULT NULL,

  -- Detailed Expenses (16 Categories x 2 = 32 columns)
  `oprefer_md01_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md01_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md02_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md02_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md03_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md03_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md04_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md04_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md05_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md05_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md06_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md06_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md07_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md07_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md08_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md08_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md09_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md09_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md10_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md10_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md11_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md11_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md12_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md12_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md13_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md13_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md14_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md14_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md15_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md15_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md16_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md16_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md17_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md17_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md18_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md18_free` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md19_claim` DOUBLE(10,2) DEFAULT NULL,
  `oprefer_md19_free` DOUBLE(10,2) DEFAULT NULL,

  -- Error & Status
  `error_code` VARCHAR(100) DEFAULT NULL,
  `deny_hc` VARCHAR(10) DEFAULT NULL,
  `deny_ae` VARCHAR(10) DEFAULT NULL,
  `deny_inst` VARCHAR(10) DEFAULT NULL,
  `deny_dmis` VARCHAR(10) DEFAULT NULL,

  -- Other
  `va` DOUBLE(10,2) DEFAULT NULL,
  `remark` VARCHAR(100) DEFAULT NULL,
  `audit_results` VARCHAR(255) DEFAULT NULL,
  `payment_type` VARCHAR(255) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,
  `seq_no` VARCHAR(15) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,
  `invoice_no` VARCHAR(20) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,
  `invoice_lt` VARCHAR(20) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,

  -- ORIGINAL: Hospital internal fields
  `inp_id` INT DEFAULT NULL,
  `inp_date` DATETIME DEFAULT NULL,
  `lastupdate` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  -- NEW: Scheme field for filtering
  `scheme` VARCHAR(10) DEFAULT NULL COMMENT 'Insurance scheme: UCS, OFC, SSS, LGO',

  -- NEW: HIS Reconciliation Fields
  `his_matched` BOOLEAN DEFAULT FALSE COMMENT 'Matched with HIS data',
  `his_matched_at` DATETIME NULL COMMENT 'When matched',
  `his_vn` VARCHAR(20) NULL COMMENT 'VN from HIS',
  `his_amount_diff` DOUBLE(10,2) NULL COMMENT 'Difference in amount (e-claim vs HIS)',
  `reconcile_status` VARCHAR(20) NULL COMMENT 'pending/matched/mismatched/manual',
  `reconcile_note` TEXT NULL COMMENT 'Reconciliation notes',

  PRIMARY KEY (`id`),

  -- NEW: Foreign key to tracking table
  FOREIGN KEY (`file_id`) REFERENCES `eclaim_imported_files`(`id`) ON DELETE SET NULL,

  -- ORIGINAL: All existing indexes
  KEY `rep_no` (`rep_no`,`tran_id`) USING BTREE,
  KEY `hn` (`hn`) USING BTREE,
  KEY `pid` (`pid`) USING BTREE,
  KEY `service_date` (`service_date`) USING BTREE,

  -- NEW: Additional indexes
  KEY `idx_file_id` (`file_id`),
  KEY `idx_scheme` (`scheme`),
  KEY `idx_reconcile` (`his_matched`, `reconcile_status`),

  -- NEW: Unique constraint for UPSERT
  UNIQUE KEY `uq_tran_file` (`tran_id`, `file_id`)

) ENGINE=InnoDB DEFAULT CHARSET=tis620
COMMENT='OP Refer (ORF) Claims from NHSO E-Claim (merged with tracking)';

-- ============================================================================
-- 4. VIEWS FOR REPORTING
-- ============================================================================

-- Daily summary view
CREATE OR REPLACE VIEW v_daily_claim_summary AS
SELECT
    DATE(c.dateadm) as service_date,
    c.ptype,
    c.main_inscl,
    COUNT(*) as claim_count,
    SUM(c.reimb_nhso) as total_reimbursement,
    SUM(CASE WHEN c.error_code IS NOT NULL AND c.error_code != '-' THEN 1 ELSE 0 END) as error_count,
    SUM(CASE WHEN c.his_matched THEN 1 ELSE 0 END) as matched_count
FROM claim_rep_opip_nhso_item c
GROUP BY DATE(c.dateadm), c.ptype, c.main_inscl
ORDER BY service_date DESC, ptype, main_inscl;

-- Unmatched claims for reconciliation
CREATE OR REPLACE VIEW v_unmatched_claims AS
SELECT
    c.id,
    c.tran_id,
    c.hn,
    c.an,
    c.pid,
    c.name,
    c.ptype,
    c.dateadm,
    c.datedsc,
    c.reimb_nhso,
    c.error_code,
    f.filename,
    f.file_date
FROM claim_rep_opip_nhso_item c
LEFT JOIN eclaim_imported_files f ON c.file_id = f.id
WHERE c.his_matched = FALSE
ORDER BY c.dateadm DESC;

-- Import status summary
CREATE OR REPLACE VIEW v_import_status AS
SELECT
    f.file_type,
    f.status,
    COUNT(*) as file_count,
    SUM(f.total_records) as total_records,
    SUM(f.imported_records) as imported_records,
    SUM(f.failed_records) as failed_records,
    MIN(f.file_date) as earliest_file,
    MAX(f.file_date) as latest_file
FROM eclaim_imported_files f
GROUP BY f.file_type, f.status
ORDER BY f.file_type, f.status;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
