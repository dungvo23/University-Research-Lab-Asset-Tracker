-- INT1313 | University Research & Lab Asset Tracker
-- Phase 3 - 04: Trigger, View, thu tuc giao dich va kiem soat nghiep vu.
-- PHẢI chay SAU 01_tao_bang.sql va TRUOC 03_du_lieu_mau.sql.
USE university_lab_tracker;

DROP VIEW IF EXISTS v_project_asset_allocation;
DROP VIEW IF EXISTS v_chemical_expiring_soon;
DROP PROCEDURE IF EXISTS sp_audit_invariants;
DROP PROCEDURE IF EXISTS sp_log_lab_access;
DROP PROCEDURE IF EXISTS sp_book_equipment;
DROP PROCEDURE IF EXISTS sp_dispense_chemical;
DROP PROCEDURE IF EXISTS sp_create_chemical;
DROP PROCEDURE IF EXISTS sp_create_equipment;
DROP PROCEDURE IF EXISTS sp_create_personnel;

DROP TRIGGER IF EXISTS trg_student_bd;
DROP TRIGGER IF EXISTS trg_faculty_bd;
DROP TRIGGER IF EXISTS trg_technician_bd;
DROP TRIGGER IF EXISTS trg_equipment_bi;
DROP TRIGGER IF EXISTS trg_equipment_bd;
DROP TRIGGER IF EXISTS trg_chemical_bi;
DROP TRIGGER IF EXISTS trg_chemical_bu;
DROP TRIGGER IF EXISTS trg_chemical_bd;
DROP TRIGGER IF EXISTS trg_asset_bu;
DROP TRIGGER IF EXISTS trg_room_bu;
DROP TRIGGER IF EXISTS trg_dispense_bi;
DROP TRIGGER IF EXISTS trg_dispense_bu;
DROP TRIGGER IF EXISTS trg_dispense_bd;
DROP TRIGGER IF EXISTS trg_booking_bi;
DROP TRIGGER IF EXISTS trg_booking_bu;
DROP TRIGGER IF EXISTS trg_lab_access_bi;

DROP TRIGGER IF EXISTS trg_student_bu;

DROP TRIGGER IF EXISTS trg_faculty_bu;

DROP TRIGGER IF EXISTS trg_technician_bu;

DROP TRIGGER IF EXISTS trg_equipment_bu;

DELIMITER $$

-- PK subtype bat bien de khong bo lai parent thieu subtype.
CREATE TRIGGER trg_student_bu BEFORE UPDATE ON student
FOR EACH ROW
BEGIN
    IF NEW.personnel_id <> OLD.personnel_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'student personnel_id is immutable';
    END IF;
END$$

CREATE TRIGGER trg_faculty_bu BEFORE UPDATE ON faculty
FOR EACH ROW
BEGIN
    IF NEW.personnel_id <> OLD.personnel_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'faculty personnel_id is immutable';
    END IF;
END$$

CREATE TRIGGER trg_technician_bu BEFORE UPDATE ON lab_technician
FOR EACH ROW
BEGIN
    IF NEW.personnel_id <> OLD.personnel_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'lab_technician personnel_id is immutable';
    END IF;
END$$

CREATE TRIGGER trg_equipment_bu BEFORE UPDATE ON equipment
FOR EACH ROW
BEGIN
    IF NEW.asset_id <> OLD.asset_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'equipment asset_id is immutable';
    END IF;
END$$

-- BR-01: Khong xoa vai tro duy nhat cua mot nhan su (Overlapping duoc giu).
CREATE TRIGGER trg_student_bd BEFORE DELETE ON student
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM faculty WHERE personnel_id = OLD.personnel_id)
       AND NOT EXISTS (SELECT 1 FROM lab_technician WHERE personnel_id = OLD.personnel_id)
       AND NOT EXISTS (SELECT 1 FROM collaborator WHERE personnel_id=OLD.personnel_id)
    THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-01: Personnel must keep at least one subtype';
    END IF;
END$$

CREATE TRIGGER trg_faculty_bd BEFORE DELETE ON faculty
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM student WHERE personnel_id = OLD.personnel_id)
       AND NOT EXISTS (SELECT 1 FROM lab_technician WHERE personnel_id = OLD.personnel_id)
       AND NOT EXISTS (SELECT 1 FROM collaborator WHERE personnel_id=OLD.personnel_id)
    THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-01: Personnel must keep at least one subtype';
    END IF;
END$$

CREATE TRIGGER trg_technician_bd BEFORE DELETE ON lab_technician
FOR EACH ROW
BEGIN
    IF NOT EXISTS (SELECT 1 FROM student WHERE personnel_id = OLD.personnel_id)
       AND NOT EXISTS (SELECT 1 FROM faculty WHERE personnel_id = OLD.personnel_id)
       AND NOT EXISTS (SELECT 1 FROM collaborator WHERE personnel_id=OLD.personnel_id)
    THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-01: Personnel must keep at least one subtype';
    END IF;
END$$

-- BR-02: Ngan chen sai loai tai san theo cot phan biet asset_type.
CREATE TRIGGER trg_equipment_bi BEFORE INSERT ON equipment
FOR EACH ROW
BEGIN
    DECLARE v_type VARCHAR(20) DEFAULT NULL;
    SELECT asset_type INTO v_type
    FROM lab_asset WHERE asset_id = NEW.asset_id FOR UPDATE;
    IF v_type IS NULL OR v_type <> 'EQUIPMENT' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-02: Equipment requires EQUIPMENT asset_type';
    END IF;
END$$

CREATE TRIGGER trg_equipment_bd BEFORE DELETE ON equipment
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-02: Do not delete subtype; retire asset instead';
END$$

-- BR-02 va BR-08: Kiểm tra loai tai san va cap an toan phong lab.
CREATE TRIGGER trg_chemical_bi BEFORE INSERT ON chemical_material
FOR EACH ROW
BEGIN
    DECLARE v_type VARCHAR(20) DEFAULT NULL;
    DECLARE v_room_safety INT DEFAULT NULL;
    SELECT a.asset_type, r.safety_category
        INTO v_type, v_room_safety
    FROM lab_asset AS a
    JOIN lab_room AS r ON r.room_id = a.room_id
    WHERE a.asset_id = NEW.asset_id
    FOR UPDATE;
    IF v_type IS NULL OR v_type <> 'CHEMICAL' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-02: Chemical requires CHEMICAL asset_type';
    END IF;
    IF NEW.hazard_level > v_room_safety THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-08: Room safety level is insufficient';
    END IF;
END$$

CREATE TRIGGER trg_chemical_bu BEFORE UPDATE ON chemical_material
FOR EACH ROW
BEGIN
    DECLARE v_room_safety INT DEFAULT NULL;
    IF NEW.asset_id <> OLD.asset_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Chemical asset_id is immutable';
    END IF;
    -- Cap nhat ton kho khong lam thay doi cap nguy hiem; tranh khoa thua.
    IF NEW.hazard_level <> OLD.hazard_level THEN
        SELECT r.safety_category INTO v_room_safety
        FROM lab_asset AS a
        JOIN lab_room AS r ON r.room_id = a.room_id
        WHERE a.asset_id = NEW.asset_id
        FOR SHARE;
        IF v_room_safety IS NULL OR NEW.hazard_level > v_room_safety THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-08: Hazard exceeds room safety';
        END IF;
    END IF;
END$$

CREATE TRIGGER trg_chemical_bd BEFORE DELETE ON chemical_material
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-02: Do not delete subtype; retire asset instead';
END$$

CREATE TRIGGER trg_asset_bu BEFORE UPDATE ON lab_asset
FOR EACH ROW
BEGIN
    DECLARE v_hazard INT DEFAULT NULL;
    DECLARE v_safety INT DEFAULT NULL;
    IF NEW.asset_type <> OLD.asset_type THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-02: Cannot change asset_type after registration';
    END IF;
    IF NEW.room_id <> OLD.room_id AND NEW.asset_type = 'CHEMICAL' THEN
        SELECT hazard_level INTO v_hazard
        FROM chemical_material WHERE asset_id = OLD.asset_id FOR UPDATE;
        IF v_hazard IS NOT NULL THEN
            SELECT safety_category INTO v_safety
            FROM lab_room WHERE room_id = NEW.room_id FOR SHARE;
            IF v_safety IS NULL OR v_hazard > v_safety THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-08: Cannot move chemical to unsafe room';
            END IF;
        END IF;
    END IF;
END$$

CREATE TRIGGER trg_room_bu BEFORE UPDATE ON lab_room
FOR EACH ROW
BEGIN
    DECLARE v_max_hazard INT DEFAULT NULL;
    IF NEW.safety_category < OLD.safety_category THEN
        SELECT c.hazard_level INTO v_max_hazard
        FROM lab_asset AS a
        JOIN chemical_material AS c ON c.asset_id = a.asset_id
        WHERE a.room_id = OLD.room_id
          AND c.hazard_level > NEW.safety_category
        LIMIT 1 FOR SHARE;
        IF COALESCE(v_max_hazard, 0) > NEW.safety_category THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-08: Room has chemicals above proposed category';
        END IF;
    END IF;
END$$

-- BR-03, BR-06, BR-07: Kiem tra va tru ton kho trong cung lenh INSERT.
-- UPDATE co dieu kien giu tinh nguyen tu va ngan hai giao dich cung xuat vuot ton.
CREATE TRIGGER trg_dispense_bi BEFORE INSERT ON chemical_dispense_log
FOR EACH ROW
BEGIN
    DECLARE v_hazard INT DEFAULT NULL;
    DECLARE v_expiry DATE DEFAULT NULL;
    DECLARE v_valid_cert INT DEFAULT 0;

    IF NEW.quantity IS NULL OR NEW.quantity <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-06: Dispense quantity must be positive';
    END IF;

    -- Ghi nhan thoi diem thuc thi do he quan tri cap, khong tin thoi diem client.
    SET NEW.dispense_date = CURRENT_TIMESTAMP;

    SELECT hazard_level, expiry_date INTO v_hazard, v_expiry
    FROM chemical_material WHERE asset_id = NEW.asset_id FOR UPDATE;
    IF v_hazard IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Invalid chemical asset_id';
    END IF;
    IF v_expiry < DATE(NEW.dispense_date) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-07: Chemical has expired';
    END IF;

    IF v_hazard >= 2 THEN
        SELECT pc.cert_id INTO v_valid_cert
        FROM personnel_certificate AS pc
        JOIN safety_certificate AS sc ON sc.cert_id = pc.cert_id
        WHERE pc.personnel_id = NEW.personnel_id
          AND sc.hazard_level >= v_hazard
          AND pc.issue_date <= DATE(NEW.dispense_date)
          AND pc.expiry_date >= DATE(NEW.dispense_date)
        LIMIT 1 FOR SHARE;
        IF v_valid_cert = 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-03: No matching valid safety certificate';
        END IF;
    END IF;

    UPDATE chemical_material
       SET stock_qty = stock_qty - NEW.quantity
     WHERE asset_id = NEW.asset_id AND stock_qty >= NEW.quantity;
    IF ROW_COUNT() <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-06: Insufficient chemical stock';
    END IF;
END$$

-- Nhat ky la bat bien; khong sua/xoa truc tiep va khong hoan kho ngam.
CREATE TRIGGER trg_dispense_bu BEFORE UPDATE ON chemical_dispense_log
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dispense log is immutable';
END$$

CREATE TRIGGER trg_dispense_bd BEFORE DELETE ON chemical_dispense_log
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dispense log is immutable';
END$$

-- BR-04: Khoa dong equipment de tuan tu hoa cac booking cho tung thiet bi.
-- Dung locking read cho booking de khong doc snapshot cu trong giao dich dai.
CREATE TRIGGER trg_booking_bi BEFORE INSERT ON equipment_booking
FOR EACH ROW
BEGIN
    DECLARE v_locked_asset INT DEFAULT NULL;
    DECLARE v_collision INT DEFAULT NULL;
    IF NEW.start_time IS NULL OR NEW.end_time IS NULL OR NEW.start_time >= NEW.end_time THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-04: Invalid booking time interval';
    END IF;
    IF NEW.start_time <= DATE_ADD(UTC_TIMESTAMP(),INTERVAL 7 HOUR) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BOOKING_PAST_TIME';
    END IF;
    IF MOD(MINUTE(NEW.start_time),15)<>0 OR MOD(MINUTE(NEW.end_time),15)<>0
       OR SECOND(NEW.start_time)<>0 OR SECOND(NEW.end_time)<>0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BOOKING_QUARTER_HOUR';
    END IF;
    SELECT asset_id INTO v_locked_asset
    FROM equipment WHERE asset_id = NEW.asset_id FOR UPDATE;
    IF v_locked_asset IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-04: Equipment does not exist';
    END IF;
    IF NEW.booking_status IN ('PENDING','APPROVED') THEN
    SELECT booking_id INTO v_collision
    FROM equipment_booking
    WHERE asset_id = NEW.asset_id
      AND booking_status IN ('PENDING','APPROVED')
      AND start_time < NEW.end_time AND NEW.start_time < end_time
    LIMIT 1 FOR SHARE;
    IF v_collision IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-04: Overlapping equipment booking';
    END IF;
    END IF;
END$$

CREATE TRIGGER trg_booking_bu BEFORE UPDATE ON equipment_booking
FOR EACH ROW
BEGIN
    DECLARE v_locked_asset INT DEFAULT NULL;
    DECLARE v_collision INT DEFAULT NULL;
    IF NEW.start_time IS NULL OR NEW.end_time IS NULL OR NEW.start_time >= NEW.end_time THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-04: Invalid booking time interval';
    END IF;
    IF NEW.start_time<>OLD.start_time OR NEW.end_time<>OLD.end_time OR (OLD.booking_status='REJECTED' AND NEW.booking_status IN ('PENDING','APPROVED')) THEN
    IF NEW.start_time <= DATE_ADD(UTC_TIMESTAMP(),INTERVAL 7 HOUR) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BOOKING_PAST_TIME';
    END IF;
    IF MOD(MINUTE(NEW.start_time),15)<>0 OR MOD(MINUTE(NEW.end_time),15)<>0
       OR SECOND(NEW.start_time)<>0 OR SECOND(NEW.end_time)<>0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BOOKING_QUARTER_HOUR';
    END IF;
    END IF;
    SELECT asset_id INTO v_locked_asset
    FROM equipment WHERE asset_id = NEW.asset_id FOR UPDATE;
    IF v_locked_asset IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-04: Equipment does not exist';
    END IF;
    IF NEW.booking_status IN ('PENDING','APPROVED') THEN
    SELECT booking_id INTO v_collision
    FROM equipment_booking
    WHERE asset_id = NEW.asset_id
      AND booking_status IN ('PENDING','APPROVED')
      AND booking_id <> OLD.booking_id
      AND start_time < NEW.end_time AND NEW.start_time < end_time
    LIMIT 1 FOR SHARE;
    IF v_collision IS NOT NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-04: Overlapping equipment booking';
    END IF;
    END IF;
END$$

-- Yeu cau dac thu de tai: kiem soat vao phong dang luu hoa chat nguy hiem.
-- Nhat ky co entry_time la thoi diem su kien; voi truy cap truc tiep nen dung sp_log_lab_access.
CREATE TRIGGER trg_lab_access_bi BEFORE INSERT ON lab_access_log
FOR EACH ROW
BEGIN
    DECLARE v_required_hazard INT DEFAULT 0;
    DECLARE v_valid_cert INT DEFAULT 0;
    SELECT COALESCE(MAX(c.hazard_level), 0) INTO v_required_hazard
    FROM lab_asset AS a
    JOIN chemical_material AS c ON c.asset_id = a.asset_id
    WHERE a.room_id = NEW.room_id;
    IF v_required_hazard >= 2 THEN
        SELECT pc.cert_id INTO v_valid_cert
        FROM personnel_certificate AS pc
        JOIN safety_certificate AS sc ON sc.cert_id = pc.cert_id
        WHERE pc.personnel_id = NEW.personnel_id
          AND sc.hazard_level >= v_required_hazard
          AND pc.issue_date <= DATE(NEW.entry_time)
          AND pc.expiry_date >= DATE(NEW.entry_time)
        LIMIT 1 FOR SHARE;
        IF v_valid_cert = 0 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unsafe lab access: valid certificate required';
        END IF;
    END IF;
END$$

-- Thu tuc tao nhan su voi it nhat mot vai tro; Overlapping duoc phep.
CREATE PROCEDURE sp_create_personnel(
    IN p_full_name VARCHAR(120), IN p_email VARCHAR(160), IN p_phone VARCHAR(20),
    IN p_student_code VARCHAR(20), IN p_major VARCHAR(100), IN p_gpa DECIMAL(3,2),
    IN p_faculty_code VARCHAR(20), IN p_academic_rank VARCHAR(80),
    IN p_staff_code VARCHAR(20), IN p_shift VARCHAR(30), OUT p_personnel_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    IF p_student_code IS NULL AND p_faculty_code IS NULL AND p_staff_code IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-01: At least one subtype is required';
    END IF;
    START TRANSACTION;
    INSERT INTO personnel (full_name, email, phone)
    VALUES (p_full_name, p_email, p_phone);
    SET p_personnel_id = LAST_INSERT_ID();
    IF p_student_code IS NOT NULL THEN
        INSERT INTO student (personnel_id, student_code, major, gpa)
        VALUES (p_personnel_id, p_student_code, p_major, p_gpa);
    END IF;
    IF p_faculty_code IS NOT NULL THEN
        INSERT INTO faculty (personnel_id, faculty_code, academic_rank)
        VALUES (p_personnel_id, p_faculty_code, p_academic_rank);
    END IF;
    IF p_staff_code IS NOT NULL THEN
        INSERT INTO lab_technician (personnel_id, staff_code, shift)
        VALUES (p_personnel_id, p_staff_code, p_shift);
    END IF;
    COMMIT;
END$$

CREATE PROCEDURE sp_create_equipment(
    IN p_name VARCHAR(150), IN p_room_id INT,
    IN p_serial VARCHAR(80), IN p_model VARCHAR(100), OUT p_asset_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    INSERT INTO lab_asset (asset_name, asset_type, status, room_id)
    VALUES (p_name, 'EQUIPMENT', 'AVAILABLE', p_room_id);
    SET p_asset_id = LAST_INSERT_ID();
    INSERT INTO equipment (asset_id, serial_number, model)
    VALUES (p_asset_id, p_serial, p_model);
    COMMIT;
END$$

CREATE PROCEDURE sp_create_chemical(
    IN p_name VARCHAR(150), IN p_room_id INT,
    IN p_hazard TINYINT, IN p_unit VARCHAR(20), IN p_stock DECIMAL(12,3),
    IN p_concentration VARCHAR(40), IN p_expiry DATE, OUT p_asset_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    IF p_expiry IS NULL OR p_expiry < CURRENT_DATE() THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'BR-07: Chemical has expired';
    END IF;
    IF p_stock IS NULL OR p_stock <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Chemical receipt quantity must be positive';
    END IF;
    START TRANSACTION;
    INSERT INTO lab_asset (asset_name, asset_type, status, room_id)
    VALUES (p_name, 'CHEMICAL', 'AVAILABLE', p_room_id);
    SET p_asset_id = LAST_INSERT_ID();
    INSERT INTO chemical_material
        (asset_id, hazard_level, unit, stock_qty, concentration, expiry_date)
    VALUES (p_asset_id, p_hazard, p_unit, p_stock, p_concentration, p_expiry);
    COMMIT;
END$$

CREATE PROCEDURE sp_dispense_chemical(
    IN p_asset_id INT, IN p_personnel_id INT, IN p_project_id INT,
    IN p_quantity DECIMAL(12,3), IN p_purpose VARCHAR(255), OUT p_dispense_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    INSERT INTO chemical_dispense_log
        (asset_id, personnel_id, project_id, quantity, purpose)
    VALUES (p_asset_id, p_personnel_id, p_project_id, p_quantity, p_purpose);
    SET p_dispense_id = LAST_INSERT_ID();
    COMMIT;
END$$

CREATE PROCEDURE sp_book_equipment(
    IN p_asset_id INT, IN p_personnel_id INT, IN p_project_id INT,
    IN p_start DATETIME, IN p_end DATETIME, IN p_purpose VARCHAR(255),
    OUT p_booking_id INT
)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    INSERT INTO equipment_booking
        (asset_id, personnel_id, project_id, start_time, end_time, purpose)
    VALUES (p_asset_id, p_personnel_id, p_project_id, p_start, p_end, p_purpose);
    SET p_booking_id = LAST_INSERT_ID();
    COMMIT;
END$$

CREATE PROCEDURE sp_log_lab_access(
    IN p_personnel_id INT, IN p_room_id INT, IN p_purpose VARCHAR(255),
    OUT p_access_id INT
)
BEGIN
    INSERT INTO lab_access_log (personnel_id, room_id, entry_time, purpose)
    VALUES (p_personnel_id, p_room_id, CURRENT_TIMESTAMP, p_purpose);
    SET p_access_id = LAST_INSERT_ID();
END$$

-- Kiem tra tinh Total/Disjoint tai thoi diem audit tren du lieu da commit.
CREATE PROCEDURE sp_audit_invariants()
BEGIN
    DECLARE v_missing_person INT DEFAULT 0;
    DECLARE v_wrong_assets INT DEFAULT 0;
    DECLARE v_unsafe_rooms INT DEFAULT 0;
    SELECT COUNT(*) INTO v_missing_person
    FROM personnel AS p
    WHERE NOT EXISTS (SELECT 1 FROM student AS s WHERE s.personnel_id = p.personnel_id)
      AND NOT EXISTS (SELECT 1 FROM faculty AS f WHERE f.personnel_id = p.personnel_id)
      AND NOT EXISTS (SELECT 1 FROM lab_technician AS t WHERE t.personnel_id = p.personnel_id)
      AND NOT EXISTS (SELECT 1 FROM collaborator co WHERE co.personnel_id=p.personnel_id);

    SELECT COUNT(*) INTO v_wrong_assets
    FROM lab_asset AS a
    LEFT JOIN equipment AS e ON e.asset_id = a.asset_id
    LEFT JOIN chemical_material AS c ON c.asset_id = a.asset_id
    WHERE (a.asset_type = 'EQUIPMENT' AND (e.asset_id IS NULL OR c.asset_id IS NOT NULL))
       OR (a.asset_type = 'CHEMICAL' AND (c.asset_id IS NULL OR e.asset_id IS NOT NULL));

    SELECT COUNT(*) INTO v_unsafe_rooms
    FROM chemical_material AS c
    JOIN lab_asset AS a ON a.asset_id = c.asset_id
    JOIN lab_room AS r ON r.room_id = a.room_id
    WHERE c.hazard_level > r.safety_category;

    SELECT v_missing_person AS personnel_without_subtype,
           v_wrong_assets AS invalid_asset_specialization,
           v_unsafe_rooms AS unsafe_chemical_locations;
    IF v_missing_person > 0 OR v_wrong_assets > 0 OR v_unsafe_rooms > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Specialization or room safety audit failed';
    END IF;
END$$

DELIMITER ;

CREATE VIEW v_chemical_expiring_soon AS
SELECT c.asset_id, a.asset_name, r.room_name, c.hazard_level,
       c.unit, c.stock_qty, c.expiry_date,
       DATEDIFF(c.expiry_date, CURRENT_DATE()) AS days_to_expiry,
       CASE
           WHEN c.expiry_date < CURRENT_DATE() THEN 'EXPIRED'
           ELSE 'EXPIRING_WITHIN_30_DAYS'
       END AS expiry_status
FROM chemical_material AS c
JOIN lab_asset AS a ON a.asset_id = c.asset_id
JOIN lab_room AS r ON r.room_id = a.room_id
WHERE c.expiry_date <= DATE_ADD(CURRENT_DATE(), INTERVAL 30 DAY);

CREATE VIEW v_project_asset_allocation AS
SELECT p.project_id, p.project_name, a.asset_id, a.asset_name,
       a.asset_type, COUNT(*) AS allocation_count,
       CASE WHEN a.asset_type='EQUIPMENT' THEN MAX(pa.allocated_qty) ELSE SUM(pa.allocated_qty) END AS total_allocated_qty,
       MAX(pa.allocated_at) AS last_allocated_at
FROM project_asset_allocation AS pa
JOIN research_project AS p ON p.project_id = pa.project_id
JOIN lab_asset AS a ON a.asset_id = pa.asset_id
GROUP BY p.project_id, p.project_name,
         a.asset_id, a.asset_name, a.asset_type;

DELIMITER $$

CREATE TRIGGER trg_collaborator_bu BEFORE UPDATE ON collaborator FOR EACH ROW
BEGIN
 IF NEW.personnel_id<>OLD.personnel_id THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='collaborator personnel_id is immutable'; END IF;
END$$
CREATE TRIGGER trg_collaborator_bd BEFORE DELETE ON collaborator FOR EACH ROW
BEGIN
 IF NOT EXISTS(SELECT 1 FROM student WHERE personnel_id=OLD.personnel_id)
 AND NOT EXISTS(SELECT 1 FROM faculty WHERE personnel_id=OLD.personnel_id)
 AND NOT EXISTS(SELECT 1 FROM lab_technician WHERE personnel_id=OLD.personnel_id) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='BR-01: Personnel must keep at least one subtype'; END IF;
END$$
DELIMITER ;

DELIMITER $$
CREATE TRIGGER trg_student_external_bi BEFORE INSERT ON student FOR EACH ROW
BEGIN
 IF EXISTS(SELECT 1 FROM collaborator WHERE personnel_id=NEW.personnel_id) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='External collaborator cannot hold an internal SV/GV/KT role'; END IF;
END$$
CREATE TRIGGER trg_faculty_external_bi BEFORE INSERT ON faculty FOR EACH ROW
BEGIN
 IF EXISTS(SELECT 1 FROM collaborator WHERE personnel_id=NEW.personnel_id) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='External collaborator cannot hold an internal SV/GV/KT role'; END IF;
END$$
CREATE TRIGGER trg_lab_technician_external_bi BEFORE INSERT ON lab_technician FOR EACH ROW
BEGIN
 IF EXISTS(SELECT 1 FROM collaborator WHERE personnel_id=NEW.personnel_id) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='External collaborator cannot hold an internal SV/GV/KT role'; END IF;
END$$
CREATE TRIGGER trg_collaborator_bi BEFORE INSERT ON collaborator FOR EACH ROW
BEGIN
 IF EXISTS(SELECT 1 FROM student WHERE personnel_id=NEW.personnel_id)
 OR EXISTS(SELECT 1 FROM faculty WHERE personnel_id=NEW.personnel_id)
 OR EXISTS(SELECT 1 FROM lab_technician WHERE personnel_id=NEW.personnel_id) THEN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='External collaborator cannot hold an internal SV/GV/KT role'; END IF;
END$$
DELIMITER ;

DELIMITER $$
CREATE TRIGGER trg_allocation_bi BEFORE INSERT ON project_asset_allocation FOR EACH ROW
BEGIN
 DECLARE v_type VARCHAR(20) DEFAULT NULL;
 SELECT asset_type INTO v_type FROM lab_asset WHERE asset_id=NEW.asset_id FOR SHARE;
 IF v_type='EQUIPMENT' AND NEW.allocated_qty<>1 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ALLOCATION_EQUIPMENT_ONE';
 END IF;
END$$
CREATE TRIGGER trg_allocation_bu BEFORE UPDATE ON project_asset_allocation FOR EACH ROW
BEGIN
 DECLARE v_type VARCHAR(20) DEFAULT NULL;
 SELECT asset_type INTO v_type FROM lab_asset WHERE asset_id=NEW.asset_id FOR SHARE;
 IF v_type='EQUIPMENT' AND NEW.allocated_qty<>1 THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ALLOCATION_EQUIPMENT_ONE';
 END IF;
END$$
DELIMITER ;
