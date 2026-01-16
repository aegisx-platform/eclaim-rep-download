-- Seed: Populate dim_date table with dates
-- MySQL version using stored procedure for date generation

DELIMITER //

DROP PROCEDURE IF EXISTS populate_dim_date//

CREATE PROCEDURE populate_dim_date()
BEGIN
    DECLARE v_date DATE;
    DECLARE v_end_date DATE;

    SET v_date = DATE_SUB(CURDATE(), INTERVAL 5 YEAR);
    SET v_end_date = DATE_ADD(CURDATE(), INTERVAL 2 YEAR);

    WHILE v_date <= v_end_date DO
        INSERT IGNORE INTO dim_date (
            date_id, full_date, day_of_week, day_name, day_of_month, day_of_year,
            week_of_year, month_number, month_name, month_name_th, quarter, year,
            fiscal_year, fiscal_quarter, is_weekend
        ) VALUES (
            DATE_FORMAT(v_date, '%Y%m%d'),
            v_date,
            DAYOFWEEK(v_date) - 1,
            DAYNAME(v_date),
            DAY(v_date),
            DAYOFYEAR(v_date),
            WEEK(v_date),
            MONTH(v_date),
            MONTHNAME(v_date),
            CASE MONTH(v_date)
                WHEN 1 THEN 'มกราคม' WHEN 2 THEN 'กุมภาพันธ์' WHEN 3 THEN 'มีนาคม'
                WHEN 4 THEN 'เมษายน' WHEN 5 THEN 'พฤษภาคม' WHEN 6 THEN 'มิถุนายน'
                WHEN 7 THEN 'กรกฎาคม' WHEN 8 THEN 'สิงหาคม' WHEN 9 THEN 'กันยายน'
                WHEN 10 THEN 'ตุลาคม' WHEN 11 THEN 'พฤศจิกายน' WHEN 12 THEN 'ธันวาคม'
            END,
            QUARTER(v_date),
            YEAR(v_date),
            CASE WHEN MONTH(v_date) >= 10 THEN YEAR(v_date) + 1 ELSE YEAR(v_date) END,
            CASE
                WHEN MONTH(v_date) IN (10,11,12) THEN 1
                WHEN MONTH(v_date) IN (1,2,3) THEN 2
                WHEN MONTH(v_date) IN (4,5,6) THEN 3
                ELSE 4
            END,
            DAYOFWEEK(v_date) IN (1, 7)
        );

        SET v_date = DATE_ADD(v_date, INTERVAL 1 DAY);
    END WHILE;
END//

DELIMITER ;

CALL populate_dim_date();
DROP PROCEDURE IF EXISTS populate_dim_date;
