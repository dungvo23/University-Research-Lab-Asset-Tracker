-- INT1313 | Phase 3 - 02: Du lieu gia lap, KHONG phai ket qua thu nghiem.
-- Truoc khi nap: 01_tao_bang.sql -> 02_trigger_view_procedure.sql.
-- Chay mot lan tren co so du lieu moi; toan bo INSERT nam trong 1 giao dich.
USE university_lab_tracker;
SET NAMES utf8mb4;
START TRANSACTION;

INSERT INTO personnel (personnel_id, full_name, email, phone) VALUES
    (1, 'Nguyễn Minh Đức', 'gv009@gmail.com', '0900000001'),
    (2, 'Trần Văn Nam', 'sv002@gmail.com', '0900000002'),
    (3, 'Lê Hoàng Anh', 'sv003@gmail.com', '0900000003'),
    (4, 'Phạm Gia Huy', 'sv004@gmail.com', '0900000004'),
    (5, 'Hoàng Thu Hà', 'sv005@gmail.com', '0900000005'),
    (6, 'Nguyễn Hải Đăng', 'sv001@gmail.com', '0900000006'),
    (7, 'Trần Quốc Bảo', 'gv001@gmail.com', '0900000007'),
    (8, 'Lê Thị Mai', 'gv002@gmail.com', '0900000008'),
    (9, 'Phạm Minh Tuấn', 'gv003@gmail.com', '0900000009'),
    (10, 'Vũ Ngọc Lan', 'gv004@gmail.com', '0900000010'),
    (11, 'Đặng Thanh Tùng', 'gv005@gmail.com', '0900000011'),
    (12, 'Bùi Thu Hương', 'gv006@gmail.com', '0900000012'),
    (13, 'Đỗ Quang Huy', 'gv007@gmail.com', '0900000013'),
    (14, 'Ngô Thị Hạnh', 'gv008@gmail.com', '0900000014'),
    (15, 'Dương Minh Khang', 'sv006@gmail.com', '0900000015'),
    (16, 'Đinh Bảo Ngọc', 'sv007@gmail.com', '0900000016'),
    (17, 'Lý Anh Khoa', 'sv008@gmail.com', '0900000017'),
    (18, 'Mai Phương Linh', 'sv009@gmail.com', '0900000018'),
    (19, 'Tạ Đức Anh', 'sv010@gmail.com', '0900000019'),
    (20, 'Hồ Khánh Vy', 'sv011@gmail.com', '0900000020'),
    (21, 'Nguyễn Văn Sơn', 'ctv001@gmail.com', '0900000021'),
    (22, 'Trần Thị Hồng', 'ctv002@gmail.com', '0900000022'),
    (23, 'Lê Minh Phúc', 'ctv003@gmail.com', '0900000023'),
    (24, 'Phạm Thanh Bình', 'ctv004@gmail.com', '0900000024');

INSERT INTO student (personnel_id, student_code, major, gpa) VALUES
    (2, 'SV002', 'Kỹ thuật điện', 2.70),
    (3, 'SV003', 'Khoa học máy tính', 2.80),
    (4, 'SV004', 'Kỹ thuật điện', 2.90),
    (5, 'SV005', 'Khoa học máy tính', 3.00),
    (6, 'SV001', 'Kỹ thuật điện', 3.10),
    (15, 'SV006', 'Khoa học máy tính', 3.00),
    (16, 'SV007', 'Kỹ thuật điện', 3.10),
    (17, 'SV008', 'Khoa học máy tính', 3.20),
    (18, 'SV009', 'Kỹ thuật điện', 3.30),
    (19, 'SV010', 'Khoa học máy tính', 3.40),
    (20, 'SV011', 'Kỹ thuật điện', 2.50);

INSERT INTO faculty (personnel_id, faculty_code, academic_rank) VALUES
    (1, 'GV009', 'Giảng viên'),
    (7, 'GV001', 'Giảng viên'),
    (8, 'GV002', 'Giảng viên chính'),
    (9, 'GV003', 'Giảng viên'),
    (10, 'GV004', 'Giảng viên chính'),
    (11, 'GV005', 'Giảng viên'),
    (12, 'GV006', 'Giảng viên chính'),
    (13, 'GV007', 'Giảng viên'),
    (14, 'GV008', 'Giảng viên chính');

INSERT INTO lab_technician (personnel_id, staff_code, shift) VALUES
 (1,'KT009','Sáng'),(2,'KT002','Chiều'),(7,'KT001','Sáng');

INSERT INTO collaborator(personnel_id,home_institution) VALUES (21,NULL),(22,NULL),(23,NULL),(24,NULL);

INSERT INTO safety_certificate (cert_id, cert_name, hazard_level) VALUES
    (1, 'Chứng chỉ an toàn cấp 1', 1),
    (2, 'Chứng chỉ an toàn cấp 2', 2),
    (3, 'Chứng chỉ an toàn cấp 3', 3),
    (4, 'Chứng chỉ an toàn cấp 4', 4),
    (5, 'Chứng chỉ an toàn cấp 5', 5),
    (6, 'Chứng chỉ an toàn nâng cao', 5);

INSERT INTO personnel_certificate (personnel_id, cert_id, issue_date, expiry_date) VALUES
    (1, 6, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (2, 6, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (3, 6, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (4, 6, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (5, 6, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (6, 6, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (7, 6, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)),
    (8, 4, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (9, 5, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (10, 1, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (11, 2, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (12, 3, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (13, 4, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (14, 5, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (15, 1, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (16, 2, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (17, 3, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (18, 4, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (19, 5, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (20, 1, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (21, 2, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (22, 3, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (23, 4, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (24, 1, DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY), DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY));

INSERT INTO research_project (project_id, project_name, start_date, end_date, total_budget, funding_source, pi_personnel_id) VALUES
    (1, 'Khảo sát pH của dung dịch HCl, HNO3 và hệ đệm phosphat', '2026-07-01', '2027-12-31', 107500000.00, 'Quỹ nghiên cứu trường', 7),
    (2, 'So sánh đặc tính của ethanol, acid citric và kali permanganate trong xử lý mẫu', '2026-07-01', '2027-12-31', 115000000.00, 'Hợp tác doanh nghiệp', 8),
    (3, 'Khảo sát đặc tính thuốc thử HNO3, H2O2 và dung dịch đệm phosphat', '2026-07-01', '2027-12-31', 122500000.00, 'Quỹ nghiên cứu trường', 9),
    (4, 'Khảo sát điều chỉnh pH bằng acid citric và NaOH trong nghiên cứu dung môi ethanol', '2026-07-01', '2027-12-31', 130000000.00, 'Hợp tác doanh nghiệp', 10),
    (5, 'Đánh giá dung môi acetone, H2O2 và hệ đệm phosphat phục vụ phân tích UV-Vis', '2026-07-01', '2027-12-31', 137500000.00, 'Quỹ nghiên cứu trường', 11),
    (6, 'Khảo sát đặc tính dung dịch đồng(II) sulfate với các tác nhân điều chỉnh pH', '2026-07-01', '2027-12-31', 145000000.00, 'Hợp tác doanh nghiệp', 12),
    (7, 'Nghiên cứu quản lý và lưu trữ riêng biệt acetone, HCl và H2O2 trong phòng thí nghiệm', '2026-07-01', '2027-12-31', 152500000.00, 'Quỹ nghiên cứu trường', 13),
    (8, 'Khảo sát đặc tính thuốc thử CuSO4, NaOH và KMnO4 trong phân tích dung dịch', '2026-07-01', '2027-12-31', 160000000.00, 'Hợp tác doanh nghiệp', 14);

INSERT INTO project_member (project_id, personnel_id, enroll_date, project_role) VALUES
    (1, 1, '2026-08-01', 'Nghiên cứu viên'),
    (1, 2, '2026-08-01', 'Nghiên cứu viên'),
    (1, 7, '2026-08-01', 'Hướng dẫn'),
    (2, 3, '2026-08-01', 'Nghiên cứu viên'),
    (2, 4, '2026-08-01', 'Nghiên cứu viên'),
    (2, 8, '2026-08-01', 'Hướng dẫn'),
    (3, 5, '2026-08-01', 'Nghiên cứu viên'),
    (3, 6, '2026-08-01', 'Nghiên cứu viên'),
    (3, 9, '2026-08-01', 'Hướng dẫn'),
    (4, 15, '2026-08-01', 'Nghiên cứu viên'),
    (4, 10, '2026-08-01', 'Hướng dẫn'),
    (5, 16, '2026-08-01', 'Nghiên cứu viên'),
    (5, 11, '2026-08-01', 'Hướng dẫn'),
    (6, 17, '2026-08-01', 'Nghiên cứu viên'),
    (6, 12, '2026-08-01', 'Hướng dẫn'),
    (7, 18, '2026-08-01', 'Nghiên cứu viên'),
    (7, 13, '2026-08-01', 'Hướng dẫn'),
    (8, 14, '2026-08-01', 'Hướng dẫn');

INSERT INTO lab_room (room_id, room_name, safety_category) VALUES
    (1, 'Phòng Lab 01', 1),
    (2, 'Phòng Lab 02', 2),
    (3, 'Phòng Lab 03', 3),
    (4, 'Phòng Lab 04', 4),
    (5, 'Phòng Lab 05', 5);

INSERT INTO lab_asset (asset_id, asset_name, asset_type, status, room_id) VALUES
    (1, 'Cân phân tích điện tử', 'EQUIPMENT', 'AVAILABLE', 2),
    (2, 'Máy ly tâm để bàn', 'EQUIPMENT', 'AVAILABLE', 3),
    (3, 'Kính hiển vi quang học', 'EQUIPMENT', 'AVAILABLE', 4),
    (4, 'Máy đo pH để bàn', 'EQUIPMENT', 'AVAILABLE', 5),
    (5, 'Máy quang phổ UV-Vis', 'EQUIPMENT', 'AVAILABLE', 1),
    (6, 'Máy khuấy từ gia nhiệt', 'EQUIPMENT', 'AVAILABLE', 2),
    (7, 'Máy trộn vortex', 'EQUIPMENT', 'AVAILABLE', 3),
    (8, 'Máy lắc phòng thí nghiệm', 'EQUIPMENT', 'AVAILABLE', 4),
    (9, 'Tủ sấy phòng thí nghiệm', 'EQUIPMENT', 'AVAILABLE', 5),
    (10, 'Tủ ấm vi sinh', 'EQUIPMENT', 'AVAILABLE', 1),
    (11, 'Bể điều nhiệt cách thủy', 'EQUIPMENT', 'AVAILABLE', 2),
    (12, 'Micropipette đơn kênh', 'EQUIPMENT', 'AVAILABLE', 3),
    (13, 'Dung dịch đệm phosphat', 'CHEMICAL', 'AVAILABLE', 1),
    (14, 'Acid citric (C6H8O7)', 'CHEMICAL', 'AVAILABLE', 2),
    (15, 'Hydrogen peroxide (H2O2)', 'CHEMICAL', 'AVAILABLE', 3),
    (16, 'Natri hydroxide (NaOH)', 'CHEMICAL', 'AVAILABLE', 3),
    (17, 'Acetone (C3H6O)', 'CHEMICAL', 'AVAILABLE', 4),
    (18, 'Đồng(II) sulfate ngậm 5 nước (CuSO4·5H2O)', 'CHEMICAL', 'AVAILABLE', 4),
    (19, 'Acid hydrochloric (HCl)', 'CHEMICAL', 'AVAILABLE', 5),
    (20, 'Kali permanganate (KMnO4)', 'CHEMICAL', 'AVAILABLE', 5),
    (21, 'Acid nitric (HNO3)', 'CHEMICAL', 'AVAILABLE', 5),
    (22, 'Natri chloride (NaCl)', 'CHEMICAL', 'AVAILABLE', 1),
    (23, 'Ethanol (C2H5OH)', 'CHEMICAL', 'AVAILABLE', 3),
    (24, 'Amoni chloride (NH4Cl)', 'CHEMICAL', 'AVAILABLE', 4);

INSERT INTO equipment (asset_id, serial_number, model) VALUES
    (1, 'EQM-0001', NULL),
    (2, 'EQM-0002', NULL),
    (3, 'EQM-0003', NULL),
    (4, 'EQM-0004', NULL),
    (5, 'EQM-0005', NULL),
    (6, 'EQM-0006', NULL),
    (7, 'EQM-0007', NULL),
    (8, 'EQM-0008', NULL),
    (9, 'EQM-0009', NULL),
    (10, 'EQM-0010', NULL),
    (11, 'EQM-0011', NULL),
    (12, 'EQM-0012', NULL);

INSERT INTO chemical_material (asset_id, hazard_level, unit, stock_qty, concentration, expiry_date) VALUES
    (13, 1, 'ml', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (14, 2, 'g', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 15 DAY)),
    (15, 2, 'ml', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (16, 3, 'g', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (17, 3, 'ml', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 28 DAY)),
    (18, 4, 'g', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (19, 4, 'ml', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (20, 5, 'g', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (21, 5, 'ml', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (22, 1, 'g', 100.000, NULL, DATE_SUB(CURRENT_DATE(), INTERVAL 10 DAY)),
    (23, 2, 'ml', 100.000, NULL, DATE_ADD(CURRENT_DATE(), INTERVAL 180 DAY)),
    (24, 3, 'g', 100.000, NULL, DATE_SUB(CURRENT_DATE(), INTERVAL 10 DAY));

INSERT INTO project_asset_allocation (allocation_id, project_id, asset_id, allocated_qty, allocated_at) VALUES
    (1, 1, 1, 1.000, '2026-10-01 09:00:00'),
    (2, 1, 13, 2.000, '2026-10-01 09:00:00'),
    (3, 1, 14, 2.000, '2026-10-01 09:00:00'),
    (4, 2, 2, 1.000, '2026-10-01 09:00:00'),
    (5, 2, 15, 2.000, '2026-10-01 09:00:00'),
    (6, 2, 16, 2.000, '2026-10-01 09:00:00'),
    (7, 3, 3, 1.000, '2026-10-01 09:00:00'),
    (8, 3, 17, 2.000, '2026-10-01 09:00:00'),
    (9, 3, 18, 2.000, '2026-10-01 09:00:00'),
    (10, 4, 4, 1.000, '2026-10-01 09:00:00'),
    (11, 4, 19, 2.000, '2026-10-01 09:00:00'),
    (12, 5, 5, 1.000, '2026-10-01 09:00:00'),
    (13, 5, 20, 2.000, '2026-10-01 09:00:00'),
    (14, 6, 6, 1.000, '2026-10-01 09:00:00'),
    (15, 7, 7, 1.000, '2026-10-01 09:00:00'),
    (16, 8, 8, 1.000, '2026-10-01 09:00:00');

INSERT INTO equipment_booking (booking_id, asset_id, personnel_id, project_id, start_time, end_time, purpose, booking_status) VALUES
    (1, 1, 2, 2, '2026-12-01 08:00:00', '2026-12-01 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (2, 1, 2, 2, '2026-12-01 10:00:00', '2026-12-01 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (3, 2, 3, 3, '2026-12-02 08:00:00', '2026-12-02 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (4, 2, 3, 3, '2026-12-02 10:00:00', '2026-12-02 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (5, 3, 4, 4, '2026-12-03 08:00:00', '2026-12-03 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (6, 3, 4, 4, '2026-12-03 10:00:00', '2026-12-03 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (7, 4, 5, 5, '2026-12-04 08:00:00', '2026-12-04 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (8, 4, 5, 5, '2026-12-04 10:00:00', '2026-12-04 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (9, 5, 6, 6, '2026-12-05 08:00:00', '2026-12-05 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (10, 5, 6, 6, '2026-12-05 10:00:00', '2026-12-05 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (11, 6, 1, 7, '2026-12-06 08:00:00', '2026-12-06 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (12, 6, 1, 7, '2026-12-06 10:00:00', '2026-12-06 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (13, 7, 2, 8, '2026-12-07 08:00:00', '2026-12-07 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (14, 7, 2, 8, '2026-12-07 10:00:00', '2026-12-07 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (15, 8, 3, 1, '2026-12-08 08:00:00', '2026-12-08 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (16, 8, 3, 1, '2026-12-08 10:00:00', '2026-12-08 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (17, 9, 4, 2, '2026-12-09 08:00:00', '2026-12-09 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (18, 9, 4, 2, '2026-12-09 10:00:00', '2026-12-09 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (19, 10, 5, 3, '2026-12-10 08:00:00', '2026-12-10 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (20, 10, 5, 3, '2026-12-10 10:00:00', '2026-12-10 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (21, 11, 6, 4, '2026-12-11 08:00:00', '2026-12-11 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (22, 11, 6, 4, '2026-12-11 10:00:00', '2026-12-11 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (23, 12, 1, 5, '2026-12-12 08:00:00', '2026-12-12 10:00:00', 'Đặt lịch nghiên cứu', 'APPROVED'),
    (24, 12, 1, 5, '2026-12-12 10:00:00', '2026-12-12 12:00:00', 'Đặt lịch nghiên cứu', 'APPROVED');

INSERT INTO chemical_dispense_log (dispense_id, asset_id, personnel_id, project_id, quantity, dispense_date, purpose) VALUES
    (1, 13, 1, 1, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (2, 14, 2, 2, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (3, 15, 3, 3, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (4, 16, 4, 4, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (5, 17, 5, 5, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (6, 18, 6, 6, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (7, 19, 1, 7, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (8, 20, 2, 8, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (9, 21, 3, 1, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (10, 23, 4, 2, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (11, 13, 5, 3, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (12, 14, 6, 4, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (13, 15, 1, 5, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (14, 16, 2, 6, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (15, 17, 3, 7, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (16, 18, 4, 8, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (17, 19, 5, 1, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (18, 20, 6, 2, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (19, 21, 1, 3, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (20, 23, 2, 4, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (21, 13, 3, 5, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (22, 14, 4, 6, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (23, 15, 5, 7, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng'),
    (24, 16, 6, 8, 1.000, CURRENT_TIMESTAMP, 'Thực hành mô phỏng');

INSERT INTO lab_access_log (access_id, personnel_id, room_id, entry_time, exit_time, purpose) VALUES
    (1, 1, 3, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 24 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 23 HOUR), 'Ra vào phòng thí nghiệm'),
    (2, 2, 4, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 23 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 22 HOUR), 'Ra vào phòng thí nghiệm'),
    (3, 3, 5, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 22 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 21 HOUR), 'Ra vào phòng thí nghiệm'),
    (4, 4, 2, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 21 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 20 HOUR), 'Ra vào phòng thí nghiệm'),
    (5, 5, 3, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 20 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 19 HOUR), 'Ra vào phòng thí nghiệm'),
    (6, 6, 4, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 19 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 18 HOUR), 'Ra vào phòng thí nghiệm'),
    (7, 1, 5, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 18 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 17 HOUR), 'Ra vào phòng thí nghiệm'),
    (8, 2, 2, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 17 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 16 HOUR), 'Ra vào phòng thí nghiệm'),
    (9, 3, 3, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 16 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 15 HOUR), 'Ra vào phòng thí nghiệm'),
    (10, 4, 4, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 15 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 14 HOUR), 'Ra vào phòng thí nghiệm'),
    (11, 5, 5, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 14 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 13 HOUR), 'Ra vào phòng thí nghiệm'),
    (12, 6, 2, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 13 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 12 HOUR), 'Ra vào phòng thí nghiệm'),
    (13, 15, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 12 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 11 HOUR), 'Ra vào phòng thí nghiệm'),
    (14, 16, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 11 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 HOUR), 'Ra vào phòng thí nghiệm'),
    (15, 17, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 10 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 9 HOUR), 'Ra vào phòng thí nghiệm'),
    (16, 18, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 9 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 8 HOUR), 'Ra vào phòng thí nghiệm'),
    (17, 19, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 8 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 7 HOUR), 'Ra vào phòng thí nghiệm'),
    (18, 20, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 7 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 6 HOUR), 'Ra vào phòng thí nghiệm'),
    (19, 15, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 6 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 5 HOUR), 'Ra vào phòng thí nghiệm'),
    (20, 16, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 5 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 4 HOUR), 'Ra vào phòng thí nghiệm'),
    (21, 17, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 4 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 3 HOUR), 'Ra vào phòng thí nghiệm'),
    (22, 18, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 3 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 2 HOUR), 'Ra vào phòng thí nghiệm'),
    (23, 19, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 2 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 1 HOUR), 'Ra vào phòng thí nghiệm'),
    (24, 20, 1, DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 1 HOUR), DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 0 HOUR), 'Ra vào phòng thí nghiệm');

INSERT INTO maintenance_log (maint_id, asset_id, technician_id, maint_date, description) VALUES
    (1, 1, 1, '2026-10-02 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (2, 2, 2, '2026-10-03 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (3, 3, 7, '2026-10-04 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (4, 4, 2, '2026-10-05 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (5, 5, 1, '2026-10-06 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (6, 6, 7, '2026-10-07 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (7, 7, 1, '2026-10-08 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (8, 8, 2, '2026-10-09 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (9, 1, 2, '2026-10-10 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (10, 2, 1, '2026-10-11 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (11, 3, 7, '2026-10-12 09:00:00', 'Kiểm tra định kỳ mô phỏng'),
    (12, 4, 2, '2026-10-13 09:00:00', 'Kiểm tra định kỳ mô phỏng');

COMMIT;

-- Kiem tra tinh tham gia va phan loai sau khi nap.
CALL sp_audit_invariants();
SELECT (SELECT COUNT(*) FROM personnel) AS personnel_count,
       (SELECT COUNT(*) FROM research_project) AS project_count,
       (SELECT COUNT(*) FROM lab_asset) AS asset_count,
       (SELECT COUNT(*) FROM equipment_booking) AS booking_count,
       (SELECT COUNT(*) FROM chemical_dispense_log) AS dispense_count;
