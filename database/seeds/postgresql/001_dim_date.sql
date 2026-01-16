-- Seed: Populate dim_date table with 7 years of dates
-- From 5 years back to 2 years forward

INSERT INTO dim_date (date_id, full_date, day_of_week, day_name, day_of_month, day_of_year,
                      week_of_year, month_number, month_name, month_name_th, quarter, year,
                      fiscal_year, fiscal_quarter, is_weekend)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INTEGER as date_id,
    d as full_date,
    EXTRACT(DOW FROM d)::INTEGER as day_of_week,
    TO_CHAR(d, 'Day') as day_name,
    EXTRACT(DAY FROM d)::INTEGER as day_of_month,
    EXTRACT(DOY FROM d)::INTEGER as day_of_year,
    EXTRACT(WEEK FROM d)::INTEGER as week_of_year,
    EXTRACT(MONTH FROM d)::INTEGER as month_number,
    TO_CHAR(d, 'Month') as month_name,
    CASE EXTRACT(MONTH FROM d)
        WHEN 1 THEN 'มกราคม' WHEN 2 THEN 'กุมภาพันธ์' WHEN 3 THEN 'มีนาคม'
        WHEN 4 THEN 'เมษายน' WHEN 5 THEN 'พฤษภาคม' WHEN 6 THEN 'มิถุนายน'
        WHEN 7 THEN 'กรกฎาคม' WHEN 8 THEN 'สิงหาคม' WHEN 9 THEN 'กันยายน'
        WHEN 10 THEN 'ตุลาคม' WHEN 11 THEN 'พฤศจิกายน' WHEN 12 THEN 'ธันวาคม'
    END as month_name_th,
    EXTRACT(QUARTER FROM d)::INTEGER as quarter,
    EXTRACT(YEAR FROM d)::INTEGER as year,
    CASE WHEN EXTRACT(MONTH FROM d) >= 10 THEN EXTRACT(YEAR FROM d)::INTEGER + 1
         ELSE EXTRACT(YEAR FROM d)::INTEGER
    END as fiscal_year,
    CASE
        WHEN EXTRACT(MONTH FROM d) IN (10,11,12) THEN 1
        WHEN EXTRACT(MONTH FROM d) IN (1,2,3) THEN 2
        WHEN EXTRACT(MONTH FROM d) IN (4,5,6) THEN 3
        ELSE 4
    END as fiscal_quarter,
    EXTRACT(DOW FROM d) IN (0, 6) as is_weekend
FROM generate_series(
    CURRENT_DATE - INTERVAL '5 years',
    CURRENT_DATE + INTERVAL '2 years',
    INTERVAL '1 day'
) AS d
ON CONFLICT (date_id) DO NOTHING;
