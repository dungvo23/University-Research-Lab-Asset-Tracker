USE university_lab_tracker;
-- Giá trị hiện hữu phải là mã ASCII gồm chữ hoặc số, tối đa 20 ký tự.
-- UNIQUE hiện hữu áp dụng collation không phân biệt hoa/thường sau migration.
ALTER TABLE student
    MODIFY student_code VARCHAR(20) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
    ADD CONSTRAINT ck_student_code_format
        CHECK (CHAR_LENGTH(student_code) BETWEEN 1 AND 20
            AND NOT REGEXP_LIKE(student_code, '[^A-Za-z0-9]', 'c'));

CREATE TABLE app_operator_account (
 operator_id INT PRIMARY KEY AUTO_INCREMENT,
 email VARCHAR(160) NOT NULL UNIQUE,
 display_name VARCHAR(120) NOT NULL,
 password_hash VARCHAR(255) NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE CHECK(is_active IN (0,1))
) ENGINE=InnoDB;

CREATE TABLE app_account (
    personnel_id INT PRIMARY KEY,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_active IN (0,1)),
    FOREIGN KEY (personnel_id) REFERENCES personnel(personnel_id)
) ENGINE=InnoDB;

CREATE TABLE app_account_role (
    personnel_id INT NOT NULL,
    role_code ENUM('MEMBER','OPERATOR') NOT NULL,
    PRIMARY KEY (personnel_id, role_code),
    FOREIGN KEY (personnel_id) REFERENCES app_account(personnel_id)
) ENGINE=InnoDB;

CREATE VIEW v_app_identity AS
SELECT a.personnel_id, p.full_name, p.email, s.student_code, a.password_hash, a.is_active
FROM app_account a JOIN personnel p USING (personnel_id)
LEFT JOIN student s USING (personnel_id);

DELIMITER $$
CREATE PROCEDURE sp_app_checkin(IN person INT, IN room INT, IN reason VARCHAR(255), OUT log_id INT)
BEGIN
    DECLARE locked_person INT;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    SELECT personnel_id INTO locked_person FROM personnel WHERE personnel_id=person FOR UPDATE;
    IF EXISTS (SELECT 1 FROM lab_access_log WHERE personnel_id=person AND exit_time IS NULL)
    THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ACCESS_OPEN'; END IF;
    CALL sp_log_lab_access(person, room, reason, log_id);
    COMMIT;
END$$
CREATE PROCEDURE sp_app_checkout(IN person INT, IN log_id INT)
BEGIN
    UPDATE lab_access_log SET exit_time=CURRENT_TIMESTAMP
    WHERE access_id=log_id AND personnel_id=person AND exit_time IS NULL;
    IF ROW_COUNT() <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ACCESS_NOT_OPEN';
    END IF;
END$$
DELIMITER ;

-- Dang ky cho duyet: chi tao tai khoan MEMBER sau khi dieu hanh phe duyet.
CREATE TABLE app_registration_request (
    request_id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    phone VARCHAR(20) NULL,
    person_type ENUM('STUDENT','FACULTY','LAB_TECHNICIAN','COLLABORATOR') NOT NULL,
    identity_code VARCHAR(20) CHARACTER SET ascii COLLATE ascii_general_ci NULL,
    home_institution VARCHAR(150) NULL,
    password_hash VARCHAR(255) NOT NULL,
    status ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME NULL,
    reviewed_by INT NULL,
    review_note VARCHAR(500) NULL,
    reviewed_operator_id INT NULL,
    FOREIGN KEY (reviewed_operator_id) REFERENCES app_operator_account(operator_id),
    FOREIGN KEY (reviewed_by) REFERENCES personnel(personnel_id),
    INDEX idx_registration_status(status,created_at)
) ENGINE=InnoDB;

DELIMITER $$
CREATE PROCEDURE sp_review_registration(
 IN p_request INT, IN p_operator INT, IN p_approve BOOLEAN, IN p_note VARCHAR(500)
)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_operator INT DEFAULT NULL;
 DECLARE v_request INT DEFAULT NULL;
 DECLARE v_person INT DEFAULT NULL;
 DECLARE v_name VARCHAR(120);
 DECLARE v_email VARCHAR(160);
 DECLARE v_phone VARCHAR(20);
 DECLARE v_type VARCHAR(30);
 DECLARE v_code VARCHAR(20);
 DECLARE v_school VARCHAR(150);
 DECLARE v_hash VARCHAR(255);
 DECLARE v_status VARCHAR(20);
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 SELECT operator_id INTO v_operator FROM app_operator_account
 WHERE operator_id=p_operator AND is_active=TRUE FOR SHARE;
 IF v_operator IS NULL THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_OPERATOR_REQUIRED';
 END IF;
 SELECT request_id,full_name,email,phone,person_type,identity_code,password_hash,status,home_institution
 INTO v_request,v_name,v_email,v_phone,v_type,v_code,v_hash,v_status,v_school
 FROM app_registration_request WHERE request_id=p_request FOR UPDATE;
 IF v_request IS NULL OR v_status<>'PENDING' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_NOT_PENDING';
 END IF;
 IF p_approve IS NULL OR p_approve NOT IN (0,1) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_INVALID_DECISION';
 END IF;
 IF p_approve=TRUE THEN
  SELECT personnel_id INTO v_person FROM personnel WHERE email=v_email FOR UPDATE;
  IF v_person IS NOT NULL THEN
   IF EXISTS(SELECT 1 FROM app_account WHERE personnel_id=v_person) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_ACCOUNT_EXISTS';
   END IF;
   IF NOT ((v_type='STUDENT' AND EXISTS(SELECT 1 FROM student WHERE personnel_id=v_person AND student_code=v_code))
        OR (v_type='FACULTY' AND EXISTS(SELECT 1 FROM faculty WHERE personnel_id=v_person AND faculty_code=v_code))
        OR (v_type='LAB_TECHNICIAN' AND EXISTS(SELECT 1 FROM lab_technician WHERE personnel_id=v_person AND staff_code=v_code))
        OR (v_type='COLLABORATOR' AND EXISTS(SELECT 1 FROM collaborator WHERE personnel_id=v_person))) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_IDENTITY_MISMATCH';
   END IF;
  ELSE
   INSERT INTO personnel(full_name,email,phone) VALUES(v_name,v_email,v_phone);
   SET v_person=LAST_INSERT_ID();
   IF v_type='STUDENT' THEN
    INSERT INTO student(personnel_id,student_code) VALUES(v_person,v_code);
   ELSEIF v_type='FACULTY' THEN
    INSERT INTO faculty(personnel_id,faculty_code) VALUES(v_person,v_code);
   ELSEIF v_type='LAB_TECHNICIAN' THEN
    INSERT INTO lab_technician(personnel_id,staff_code) VALUES(v_person,v_code);
   ELSEIF v_type='COLLABORATOR' THEN
    INSERT INTO collaborator(personnel_id,home_institution) VALUES(v_person,v_school);
   ELSE
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_IDENTITY_MISMATCH';
   END IF;
  END IF;
  INSERT INTO app_account(personnel_id,password_hash,is_active) VALUES(v_person,v_hash,TRUE);
  INSERT INTO app_account_role(personnel_id,role_code) VALUES(v_person,'MEMBER');
 END IF;
 UPDATE app_registration_request
 SET status=IF(p_approve,'APPROVED','REJECTED'),reviewed_at=CURRENT_TIMESTAMP,
     reviewed_operator_id=p_operator,review_note=p_note WHERE request_id=p_request;
 COMMIT;
END$$
DELIMITER ;

-- Quick chemical receipt: new lot, original lot unchanged.
CREATE TABLE chemical_receipt (
 asset_id INT PRIMARY KEY,
 received_on DATE NOT NULL,
 received_qty DECIMAL(12,3) NOT NULL CHECK(received_qty>0),
 received_by INT NULL,
 received_operator_id INT NULL,
 FOREIGN KEY(received_operator_id) REFERENCES app_operator_account(operator_id),
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(asset_id) REFERENCES chemical_material(asset_id),
 FOREIGN KEY(received_by) REFERENCES personnel(personnel_id)
) ENGINE=InnoDB;
DELIMITER $$
CREATE PROCEDURE sp_receive_chemical(IN p_source INT,IN p_unit VARCHAR(20),IN p_qty DECIMAL(12,3),IN p_expiry DATE,IN p_received DATE,IN p_operator INT,OUT p_id INT)
SQL SECURITY DEFINER
BEGIN
 DECLARE v_name VARCHAR(150); DECLARE v_room INT; DECLARE v_hazard TINYINT; DECLARE v_concentration VARCHAR(40);
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM app_operator_account WHERE operator_id=p_operator AND is_active=TRUE) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_OPERATOR_REQUIRED';
 END IF;
 IF p_qty IS NULL OR p_qty<=0 OR p_unit IS NULL OR CHAR_LENGTH(TRIM(p_unit))=0 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid receipt quantity or unit';
 END IF;
 IF p_expiry IS NULL OR p_received IS NULL OR p_expiry<CURRENT_DATE() OR p_received>CURRENT_DATE() OR p_received>p_expiry THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid receipt or expiry date';
 END IF;
 SELECT a.asset_name,a.room_id,c.hazard_level,c.concentration INTO v_name,v_room,v_hazard,v_concentration
 FROM chemical_material c JOIN lab_asset a USING(asset_id) WHERE c.asset_id=p_source FOR SHARE;
 IF v_name IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Invalid chemical asset_id'; END IF;
 INSERT INTO lab_asset(asset_name,asset_type,status,room_id) VALUES(v_name,'CHEMICAL','AVAILABLE',v_room);
 SET p_id=LAST_INSERT_ID();
 INSERT INTO chemical_material(asset_id,hazard_level,unit,stock_qty,concentration,expiry_date)
 VALUES(p_id,v_hazard,TRIM(p_unit),p_qty,v_concentration,p_expiry);
 INSERT INTO chemical_receipt(asset_id,received_on,received_qty,received_operator_id) VALUES(p_id,p_received,p_qty,p_operator);
 COMMIT;
END$$
DELIMITER ;

-- Booking approval audit. Pending requests reserve the time slot.
ALTER TABLE equipment_booking
 ADD COLUMN reviewed_by_operator INT NULL,
 ADD COLUMN reviewed_at DATETIME NULL,
 ADD COLUMN review_note VARCHAR(500) NULL,
 ADD FOREIGN KEY(reviewed_by_operator) REFERENCES app_operator_account(operator_id);
DELIMITER $$
CREATE PROCEDURE sp_review_booking(IN p_booking INT,IN p_operator INT,IN p_approve BOOLEAN,IN p_note VARCHAR(500))
SQL SECURITY DEFINER
BEGIN
 DECLARE v_asset INT DEFAULT NULL; DECLARE v_locked INT DEFAULT NULL;
 DECLARE v_status VARCHAR(20); DECLARE v_start DATETIME;
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM app_operator_account WHERE operator_id=p_operator AND is_active=TRUE) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_OPERATOR_REQUIRED';
 END IF;
 IF p_approve IS NULL OR p_approve NOT IN(0,1) OR (p_approve=0 AND (p_note IS NULL OR CHAR_LENGTH(TRIM(p_note))=0)) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BOOKING_INVALID_DECISION';
 END IF;
 SELECT asset_id INTO v_asset FROM equipment_booking WHERE booking_id=p_booking;
 SELECT asset_id INTO v_locked FROM equipment WHERE asset_id=v_asset FOR UPDATE;
 SELECT booking_status,start_time INTO v_status,v_start FROM equipment_booking WHERE booking_id=p_booking FOR UPDATE;
 IF v_status IS NULL OR v_status<>'PENDING' THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BOOKING_NOT_PENDING';
 END IF;
 IF p_approve=1 AND v_start<=CURRENT_TIMESTAMP THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BOOKING_ALREADY_STARTED';
 END IF;
 UPDATE equipment_booking SET booking_status=IF(p_approve=1,'APPROVED','REJECTED'),
 reviewed_by_operator=p_operator,reviewed_at=CURRENT_TIMESTAMP,review_note=p_note WHERE booking_id=p_booking;
 COMMIT;
END$$
DELIMITER ;

-- Safety certificate changes take effect only after independent ADMIN review.
CREATE TABLE certificate_update_request (
 request_id INT PRIMARY KEY AUTO_INCREMENT,
 personnel_id INT NOT NULL,cert_id INT NOT NULL,
 issue_date DATE NOT NULL,expiry_date DATE NOT NULL,
 previous_issue DATE NULL,previous_expiry DATE NULL,
 proof_file VARCHAR(80) NULL,
 status ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 reviewed_at DATETIME NULL,reviewed_operator_id INT NULL,review_note VARCHAR(500) NULL,
 pending_guard TINYINT GENERATED ALWAYS AS (IF(status='PENDING',1,NULL)) STORED,
 UNIQUE(personnel_id,cert_id,pending_guard),
 FOREIGN KEY(personnel_id) REFERENCES personnel(personnel_id),
 FOREIGN KEY(cert_id) REFERENCES safety_certificate(cert_id),
 FOREIGN KEY(reviewed_operator_id) REFERENCES app_operator_account(operator_id),
 CHECK(expiry_date>issue_date)
) ENGINE=InnoDB;
DELIMITER $$
CREATE PROCEDURE sp_review_certificate(IN p_request INT,IN p_operator INT,IN p_approve BOOLEAN,IN p_note VARCHAR(500))
SQL SECURITY DEFINER
BEGIN
 DECLARE v_person INT DEFAULT NULL;DECLARE v_cert INT;DECLARE v_locked INT;
 DECLARE v_issue DATE;DECLARE v_expiry DATE;DECLARE v_old_issue DATE;DECLARE v_old_expiry DATE;
 DECLARE v_current_issue DATE DEFAULT NULL;DECLARE v_current_expiry DATE DEFAULT NULL;DECLARE v_status VARCHAR(20);
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK;RESIGNAL;END;
 START TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM app_operator_account WHERE operator_id=p_operator AND is_active=TRUE) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_OPERATOR_REQUIRED';END IF;
 SELECT personnel_id,cert_id,issue_date,expiry_date,previous_issue,previous_expiry,status
 INTO v_person,v_cert,v_issue,v_expiry,v_old_issue,v_old_expiry,v_status
 FROM certificate_update_request WHERE request_id=p_request FOR UPDATE;
 IF v_person IS NULL OR v_status<>'PENDING' THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='REQUEST_NOT_PENDING';END IF;
 IF p_approve IS NULL OR p_approve NOT IN(0,1) OR (p_approve=0 AND (p_note IS NULL OR CHAR_LENGTH(TRIM(p_note))=0)) THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='CERT_INVALID_DECISION';END IF;
 IF p_approve=1 THEN
  IF v_issue>CURRENT_DATE() OR v_expiry<CURRENT_DATE() THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='CERT_INVALID_DATES';END IF;
  SELECT personnel_id INTO v_locked FROM personnel WHERE personnel_id=v_person FOR UPDATE;
  SELECT issue_date,expiry_date INTO v_current_issue,v_current_expiry FROM personnel_certificate WHERE personnel_id=v_person AND cert_id=v_cert FOR UPDATE;
  IF NOT(v_current_issue <=> v_old_issue) OR NOT(v_current_expiry <=> v_old_expiry) THEN
   SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='CERT_STALE_REQUEST';END IF;
  INSERT INTO personnel_certificate(personnel_id,cert_id,issue_date,expiry_date) VALUES(v_person,v_cert,v_issue,v_expiry)
  ON DUPLICATE KEY UPDATE issue_date=v_issue,expiry_date=v_expiry;
 END IF;
 UPDATE certificate_update_request SET status=IF(p_approve=1,'APPROVED','REJECTED'),reviewed_at=CURRENT_TIMESTAMP,
 reviewed_operator_id=p_operator,review_note=p_note WHERE request_id=p_request;
 COMMIT;
END$$
DELIMITER ;

-- Read receipts for reviewed results; pending admin counts are derived live.
CREATE TABLE notification_seen (
 personnel_id INT NOT NULL,
 notification_kind ENUM('BOOKING','CERTIFICATE','REGISTRATION') NOT NULL,
 item_id INT NOT NULL,
 seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(personnel_id,notification_kind,item_id),
 FOREIGN KEY(personnel_id) REFERENCES personnel(personnel_id)
) ENGINE=InnoDB;
