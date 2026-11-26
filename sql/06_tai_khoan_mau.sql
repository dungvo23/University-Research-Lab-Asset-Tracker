-- Tạo 24 tài khoản cá nhân và 1 tài khoản quản trị riêng bằng hash scrypt đã chuẩn bị.
-- Chạy toàn bộ file một lần sau khi hoàn tất các bước 01-05.
USE university_lab_tracker;

SET @password_hash = 'scrypt:32768:8:1$x9v1CHSJGRdb8sgM$b92d5418875b11b30b3895a72b5ce0e48ceb37f763b4c3a0718d626cb09db1ef3a0a9ccce21ac38f8ac1e8b3c7744462342ca443dc29ccc009bd112af9355edc';

DELIMITER $$
CREATE PROCEDURE ch4_seed_demo_account(IN p_hash VARCHAR(255))
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_hash IS NULL
       OR NOT REGEXP_LIKE(p_hash, '^scrypt:[0-9]+:[0-9]+:[0-9]+[$][A-Za-z0-9]+[$][0-9a-f]{128}$', 'c') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Supply a Werkzeug scrypt hash in @password_hash';
    END IF;

    START TRANSACTION;
    INSERT INTO app_account (personnel_id, password_hash)
    SELECT personnel_id, p_hash FROM personnel WHERE personnel_id BETWEEN 1 AND 24;

    INSERT INTO app_account_role (personnel_id, role_code)
    SELECT personnel_id, 'MEMBER'
    FROM personnel WHERE personnel_id BETWEEN 1 AND 24;
    INSERT INTO app_operator_account(email,display_name,password_hash)
    VALUES('dh001@gmail.com','Điều hành hệ thống',p_hash);
    COMMIT;
END$$
DELIMITER ;

-- Xóa thông tin băm khỏi biến phiên sau khi dùng.
-- Nếu có lỗi, xóa procedure ch4_seed_demo_account trước khi chạy lại tệp.
CALL ch4_seed_demo_account(@password_hash);
SET @password_hash = NULL;
DROP PROCEDURE ch4_seed_demo_account;

SELECT p.personnel_id, p.email, s.student_code, r.role_code
FROM personnel AS p
JOIN app_account_role AS r USING (personnel_id)
LEFT JOIN student AS s USING (personnel_id)
WHERE p.personnel_id BETWEEN 1 AND 24
ORDER BY p.personnel_id;
