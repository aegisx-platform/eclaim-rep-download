-- Seed: Fund types for NHSO schemes
INSERT INTO fund_types (fund_code, fund_name_th, fund_name_en, fund_category, is_active) VALUES
('UCS', 'หลักประกันสุขภาพถ้วนหน้า', 'Universal Coverage Scheme', 'PUBLIC', TRUE),
('OFC', 'ข้าราชการ/รัฐวิสาหกิจ', 'Civil Servant Medical Benefit Scheme', 'PUBLIC', TRUE),
('SSS', 'ประกันสังคม', 'Social Security Scheme', 'PUBLIC', TRUE),
('LGO', 'องค์กรปกครองส่วนท้องถิ่น', 'Local Government Organization', 'PUBLIC', TRUE),
('WCF', 'กองทุนเงินทดแทน', 'Workmen Compensation Fund', 'PUBLIC', TRUE),
('PRB', 'พ.ร.บ.รถ', 'Compulsory Motor Vehicle Insurance', 'PRIVATE', TRUE),
('HC', 'High Cost', 'High Cost Items', 'FUND', TRUE),
('AE', 'Accident & Emergency', 'Accident & Emergency', 'FUND', TRUE),
('INST', 'เครื่องมือแพทย์', 'Medical Instruments', 'FUND', TRUE),
('DMIS', 'โรคเรื้อรัง', 'Disease Management', 'FUND', TRUE),
('PP', 'ส่งเสริมสุขภาพป้องกันโรค', 'Health Promotion & Prevention', 'FUND', TRUE)
ON CONFLICT (fund_code) DO UPDATE SET
    fund_name_th = EXCLUDED.fund_name_th,
    fund_name_en = EXCLUDED.fund_name_en;
