-- Seed: Service types
INSERT INTO service_types (service_code, service_name_th, service_name_en, service_category, is_active) VALUES
('OP', 'ผู้ป่วยนอก', 'Outpatient', 'PATIENT_TYPE', TRUE),
('IP', 'ผู้ป่วยใน', 'Inpatient', 'PATIENT_TYPE', TRUE),
('ER', 'ฉุกเฉิน', 'Emergency', 'SERVICE', TRUE),
('REFER', 'ส่งต่อ', 'Referral', 'SERVICE', TRUE),
('REHAB', 'ฟื้นฟูสมรรถภาพ', 'Rehabilitation', 'SERVICE', TRUE),
('MENTAL', 'จิตเวช', 'Mental Health', 'SERVICE', TRUE),
('DENTAL', 'ทันตกรรม', 'Dental', 'SERVICE', TRUE),
('ANC', 'ฝากครรภ์', 'Antenatal Care', 'SERVICE', TRUE),
('VACCINE', 'วัคซีน', 'Vaccination', 'SERVICE', TRUE),
('DIALYSIS', 'ล้างไต', 'Dialysis', 'SERVICE', TRUE)
ON DUPLICATE KEY UPDATE
    service_name_th = VALUES(service_name_th),
    service_name_en = VALUES(service_name_en);
