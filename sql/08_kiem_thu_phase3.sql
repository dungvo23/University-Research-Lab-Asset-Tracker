-- INT1313 | Phase 3 - 05: Kiem thu BR va tinh toan ven du lieu.
-- Ket qua PASS/FAIL chi co gia tri sau khi thuc thi tren MySQL 8.0.
-- Script nay khong ghi du lieu kiem thu vao bo du lieu nen (ROLLBACK sau tung ca).
USE university_lab_tracker;

DROP PROCEDURE IF EXISTS sp_run_phase3_tests;
DELIMITER $$
CREATE PROCEDURE sp_run_phase3_tests()
BEGIN
    DECLARE v_error INT DEFAULT 0;
    DECLARE v_error_2 INT DEFAULT 0;
    DECLARE v_before DECIMAL(12,3) DEFAULT 0;
    DECLARE v_after DECIMAL(12,3) DEFAULT 0;
    DECLARE v_count INT DEFAULT 0;
    DECLARE v_view_count INT DEFAULT 0;

    DROP TEMPORARY TABLE IF EXISTS phase3_test_results;
    CREATE TEMPORARY TABLE phase3_test_results (
        test_code VARCHAR(10) NOT NULL,
        result VARCHAR(12) NOT NULL,
        description VARCHAR(255) NOT NULL
    ) ENGINE = MEMORY;

    -- T01. Khoá ngoại không tồn tại phải bị từ chối.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO lab_asset (asset_name, asset_type, room_id)
        VALUES ('T01 invalid room', 'EQUIPMENT', 99999);
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T01', IF(v_error = 1, 'PASS', 'FAIL'), 'Foreign key khong ton tai bi tu choi');

    -- T02. Xuat hoa chat hop le; trong transaction kho giam 2 don vi.
    SELECT stock_qty INTO v_before FROM chemical_material WHERE asset_id = 20;
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO chemical_dispense_log
            (asset_id, personnel_id, project_id, quantity, purpose)
        VALUES (20, 1, 1, 2.000, 'T02 valid dispense');
    END;
    SELECT stock_qty INTO v_after FROM chemical_material WHERE asset_id = 20;
    SELECT COUNT(*) INTO v_count FROM chemical_dispense_log WHERE purpose = 'T02 valid dispense';
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T02', IF(v_error = 0 AND v_before - v_after = 2 AND v_count = 1,
                   'PASS', 'FAIL'), 'Cap phat hop le: kho tru 2 va ghi nhat ky');

    -- T03. Thieu chung chi phu hop voi hoa chat cap 5.
    SELECT stock_qty INTO v_before FROM chemical_material WHERE asset_id = 20;
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO chemical_dispense_log
            (asset_id, personnel_id, project_id, quantity, purpose)
        VALUES (20, 24, 1, 1.000, 'T03 missing certificate');
    END;
    SELECT stock_qty INTO v_after FROM chemical_material WHERE asset_id = 20;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T03', IF(v_error = 1 AND v_before = v_after, 'PASS', 'FAIL'),
         'Khong du chung chi, ton kho khong doi');

    -- T04. Chung chi cua nguoi 7 da het han.
    SELECT stock_qty INTO v_before FROM chemical_material WHERE asset_id = 20;
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO chemical_dispense_log
            (asset_id, personnel_id, project_id, quantity, purpose)
        VALUES (20, 7, 1, 1.000, 'T04 expired certificate');
    END;
    SELECT stock_qty INTO v_after FROM chemical_material WHERE asset_id = 20;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T04', IF(v_error = 1 AND v_before = v_after, 'PASS', 'FAIL'),
         'Chung chi het han bi tu choi');

    -- T05a. Hoa chat 22 da het han du nguy hiem cap 1.
    SELECT stock_qty INTO v_before FROM chemical_material WHERE asset_id = 22;
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO chemical_dispense_log
            (asset_id, personnel_id, project_id, quantity, purpose)
        VALUES (22, 1, 1, 1.000, 'T05 expired chemical');
    END;
    SELECT stock_qty INTO v_after FROM chemical_material WHERE asset_id = 22;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T05a', IF(v_error = 1 AND v_before = v_after, 'PASS', 'FAIL'),
         'Hoa chat het han bi tu choi');

    -- T05b. So luong xuat vuot xa 100 don vi kho.
    SELECT stock_qty INTO v_before FROM chemical_material WHERE asset_id = 20;
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO chemical_dispense_log
            (asset_id, personnel_id, project_id, quantity, purpose)
        VALUES (20, 1, 1, 1000.000, 'T05 overstock');
    END;
    SELECT stock_qty INTO v_after FROM chemical_material WHERE asset_id = 20;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T05b', IF(v_error = 1 AND v_before = v_after, 'PASS', 'FAIL'),
         'Xuat vuot ton kho bi tu choi');

    -- T06. Lich moi khong trung voi lich 2026-12-01 cua thiet bi 1.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO equipment_booking
            (asset_id, personnel_id, project_id, start_time, end_time, purpose)
        VALUES (1, 1, 1, '2026-12-20 08:00:00', '2026-12-20 10:00:00',
                'T06 valid booking');
    END;
    SELECT COUNT(*) INTO v_count FROM equipment_booking WHERE purpose = 'T06 valid booking';
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T06', IF(v_error = 0 AND v_count = 1, 'PASS', 'FAIL'),
         'Dat lich khong chong lan thanh cong');

    -- T07. Lich 09-11 trung lich 08-10 cua thiet bi 1.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO equipment_booking
            (asset_id, personnel_id, project_id, start_time, end_time, purpose)
        VALUES (1, 1, 1, '2026-12-01 09:00:00', '2026-12-01 11:00:00',
                'T07 overlap');
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T07', IF(v_error = 1, 'PASS', 'FAIL'), 'Lich chong lan bi tu choi');

    -- T08. Khoang thoi gian khong hop le.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO equipment_booking
            (asset_id, personnel_id, project_id, start_time, end_time, purpose)
        VALUES (2, 1, 1, '2026-12-20 11:00:00', '2026-12-20 10:00:00',
                'T08 bad interval');
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T08', IF(v_error = 1, 'PASS', 'FAIL'), 'end_time <= start_time bi tu choi');

    -- T09. Mot phien ket noi khong chung minh duoc race condition.
    INSERT INTO phase3_test_results VALUES
        ('T09', 'MANUAL', 'Can hai ket noi dong thoi; xem README.md');

    -- T10. Kiem tra View ton tai; 12 SELECT chay rieng tu 07_truy_van.sql.
    SELECT COUNT(*) INTO v_view_count
    FROM information_schema.views
    WHERE table_schema = DATABASE()
      AND table_name IN ('v_chemical_expiring_soon', 'v_project_asset_allocation');
    INSERT INTO phase3_test_results VALUES
        ('T10', IF(v_view_count = 2, 'MANUAL', 'FAIL'),
         'Da kiem tra View; can chay rieng 12 cau Q01-Q12');

    -- T11. Kiem tra du lieu hien tai va tu choi doi phong kem an toan.
    SELECT COUNT(*) INTO v_count
    FROM chemical_material AS c
    JOIN lab_asset AS a ON a.asset_id = c.asset_id
    JOIN lab_room AS r ON r.room_id = a.room_id
    WHERE c.hazard_level > r.safety_category;
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        UPDATE lab_asset SET room_id = 1 WHERE asset_id = 20;
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T11', IF(v_count = 0 AND v_error = 1, 'PASS', 'FAIL'),
         'Khong co hoa chat sai phong; doi phong khong an toan bi chan');

    -- T12. FK loi sau khi Trigger da cap nhat kho: statement phai rollback tat ca.
    SELECT stock_qty INTO v_before FROM chemical_material WHERE asset_id = 20;
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO chemical_dispense_log
            (asset_id, personnel_id, project_id, quantity, purpose)
        VALUES (20, 1, 99999, 3.000, 'T12 statement atomicity');
    END;
    SELECT stock_qty INTO v_after FROM chemical_material WHERE asset_id = 20;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T12', IF(v_error = 1 AND v_before = v_after, 'PASS', 'FAIL'),
         'Ghi log that bai khong lam thay doi ton kho');

    -- T13. Khong co chung chi khong duoc truy cap phong chua hoa chat cap 5.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO lab_access_log
            (personnel_id, room_id, entry_time, exit_time, purpose)
        VALUES (24, 5, CURRENT_TIMESTAMP, NULL, 'T13 unsafe access');
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T13', IF(v_error = 1, 'PASS', 'FAIL'),
         'Tu choi nguoi thieu chung chi vao phong co hoa chat nguy hiem');

    -- T14. Mã nhân sự không thuộc FACULTY không thể thành PI.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        UPDATE research_project SET pi_personnel_id = 15 WHERE project_id = 1;
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T14', IF(v_error = 1, 'PASS', 'FAIL'),
         'Principal Investigator phai la giang vien');

    -- T15. Mot chemical khong the chen nhu equipment.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        INSERT INTO equipment (asset_id, serial_number) VALUES (20, 'T15-WRONG');
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T15', IF(v_error = 1, 'PASS', 'FAIL'),
         'Tu choi tao subtype thiet bi cho chemical');

    -- T16. Nhan su 21 chi thuoc LAB_TECHNICIAN, xoa role se vi pham Total.
    SET v_error = 0;
    START TRANSACTION;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET v_error = 1;
        DELETE FROM lab_technician WHERE personnel_id = 21;
    END;
    ROLLBACK;
    INSERT INTO phase3_test_results VALUES
        ('T16', IF(v_error = 1, 'PASS', 'FAIL'),
         'Tu choi xoa vai tro cuoi cua personnel');

    SELECT test_code, result, description
    FROM phase3_test_results
    ORDER BY FIELD(test_code,
        'T01','T02','T03','T04','T05a','T05b','T06','T07','T08','T09',
        'T10','T11','T12','T13','T14','T15','T16');

    SELECT result, COUNT(*) AS case_count
    FROM phase3_test_results GROUP BY result ORDER BY result;
END$$
DELIMITER ;

CALL sp_run_phase3_tests();
-- T09 va T10 duoc gan MANUAL cho den khi co bien ban chay thuc te.
