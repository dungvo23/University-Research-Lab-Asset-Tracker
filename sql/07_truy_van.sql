-- INT1313 | Phase 3 - 03: 12 truy van SQL Q01-Q12 theo Bao cao Phan 1.
-- Chay sau khi tao bang, cai trigger/view va nap du lieu mau.
USE university_lab_tracker;
SET @query_from = '2026-12-01 00:00:00';
SET @query_to = '2027-01-01 00:00:00';
SET @hazard_level = 4;
SET @allocation_threshold = 3;

-- Q01. Danh sach de tai, giang vien PI va so thanh vien (JOIN + subquery tong hop).
SELECT p.project_id, p.project_name, f.faculty_code,
       owner.full_name AS principal_investigator,
       COALESCE(m.member_count, 0) AS member_count,
       p.total_budget
FROM research_project AS p
JOIN faculty AS f ON f.personnel_id = p.pi_personnel_id
JOIN personnel AS owner ON owner.personnel_id = f.personnel_id
LEFT JOIN (
    SELECT project_id, COUNT(*) AS member_count
    FROM project_member
    GROUP BY project_id
) AS m ON m.project_id = p.project_id
ORDER BY p.project_id;

-- Q02. Thanh vien, vai tro va so chung chi con hieu luc (multi-JOIN + subquery).
SELECT p.project_id, p.project_name, person.full_name,
       pm.project_role, pm.enroll_date,
       (SELECT COUNT(*)
        FROM personnel_certificate AS pc
        WHERE pc.personnel_id = pm.personnel_id
          AND pc.issue_date <= CURRENT_DATE()
          AND pc.expiry_date >= CURRENT_DATE()) AS active_certificate_count
FROM project_member AS pm
JOIN research_project AS p ON p.project_id = pm.project_id
JOIN personnel AS person ON person.personnel_id = pm.personnel_id
ORDER BY p.project_id, person.full_name;

-- Q03. Thiet bi theo phong va lan bao tri gan nhat (JOIN + derived table + GROUP BY).
SELECT room.room_name, a.asset_id, a.asset_name, e.serial_number,
       a.status, mh.last_maintenance
FROM equipment AS e
JOIN lab_asset AS a ON a.asset_id = e.asset_id
JOIN lab_room AS room ON room.room_id = a.room_id
LEFT JOIN (
    SELECT asset_id, MAX(maint_date) AS last_maintenance
    FROM maintenance_log
    GROUP BY asset_id
) AS mh ON mh.asset_id = e.asset_id
WHERE a.status <> 'RETIRED'
ORDER BY room.room_name, a.asset_name;

-- Q04. Lich dat thiet bi giao voi khoang thoi gian chon (JOIN + loc giao nhau).
SELECT b.booking_id, a.asset_name, e.serial_number,
       p.full_name AS booked_by, pr.project_name,
       b.start_time, b.end_time, b.purpose
FROM equipment_booking AS b
JOIN equipment AS e ON e.asset_id = b.asset_id
JOIN lab_asset AS a ON a.asset_id = e.asset_id
JOIN personnel AS p ON p.personnel_id = b.personnel_id
LEFT JOIN research_project AS pr ON pr.project_id = b.project_id
WHERE b.start_time < @query_to AND b.end_time > @query_from
ORDER BY b.start_time, a.asset_name;

-- Q05. Nhan su co chung chi hop le voi cap nguy hiem da chon (EXISTS).
SELECT p.personnel_id, p.full_name, p.email,
       (SELECT MAX(sc.hazard_level)
        FROM personnel_certificate AS pc
        JOIN safety_certificate AS sc ON sc.cert_id = pc.cert_id
        WHERE pc.personnel_id = p.personnel_id
          AND pc.issue_date <= CURRENT_DATE()
          AND pc.expiry_date >= CURRENT_DATE()) AS max_valid_hazard_level
FROM personnel AS p
WHERE EXISTS (
    SELECT 1
    FROM personnel_certificate AS pc
    JOIN safety_certificate AS sc ON sc.cert_id = pc.cert_id
    WHERE pc.personnel_id = p.personnel_id
      AND sc.hazard_level >= @hazard_level
      AND pc.issue_date <= CURRENT_DATE()
      AND pc.expiry_date >= CURRENT_DATE()
)
ORDER BY p.personnel_id;

-- Q06. Hoa chat con han, con ton va phong bao dam an toan (3 JOIN).
SELECT c.asset_id, a.asset_name, r.room_name, c.unit,
       c.stock_qty, c.hazard_level, r.safety_category, c.expiry_date
FROM chemical_material AS c
JOIN lab_asset AS a ON a.asset_id = c.asset_id
JOIN lab_room AS r ON r.room_id = a.room_id
WHERE c.stock_qty > 0
  AND c.expiry_date >= CURRENT_DATE()
  AND r.safety_category >= c.hazard_level
ORDER BY c.expiry_date, a.asset_name;

-- Q07. Tong luong hoa chat da cap phat theo de tai va loai hoa chat.
SELECT p.project_id, p.project_name, c.asset_id, a.asset_name,
       c.unit, COUNT(*) AS dispense_count,
       SUM(d.quantity) AS total_dispensed
FROM chemical_dispense_log AS d
JOIN research_project AS p ON p.project_id = d.project_id
JOIN chemical_material AS c ON c.asset_id = d.asset_id
JOIN lab_asset AS a ON a.asset_id = c.asset_id
GROUP BY p.project_id, p.project_name,
         c.asset_id, a.asset_name, c.unit
ORDER BY p.project_id, total_dispensed DESC;

-- Q08. Dem tai san theo phong ke ca phong trong (LEFT JOIN + COUNT DISTINCT).
SELECT r.room_id, r.room_name, r.safety_category,
       COUNT(DISTINCT a.asset_id) AS asset_count,
       COUNT(DISTINCT CASE WHEN a.asset_type = 'EQUIPMENT' THEN a.asset_id END)
           AS equipment_count,
       COUNT(DISTINCT CASE WHEN a.asset_type = 'CHEMICAL' THEN a.asset_id END)
           AS chemical_count
FROM lab_room AS r
LEFT JOIN lab_asset AS a ON a.room_id = r.room_id
GROUP BY r.room_id, r.room_name, r.safety_category
ORDER BY r.room_id;

-- Q09. De tai co it nhat @allocation_threshold tai san khac nhau (HAVING).
SELECT p.project_id, p.project_name,
       COUNT(DISTINCT pa.asset_id) AS distinct_allocated_assets
FROM research_project AS p
JOIN project_asset_allocation AS pa ON pa.project_id = p.project_id
GROUP BY p.project_id, p.project_name
HAVING COUNT(DISTINCT pa.asset_id) >= @allocation_threshold
ORDER BY distinct_allocated_assets DESC, p.project_id;

-- Q10. Lan bao tri gan nhat tung thiet bi, van giu thiet bi chua bao tri.
SELECT a.asset_id, a.asset_name, e.serial_number,
       m.maint_date AS last_maintenance_date, m.description,
       tech.full_name AS technician_name
FROM equipment AS e
JOIN lab_asset AS a ON a.asset_id = e.asset_id
LEFT JOIN maintenance_log AS m
    ON m.asset_id = e.asset_id
   AND m.maint_id = (
       SELECT m2.maint_id
       FROM maintenance_log AS m2
       WHERE m2.asset_id = e.asset_id
       ORDER BY m2.maint_date DESC, m2.maint_id DESC
       LIMIT 1
   )
LEFT JOIN personnel AS tech ON tech.personnel_id = m.technician_id
ORDER BY a.asset_id;

-- Q11. Nhan su khong co chung chi hop le cho cap nguy hiem da chon.
SELECT p.personnel_id, p.full_name, p.email
FROM personnel AS p
WHERE NOT EXISTS (
    SELECT 1
    FROM personnel_certificate AS pc
    JOIN safety_certificate AS sc ON sc.cert_id = pc.cert_id
    WHERE pc.personnel_id = p.personnel_id
      AND sc.hazard_level >= @hazard_level
      AND pc.issue_date <= CURRENT_DATE()
      AND pc.expiry_date >= CURRENT_DATE()
)
ORDER BY p.personnel_id;

-- Q12. Thong ke luot ra vao va tong thoi gian su dung phong theo nhan su.
SELECT p.personnel_id, p.full_name, r.room_id, r.room_name,
       COUNT(l.access_id) AS access_count,
       SUM(CASE WHEN l.exit_time IS NOT NULL
                THEN TIMESTAMPDIFF(MINUTE, l.entry_time, l.exit_time)
                ELSE 0 END) AS total_minutes,
       MAX(l.entry_time) AS last_entry_time
FROM lab_access_log AS l
JOIN personnel AS p ON p.personnel_id = l.personnel_id
JOIN lab_room AS r ON r.room_id = l.room_id
GROUP BY p.personnel_id, p.full_name, r.room_id, r.room_name
ORDER BY access_count DESC, p.personnel_id;
