-- Chạy với tài khoản quản trị trên dữ liệu mẫu Phase 3 đã được nâng cấp.
-- Các ca thử tài khoản, MSSV và lịch dùng ROLLBACK.
-- Check-in commit bên trong procedure. Xóa bản ghi thử sau khi xác minh.
USE university_lab_tracker;

DROP PROCEDURE IF EXISTS ch4_test;
DELIMITER $$
CREATE PROCEDURE ch4_test()
BEGIN
    DECLARE v_count INT;
    DECLARE v_error INT DEFAULT 0;
    DECLARE v_log_id INT DEFAULT NULL;
    DECLARE v_other_log INT DEFAULT NULL;
    DECLARE v_booking INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        IF v_log_id IS NOT NULL THEN
            DELETE FROM lab_access_log WHERE access_id = v_log_id;
        END IF;
        IF v_other_log IS NOT NULL THEN
            DELETE FROM lab_access_log WHERE access_id = v_other_log;
        END IF;
        RESIGNAL;
    END;

    IF EXISTS (
        SELECT 1 FROM lab_access_log
        WHERE personnel_id IN (6, 7) AND exit_time IS NULL
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Use fresh demo data or close demo sessions before testing';
    END IF;

    START TRANSACTION;
    -- Fixture chỉ dùng kiểm tra truy vấn MySQL, được rollback cuối ca.
    INSERT INTO app_account (personnel_id, password_hash)
    VALUES (1, 'database-test-fixture')
    ON DUPLICATE KEY UPDATE is_active = TRUE;

    SELECT COUNT(*) INTO v_count
    FROM v_app_identity
    WHERE personnel_id = 1 AND is_active = TRUE
      AND student_code IS NULL
      AND EXISTS(SELECT 1 FROM faculty WHERE personnel_id=1 AND faculty_code='GV009')
      AND email = 'gv009@gmail.com';
    IF v_count <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-01 identity lookup failed';
    END IF;
    SELECT 'CH4-01' AS test_id, 'PASS' AS result, 'Faculty email matches person 1 without a student subtype' AS test_case;

    BEGIN
        DECLARE CONTINUE HANDLER FOR 1062 SET v_error = 1062;
        UPDATE student SET student_code = 'sv002' WHERE personnel_id = 6;
    END;
    IF v_error <> 1062 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-02 case-insensitive uniqueness failed';
    END IF;
    SELECT 'CH4-02' AS test_id, 'PASS' AS result, 'Case-only duplicate MSSV is rejected' AS test_case;

    SET v_error = 0;
    BEGIN
        DECLARE CONTINUE HANDLER FOR 3819 SET v_error = 3819;
        UPDATE student SET student_code = 'SV-006' WHERE personnel_id = 6;
    END;
    IF v_error <> 3819 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-03 MSSV character check failed';
    END IF;
    UPDATE student SET student_code = '00A6' WHERE personnel_id = 6;
    SELECT COUNT(*) INTO v_count FROM student
    WHERE personnel_id = 6 AND student_code = '00a6';
    IF v_count <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-03 leading zero or mixed-case lookup failed';
    END IF;
    SELECT 'CH4-03' AS test_id, 'PASS' AS result, 'Alphanumeric IDs preserve leading zeros and reject punctuation' AS test_case;
    ROLLBACK;

    START TRANSACTION;
    INSERT INTO equipment_booking (asset_id, personnel_id, start_time, end_time, purpose)
    VALUES (1, 6, '2099-01-01 09:00:00', '2099-01-01 10:00:00', 'CH4-04'),
           (1, 6, '2099-01-01 10:00:00', '2099-01-01 11:00:00', 'CH4-04');
    SET v_booking = LAST_INSERT_ID();
    SET v_error = 0;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLSTATE '45000' SET v_error = 1644;
        UPDATE equipment_booking
        SET end_time = '2099-01-01 10:30:00'
        WHERE booking_id = v_booking;
    END;
    IF v_error <> 1644 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-04 overlap accepted or missing booking';
    END IF;
    ROLLBACK;
    SELECT 'CH4-04' AS test_id, 'PASS' AS result, 'Adjacent INSERT accepted and overlapping UPDATE rejected' AS test_case;

    CALL sp_app_checkin(6, 5, 'CH4-05', v_log_id);
    SET v_error = 0;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLSTATE '45000' SET v_error = 1644;
        CALL sp_app_checkin(6, 5, 'CH4-05 duplicate', v_other_log);
    END;
    IF v_error <> 1644 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-05 second check-in accepted';
    END IF;
    SELECT 'CH4-05' AS test_id, 'PASS' AS result, 'Second check-in rejected while first is open' AS test_case;

    SET v_error = 0;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLSTATE '45000' SET v_error = 1644;
        CALL sp_app_checkout(7, v_log_id);
    END;
    IF v_error <> 1644 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-06 checkout by wrong person accepted';
    END IF;

    CALL sp_app_checkout(6, v_log_id);
    SELECT COUNT(*) INTO v_count
    FROM lab_access_log
    WHERE access_id = v_log_id AND exit_time >= entry_time;
    IF v_count <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-06 checkout time was not saved';
    END IF;
    DELETE FROM lab_access_log WHERE access_id = v_log_id;
    SET v_log_id = NULL;
    SELECT 'CH4-06' AS test_id, 'PASS' AS result, 'Only the owner can close the visit' AS test_case;

    SET v_error = 0;
    BEGIN
        DECLARE CONTINUE HANDLER FOR SQLSTATE '45000' SET v_error = 1644;
        CALL sp_app_checkin(7, 5, 'CH4-07', v_other_log);
    END;
    IF v_error <> 1644 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'CH4-07 expired certificate accepted';
    END IF;
    SELECT 'CH4-07' AS test_id, 'PASS' AS result, 'Expired certificate rejected for room 5' AS test_case;
END$$
DELIMITER ;

CALL ch4_test();
DROP PROCEDURE ch4_test;
