-- INT1313 | University Research & Lab Asset Tracker
-- Phase 3 - 01: Dinh nghia 17 bang va rang buoc
-- MySQL 8.0.16+ / InnoDB / utf8mb4
-- Chay mot lan tren database moi; khong xoa du lieu dang co.

CREATE DATABASE IF NOT EXISTS university_lab_tracker
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE university_lab_tracker;

CREATE TABLE personnel (
    personnel_id INT NOT NULL AUTO_INCREMENT,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL,
    phone VARCHAR(20) NULL,
    CONSTRAINT pk_personnel PRIMARY KEY (personnel_id),
    CONSTRAINT uq_personnel_email UNIQUE (email)
) ENGINE = InnoDB;

CREATE TABLE student (
    personnel_id INT NOT NULL,
    student_code VARCHAR(20) NOT NULL,
    major VARCHAR(100) NULL,
    gpa DECIMAL(3,2) NULL,
    CONSTRAINT pk_student PRIMARY KEY (personnel_id),
    CONSTRAINT uq_student_code UNIQUE (student_code),
    CONSTRAINT ck_student_gpa CHECK (gpa IS NULL OR gpa BETWEEN 0 AND 4),
    CONSTRAINT fk_student_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE faculty (
    personnel_id INT NOT NULL,
    faculty_code VARCHAR(20) NOT NULL,
    academic_rank VARCHAR(80) NULL,
    CONSTRAINT pk_faculty PRIMARY KEY (personnel_id),
    CONSTRAINT uq_faculty_code UNIQUE (faculty_code),
    CONSTRAINT fk_faculty_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE lab_technician (
    personnel_id INT NOT NULL,
    staff_code VARCHAR(20) NOT NULL,
    shift VARCHAR(30) NULL,
    CONSTRAINT pk_lab_technician PRIMARY KEY (personnel_id),
    CONSTRAINT uq_technician_code UNIQUE (staff_code),
    CONSTRAINT fk_technician_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE collaborator (
 personnel_id INT PRIMARY KEY,
 home_institution VARCHAR(150) NULL,
 FOREIGN KEY(personnel_id) REFERENCES personnel(personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE safety_certificate (
    cert_id INT NOT NULL AUTO_INCREMENT,
    cert_name VARCHAR(120) NOT NULL,
    hazard_level TINYINT NOT NULL,
    CONSTRAINT pk_safety_certificate PRIMARY KEY (cert_id),
    CONSTRAINT uq_cert_name UNIQUE (cert_name),
    CONSTRAINT ck_cert_hazard CHECK (hazard_level BETWEEN 1 AND 5)
) ENGINE = InnoDB;

-- Khoa ghep 2 cot theo pham vi Phase 2: moi nguoi mot ban ghi cho moi loai chung chi.
CREATE TABLE personnel_certificate (
    personnel_id INT NOT NULL,
    cert_id INT NOT NULL,
    issue_date DATE NOT NULL,
    expiry_date DATE NOT NULL,
    CONSTRAINT pk_personnel_certificate PRIMARY KEY (personnel_id, cert_id),
    CONSTRAINT ck_cert_dates CHECK (expiry_date > issue_date),
    CONSTRAINT fk_pc_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_pc_cert FOREIGN KEY (cert_id)
        REFERENCES safety_certificate (cert_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE research_project (
    project_id INT NOT NULL AUTO_INCREMENT,
    project_name VARCHAR(200) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NULL,
    total_budget DECIMAL(15,2) NOT NULL DEFAULT 0,
    funding_source VARCHAR(150) NULL,
    pi_personnel_id INT NOT NULL,
    CONSTRAINT pk_research_project PRIMARY KEY (project_id),
    CONSTRAINT ck_project_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_project_budget CHECK (total_budget >= 0),
    CONSTRAINT fk_project_pi FOREIGN KEY (pi_personnel_id)
        REFERENCES faculty (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE project_member (
    project_id INT NOT NULL,
    personnel_id INT NOT NULL,
    enroll_date DATE NOT NULL,
    project_role VARCHAR(60) NULL,
    CONSTRAINT pk_project_member PRIMARY KEY (project_id, personnel_id),
    CONSTRAINT fk_pm_project FOREIGN KEY (project_id)
        REFERENCES research_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_pm_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE lab_room (
    room_id INT NOT NULL AUTO_INCREMENT,
    room_name VARCHAR(120) NOT NULL,
    safety_category TINYINT NOT NULL,
    CONSTRAINT pk_lab_room PRIMARY KEY (room_id),
    CONSTRAINT uq_room_name UNIQUE (room_name),
    CONSTRAINT ck_room_safety CHECK (safety_category BETWEEN 1 AND 5)
) ENGINE = InnoDB;

-- asset_type la cot phan biet bo sung o muc trien khai de kiem soat Disjoint.
CREATE TABLE lab_asset (
    asset_id INT NOT NULL AUTO_INCREMENT,
    asset_name VARCHAR(150) NOT NULL,
    asset_type ENUM('EQUIPMENT', 'CHEMICAL') NOT NULL,
    status ENUM('AVAILABLE', 'IN_USE', 'MAINTENANCE', 'RETIRED')
        NOT NULL DEFAULT 'AVAILABLE',
    room_id INT NOT NULL,
    CONSTRAINT pk_lab_asset PRIMARY KEY (asset_id),
    CONSTRAINT fk_asset_room FOREIGN KEY (room_id)
        REFERENCES lab_room (room_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE equipment (
    asset_id INT NOT NULL,
    serial_number VARCHAR(80) NOT NULL,
    model VARCHAR(100) NULL,
    CONSTRAINT pk_equipment PRIMARY KEY (asset_id),
    CONSTRAINT uq_equipment_serial UNIQUE (serial_number),
    CONSTRAINT fk_equipment_asset FOREIGN KEY (asset_id)
        REFERENCES lab_asset (asset_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE chemical_material (
    asset_id INT NOT NULL,
    hazard_level TINYINT NOT NULL,
    unit VARCHAR(20) NOT NULL,
    stock_qty DECIMAL(12,3) NOT NULL DEFAULT 0,
    concentration VARCHAR(40) NULL,
    expiry_date DATE NOT NULL,
    CONSTRAINT pk_chemical_material PRIMARY KEY (asset_id),
    CONSTRAINT ck_chemical_hazard CHECK (hazard_level BETWEEN 1 AND 5),
    CONSTRAINT ck_chemical_stock CHECK (stock_qty >= 0),
    CONSTRAINT fk_chemical_asset FOREIGN KEY (asset_id)
        REFERENCES lab_asset (asset_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE project_asset_allocation (
    allocation_id INT NOT NULL AUTO_INCREMENT,
    project_id INT NOT NULL,
    asset_id INT NOT NULL,
    allocated_qty DECIMAL(12,3) NOT NULL,
    allocated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_project_asset_allocation PRIMARY KEY (allocation_id),
    CONSTRAINT ck_allocation_qty CHECK (allocated_qty > 0),
    CONSTRAINT fk_allocation_project FOREIGN KEY (project_id)
        REFERENCES research_project (project_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_allocation_asset FOREIGN KEY (asset_id)
        REFERENCES lab_asset (asset_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE equipment_booking (
    booking_id INT NOT NULL AUTO_INCREMENT,
    asset_id INT NOT NULL,
    personnel_id INT NOT NULL,
    project_id INT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    purpose VARCHAR(255) NULL,
    booking_status ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
    CONSTRAINT pk_equipment_booking PRIMARY KEY (booking_id),
    CONSTRAINT ck_booking_time CHECK (start_time < end_time),
    CONSTRAINT fk_booking_equipment FOREIGN KEY (asset_id)
        REFERENCES equipment (asset_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_booking_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_booking_project FOREIGN KEY (project_id)
        REFERENCES research_project (project_id) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE chemical_dispense_log (
    dispense_id INT NOT NULL AUTO_INCREMENT,
    asset_id INT NOT NULL,
    personnel_id INT NOT NULL,
    project_id INT NULL,
    quantity DECIMAL(12,3) NOT NULL,
    dispense_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    purpose VARCHAR(255) NULL,
    CONSTRAINT pk_chemical_dispense_log PRIMARY KEY (dispense_id),
    CONSTRAINT ck_dispense_qty CHECK (quantity > 0),
    CONSTRAINT fk_dispense_chemical FOREIGN KEY (asset_id)
        REFERENCES chemical_material (asset_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_dispense_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_dispense_project FOREIGN KEY (project_id)
        REFERENCES research_project (project_id) ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE lab_access_log (
    access_id INT NOT NULL AUTO_INCREMENT,
    personnel_id INT NOT NULL,
    room_id INT NOT NULL,
    entry_time DATETIME NOT NULL,
    exit_time DATETIME NULL,
    purpose VARCHAR(255) NULL,
    CONSTRAINT pk_lab_access_log PRIMARY KEY (access_id),
    CONSTRAINT ck_access_times CHECK (exit_time IS NULL OR exit_time >= entry_time),
    CONSTRAINT fk_access_personnel FOREIGN KEY (personnel_id)
        REFERENCES personnel (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_access_room FOREIGN KEY (room_id)
        REFERENCES lab_room (room_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

CREATE TABLE maintenance_log (
    maint_id INT NOT NULL AUTO_INCREMENT,
    asset_id INT NOT NULL,
    technician_id INT NOT NULL,
    maint_date DATETIME NOT NULL,
    description VARCHAR(500) NULL,
    CONSTRAINT pk_maintenance_log PRIMARY KEY (maint_id),
    CONSTRAINT fk_maintenance_equipment FOREIGN KEY (asset_id)
        REFERENCES equipment (asset_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
    CONSTRAINT fk_maintenance_technician FOREIGN KEY (technician_id)
        REFERENCES lab_technician (personnel_id) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE = InnoDB;

-- Chi muc bo sung (cac PK, UNIQUE va FK da co chi muc phuc vu tham chieu).
CREATE INDEX idx_asset_name ON lab_asset (asset_name);
CREATE INDEX idx_asset_room_status ON lab_asset (room_id, status);
CREATE INDEX idx_chemical_expiry ON chemical_material (expiry_date);
CREATE INDEX idx_booking_asset_time ON equipment_booking (asset_id, start_time, end_time);
CREATE INDEX idx_dispense_asset_date ON chemical_dispense_log (asset_id, dispense_date);
CREATE INDEX idx_pcert_person_expiry ON personnel_certificate (personnel_id, expiry_date);
CREATE INDEX idx_access_room_entry ON lab_access_log (room_id, entry_time);
CREATE INDEX idx_maintenance_asset_date ON maintenance_log (asset_id, maint_date);
