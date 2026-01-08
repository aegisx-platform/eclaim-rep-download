-- =============================================================================
-- E-Claim Database Schema - Merged Version (User's Structure + Tracking)
-- Based on existing hospital schema with added tracking capabilities
-- Created: 2026-01-08
-- =============================================================================

-- ============================================================================
-- 1. IMPORT TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_imported_files (
    id                  SERIAL PRIMARY KEY,

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
    CONSTRAINT chk_file_type CHECK (file_type IN ('OP', 'IP', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial')),

    INDEX idx_file_type (file_type),
    INDEX idx_status (status),
    INDEX idx_file_date (file_date)
) 


-- ============================================================================
-- 2. OP/IP CLAIMS TABLE (Based on claim_rep_opip_nhso_item)
-- ============================================================================
CREATE TABLE `claim_rep_opip_nhso_item` (
  `id` INTEGER NOT NULL AUTO_INCREMENT,

  -- NEW: Tracking fields
  `file_id` INTEGER NULL COMMENT 'Reference to eclaim_imported_files',
  `row_number` INT NULL COMMENT 'Row number in original file',

  -- ORIGINAL: All existing fields from user's schema
  `rep_no` VARCHAR(15) DEFAULT NULL COMMENT 'REP No.',
  `seq` INT DEFAULT NULL COMMENT 'ลำดับที่',
  `tran_id` VARCHAR(15) DEFAULT NULL COMMENT 'TRAN_ID',
  `hn` VARCHAR(15) DEFAULT NULL COMMENT 'HN',
  `an` VARCHAR(15) DEFAULT NULL COMMENT 'AN',
  `pid` VARCHAR(20) DEFAULT NULL COMMENT 'เลขประจำตัวประชาชน',
  `name` VARCHAR(100) DEFAULT NULL COMMENT 'ชื่อ-สกุล',
  `ptype` VARCHAR(5) DEFAULT NULL COMMENT 'ประเภทผู้ป่วย (OP/IP/ORF)',
  `dateadm` DATETIME DEFAULT NULL COMMENT 'วันเข้ารักษา',
  `datedsc` DATETIME DEFAULT NULL COMMENT 'วันจำหน่าย',
  `reimb_nhso` DECIMAL(10,2) DEFAULT NULL COMMENT 'ชดเชยสุทธิจาก สปสช.',
  `reimb_agency` DECIMAL(10,2) DEFAULT NULL COMMENT 'ชดเชยสุทธิจากต้นสังกัด',
  `claim_from` VARCHAR(50) DEFAULT NULL COMMENT 'ชดเชยจาก',
  `error_code` VARCHAR(100) DEFAULT NULL COMMENT 'Error Code',
  `main_fund` VARCHAR(100) DEFAULT NULL COMMENT 'กองทุนหลัก',
  `sub_fund` VARCHAR(100) DEFAULT NULL COMMENT 'กองทุนย่อย',
  `service_type` VARCHAR(2) DEFAULT NULL COMMENT 'ประเภทบริการ',
  `chk_refer` VARCHAR(1) DEFAULT NULL COMMENT 'การรับส่งต่อ',
  `chk_right` VARCHAR(1) DEFAULT NULL COMMENT 'การมีสิทธิ',
  `chk_use_right` VARCHAR(1) DEFAULT NULL COMMENT 'การใช้สิทธิ',
  `chk` VARCHAR(1) DEFAULT NULL COMMENT 'ผลการตรวจสอบสิทธิ',
  `main_inscl` VARVARCHAR(5) DEFAULT NULL COMMENT 'สิทธิหลัก',
  `sub_inscl` VARVARCHAR(5) DEFAULT NULL COMMENT 'สิทธิย่อย',
  `href` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการ ที่ส่งต่อผู้ป่วยมา',
  `hcode` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการที่ให้การรักษา',
  `hmain` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการประจำ ตามข้อมูลของ รพ.',
  `prov1` VARVARCHAR(5) DEFAULT NULL COMMENT 'รหัสจังหวัดของหน่วยบริการที่ให้การรักษา',
  `rg1` VARVARCHAR(5) DEFAULT NULL COMMENT 'รหัสเขตหน่วยบริการ',
  `hmain2` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการประจำ ตามการตรวจสอบของ สปสช.',
  `prov2` VARVARCHAR(5) DEFAULT NULL COMMENT 'รหัสจังหวัดของหน่วยบริการประจำ',
  `rg2` VARVARCHAR(5) DEFAULT NULL COMMENT 'รหัสเขตของหน่วยบริการประจำ',
  `hmain3` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหน่วยบริการ DMIS',
  `da` VARCHAR(1) DEFAULT NULL COMMENT 'โรคที่รักษาเกี่ยวเนื่องกับ DMIS',
  `projcode` VARCHAR(100) DEFAULT NULL COMMENT 'รหัสโครงการพิเศษ',
  `pa` VARCHAR(1) DEFAULT NULL COMMENT 'รหัสการขอแก้ไขข้อมูล',
  `drg` VARCHAR(10) DEFAULT NULL COMMENT 'DRG',
  `rw` DECIMAL(7,4) DEFAULT NULL COMMENT 'RW',
  `ca_type` VARCHAR(5) DEFAULT NULL COMMENT 'ประเภทการเบิกของมะเร็ง',
  `claim_drg` DECIMAL(10,2) DEFAULT NULL COMMENT 'ยอดเรียกเก็บ DRG',
  `claim_xdrg` DECIMAL(10,2) DEFAULT NULL COMMENT 'ยอดเรียกเก็บนอก DRG',
  `claim_net` DECIMAL(10,2) DEFAULT NULL COMMENT 'ยอดเรียกเก็บรวม',
  `claim_central_reimb` DECIMAL(10,2) DEFAULT NULL COMMENT 'เรียกเก็บ central reimburse',
  `paid` DECIMAL(10,2) DEFAULT NULL COMMENT 'ชำระเงินเอง',
  `pay_point` DECIMAL(10,2) DEFAULT NULL COMMENT 'อัตราจ่าย/Point',
  `ps_chk` VARCHAR(1) DEFAULT NULL COMMENT 'รหัสการส่งข้อมูลล่าช้า',
  `ps_percent` VARVARCHAR(5) DEFAULT NULL COMMENT 'ล่าช้า',
  `ccuf` DECIMAL(7,4) DEFAULT NULL COMMENT 'Cancer Chemotherapy Unbundling Factor',
  `adjrw_nhso` DECIMAL(7,4) DEFAULT NULL COMMENT 'Adj.RW จาก สปสช.',
  `adjrw2` DECIMAL(7,4) DEFAULT NULL COMMENT 'AdjRW2',
  `reimb_amt` DECIMAL(10,2) DEFAULT NULL COMMENT 'จ่ายชดเชย',
  `act_amt` DECIMAL(10,2) DEFAULT NULL COMMENT 'ค่าพรบ.',
  `salary_rate` VARVARCHAR(5) DEFAULT NULL COMMENT 'หักเงินเดือนร้อยละ',
  `salary_amt` DECIMAL(10,2) DEFAULT NULL COMMENT 'จำนวนที่หักเงินเดือน',
  `reimb_diff_salary` DECIMAL(10,2) DEFAULT NULL COMMENT 'ยอดชดเชยหลังหักเงินเดือน',

  -- High Cost
  `iphc` DECIMAL(10,2) DEFAULT NULL COMMENT 'ค่าใช้จ่ายสูง (IP)',
  `ophc` DECIMAL(10,2) DEFAULT NULL COMMENT 'ค่าใช้จ่ายสูง (OP)',

  -- Accident & Emergency
  `ae_opae` DECIMAL(10,2) DEFAULT NULL COMMENT 'อุบัติเหตุฉุกเฉิน OP',
  `ae_ipnb` DECIMAL(10,2) DEFAULT NULL COMMENT 'AE - เด็กแรกเกิด',
  `ae_ipuc` DECIMAL(10,2) DEFAULT NULL COMMENT 'AE - สิทธิว่าง',
  `ae_ip3sss` DECIMAL(10,2) DEFAULT NULL COMMENT 'AE - ประกันสังคม 3 เดือน',
  `ae_ip7sss` DECIMAL(10,2) DEFAULT NULL COMMENT 'AE - ประกันสังคม 7 เดือน',
  `ae_carae` DECIMAL(10,2) DEFAULT NULL COMMENT 'AE - คลอด',
  `ae_caref` DECIMAL(10,2) DEFAULT NULL COMMENT 'AE - refer ปกติ',
  `ae_caref_puc` DECIMAL(10,2) DEFAULT NULL COMMENT 'AE - refer สิทธิว่าง',

  -- Prosthetics/Equipment
  `opinst` DECIMAL(10,2) DEFAULT NULL COMMENT 'อวัยวะเทียม OP',
  `inst` DECIMAL(10,2) DEFAULT NULL COMMENT 'อวัยวะเทียม IP',

  -- Inpatient
  `ipaec` DECIMAL(10,2) DEFAULT NULL,
  `ipaer` DECIMAL(10,2) DEFAULT NULL,
  `ipinrgc` DECIMAL(10,2) DEFAULT NULL,
  `ipinrgr` DECIMAL(10,2) DEFAULT NULL,
  `ipinspsn` DECIMAL(10,2) DEFAULT NULL,
  `ipprcc` DECIMAL(10,2) DEFAULT NULL,
  `ipprcc_puc` DECIMAL(10,2) DEFAULT NULL,
  `ipbkk_inst` DECIMAL(10,2) DEFAULT NULL,
  `ip_ontop` DECIMAL(10,2) DEFAULT NULL,

  -- DMIS
  `cataract_amt` DECIMAL(10,2) DEFAULT NULL COMMENT 'ยอด cataract',
  `cataract_oth` DECIMAL(10,2) DEFAULT NULL COMMENT 'cataract - ค่าภาระงาน(สสจ.)',
  `cataract_hosp` DECIMAL(10,2) DEFAULT NULL COMMENT 'cataract - ค่าภาระงาน(รพ.)',
  `dmis_catinst` DECIMAL(10,2) DEFAULT NULL,
  `dmisrc_amt` DECIMAL(10,2) DEFAULT NULL,
  `dmisrc_workload` DECIMAL(10,2) DEFAULT NULL,
  `rcuhosc_amt` DECIMAL(10,2) DEFAULT NULL,
  `rcuhosc_workload` DECIMAL(10,2) DEFAULT NULL,
  `rcuhosr_amt` DECIMAL(10,2) DEFAULT NULL,
  `rcuhosr_workload` DECIMAL(10,2) DEFAULT NULL,
  `dmis_llop` DECIMAL(10,2) DEFAULT NULL,
  `dmis_llrgc` DECIMAL(10,2) DEFAULT NULL,
  `dmis_llrgr` DECIMAL(10,2) DEFAULT NULL,
  `dmis_lp` DECIMAL(10,2) DEFAULT NULL,
  `dmis_stroke_drug` DECIMAL(10,2) DEFAULT NULL,
  `dmis_dmidml` DECIMAL(10,2) DEFAULT NULL,
  `dmis_pp` DECIMAL(10,2) DEFAULT NULL,
  `dmis_dmishd` DECIMAL(10,2) DEFAULT NULL,
  `dmis_dmicnt` DECIMAL(10,2) DEFAULT NULL,
  `dmis_paliative` DECIMAL(10,2) DEFAULT NULL,
  `dmis_dm` DECIMAL(10,2) DEFAULT NULL,

  -- Drug
  `drug` DECIMAL(10,2) DEFAULT NULL,

  -- OP Bangkok
  `opbkk_hc` DECIMAL(10,2) DEFAULT NULL,
  `opbkk_dent` DECIMAL(10,2) DEFAULT NULL,
  `opbkk_drug` DECIMAL(10,2) DEFAULT NULL,
  `opbkk_fs` DECIMAL(10,2) DEFAULT NULL,
  `opbkk_others` DECIMAL(10,2) DEFAULT NULL,
  `opbkk_hsub` VARCHAR(100) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,
  `opbkk_nhso` VARCHAR(100) CHARACTER SET tis620 COLLATE tis620_thai_ci DEFAULT NULL,

  -- Denial
  `deny_hc` VARCHAR(10) DEFAULT NULL,
  `deny_ae` VARCHAR(10) DEFAULT NULL,
  `deny_inst` VARCHAR(10) DEFAULT NULL,
  `deny_ip` VARCHAR(10) DEFAULT NULL,
  `deny_dmis` VARCHAR(10) DEFAULT NULL,

  -- Base Rate
  `baserate_old` DECIMAL(10,2) DEFAULT NULL,
  `baserate_add` DECIMAL(10,2) DEFAULT NULL,
  `baserate_total` DECIMAL(10,2) DEFAULT NULL,

  -- Other
  `fs` DECIMAL(10,2) DEFAULT NULL,
  `va` DECIMAL(10,2) DEFAULT NULL,
  `remark` VARCHAR(100) DEFAULT NULL,
  `audit_results` VARCHAR(255) DEFAULT NULL,
  `payment_type` VARCHAR(255) DEFAULT NULL,
  `seq_no` VARCHAR(15) DEFAULT NULL,
  `invoice_no` VARCHAR(20) DEFAULT NULL,
  `invoice_lt` VARCHAR(20) DEFAULT NULL,

  -- ORIGINAL: Hospital internal fields
  `inp_id` INT DEFAULT NULL,
  `inp_date` DATETIME DEFAULT NULL,
  `lastupdate` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

  -- NEW: HIS Reconciliation Fields
  `his_matched` BOOLEAN DEFAULT FALSE COMMENT 'Matched with HIS data',
  `his_matched_at` DATETIME NULL COMMENT 'When matched',
  `his_vn` VARCHAR(20) NULL COMMENT 'VN from HIS',
  `his_amount_diff` DECIMAL(10,2) NULL COMMENT 'Difference in amount (e-claim vs HIS)',
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
  KEY `idx_reconcile` (`his_matched`, `reconcile_status`),

  -- NEW: Unique constraint for UPSERT
  UNIQUE KEY `uq_tran_file` (`tran_id`, `file_id`)

) 


-- ============================================================================
-- 3. OP REFER TABLE (Based on claim_rep_orf_nhso_item)
-- ============================================================================
CREATE TABLE `claim_rep_orf_nhso_item` (
  `id` INTEGER NOT NULL AUTO_INCREMENT,

  -- NEW: Tracking fields
  `file_id` INTEGER NULL COMMENT 'Reference to eclaim_imported_files',
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
  `htype1` VARVARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Htype1)',
  `prov1` VARVARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Prov1)',
  `hcode` VARCHAR(100) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Hcode)',
  `htype2` VARVARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Htype2)',
  `prov2` VARVARCHAR(5) DEFAULT NULL COMMENT 'หน่วยบริการรักษา(Prov2)',
  `hmain2` VARCHAR(100) DEFAULT NULL COMMENT 'หน่วยบริการประจำ(Hmain2)',
  `href` VARCHAR(100) DEFAULT NULL COMMENT 'หน่วยบริการรับส่งต่อ(Href)',

  -- Diagnosis & Procedure
  `dx` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสโรคที่ refer',
  `proc` VARCHAR(10) DEFAULT NULL COMMENT 'รหัสหัตถการที่ refer',
  `dmis` VARCHAR(100) DEFAULT NULL,
  `hmain3` VARCHAR(100) DEFAULT NULL,
  `dar` VARCHAR(100) DEFAULT NULL,
  `ca_type` VARCHAR(5) DEFAULT NULL COMMENT 'ประเภทการเบิกของมะเร็ง',

  -- Billing Amounts
  `claim_amt` DECIMAL(10,2) DEFAULT NULL COMMENT 'ยอดรวมค่าใช้จ่าย(เฉพาะเบิกได้)',
  `central_reimb_case` VARCHAR(20) DEFAULT NULL COMMENT 'เข้าเกณฑ์ central reimburse กรณี',
  `central_reimb_amt` DECIMAL(10,2) DEFAULT NULL COMMENT 'จำนวนเงินเข้าเกณฑ์ central reimburse',
  `paid` DECIMAL(10,2) DEFAULT NULL COMMENT 'ชำระเอง',
  `act_amt` DECIMAL(10,2) DEFAULT NULL COMMENT 'พรบ.',

  -- OP Refer Amounts
  `opref_list` DECIMAL(10,2) DEFAULT NULL COMMENT 'รายการ OPREF',
  `opref_bef_adj` DECIMAL(10,2) DEFAULT NULL COMMENT 'ค่ารักษาอื่นๆ ก่อนปรับลด',
  `opref_aft_adj` DECIMAL(10,2) DEFAULT NULL COMMENT 'ค่ารักษาอื่นๆ หลังปรับลด',
  `total` DECIMAL(10,2) DEFAULT NULL COMMENT 'ผลรวมทั้ง Case',

  -- Responsible Parties
  `respon_cup` DECIMAL(10,2) DEFAULT NULL COMMENT 'CUP / จังหวัด (<=1600)',
  `respon_nhso` DECIMAL(10,2) DEFAULT NULL COMMENT 'สปสช (>1600)',

  -- Net Reimbursement
  `reimb_total` DECIMAL(10,2) DEFAULT NULL COMMENT 'ชดเชยสุทธิ (บาท)',
  `pay_by` VARCHAR(50) DEFAULT NULL COMMENT 'ชำระบัญชีโดย',
  `ps` VARCHAR(1) DEFAULT NULL COMMENT 'รหัสการส่งข้อมูลล่าช้า',

  -- Central Reimburse Detail - OPHC
  `cr_ophc_hc01` DECIMAL(10,2) DEFAULT NULL,
  `cr_ophc_hc02` DECIMAL(10,2) DEFAULT NULL,
  `cr_ophc_hc03` DECIMAL(10,2) DEFAULT NULL,
  `cr_ophc_hc04` DECIMAL(10,2) DEFAULT NULL,
  `cr_ophc_hc05` DECIMAL(10,2) DEFAULT NULL,
  `cr_ophc_hc06` DECIMAL(10,2) DEFAULT NULL,
  `cr_ophc_hc07` DECIMAL(10,2) DEFAULT NULL,
  `cr_ophc_hc08` DECIMAL(10,2) DEFAULT NULL,

  -- Other Funds
  `cr_ae04` DECIMAL(10,2) DEFAULT NULL,
  `cr_carae_ae08` DECIMAL(10,2) DEFAULT NULL,
  `cr_opinst_hc09` DECIMAL(10,2) DEFAULT NULL,
  `cr_dmisrc_amt` DECIMAL(10,2) DEFAULT NULL,
  `cr_dmisrc_workload` DECIMAL(10,2) DEFAULT NULL,
  `cr_rcuhosc_amt` DECIMAL(10,2) DEFAULT NULL,
  `cr_rcuhosc_workload` DECIMAL(10,2) DEFAULT NULL,
  `cr_rcuhosr_amt` DECIMAL(10,2) DEFAULT NULL,
  `cr_rcuhosr_workload` DECIMAL(10,2) DEFAULT NULL,
  `cr_llop` DECIMAL(10,2) DEFAULT NULL,
  `cr_lp` DECIMAL(10,2) DEFAULT NULL,
  `cr_stroke_drug` DECIMAL(10,2) DEFAULT NULL,
  `cr_dmidml` DECIMAL(10,2) DEFAULT NULL,
  `cr_pp` DECIMAL(10,2) DEFAULT NULL,
  `cr_dmishd` DECIMAL(10,2) DEFAULT NULL,
  `cr_paliative` DECIMAL(10,2) DEFAULT NULL,
  `cr_drug` DECIMAL(10,2) DEFAULT NULL,
  `cr_ontop` DECIMAL(10,2) DEFAULT NULL,
  `cr_total` DECIMAL(10,2) DEFAULT NULL,
  `cr_by` VARCHAR(100) DEFAULT NULL,

  -- Detailed Expenses (16 Categories x 2 = 32 columns)
  `oprefer_md01_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md01_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md02_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md02_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md03_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md03_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md04_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md04_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md05_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md05_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md06_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md06_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md07_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md07_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md08_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md08_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md09_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md09_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md10_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md10_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md11_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md11_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md12_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md12_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md13_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md13_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md14_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md14_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md15_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md15_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md16_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md16_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md17_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md17_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md18_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md18_free` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md19_claim` DECIMAL(10,2) DEFAULT NULL,
  `oprefer_md19_free` DECIMAL(10,2) DEFAULT NULL,

  -- Error & Status
  `error_code` VARCHAR(100) DEFAULT NULL,
  `deny_hc` VARCHAR(10) DEFAULT NULL,
  `deny_ae` VARCHAR(10) DEFAULT NULL,
  `deny_inst` VARCHAR(10) DEFAULT NULL,
  `deny_dmis` VARCHAR(10) DEFAULT NULL,

  -- Other
  `va` DECIMAL(10,2) DEFAULT NULL,
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

  -- NEW: HIS Reconciliation Fields
  `his_matched` BOOLEAN DEFAULT FALSE COMMENT 'Matched with HIS data',
  `his_matched_at` DATETIME NULL COMMENT 'When matched',
  `his_vn` VARCHAR(20) NULL COMMENT 'VN from HIS',
  `his_amount_diff` DECIMAL(10,2) NULL COMMENT 'Difference in amount (e-claim vs HIS)',
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
  KEY `idx_reconcile` (`his_matched`, `reconcile_status`),

  -- NEW: Unique constraint for UPSERT
  UNIQUE KEY `uq_tran_file` (`tran_id`, `file_id`)

) 


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
