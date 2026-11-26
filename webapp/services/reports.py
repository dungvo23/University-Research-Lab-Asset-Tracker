"""Auditable, allowlisted reports adapted from canonical sql/07_truy_van.sql.
Only value filters are bound; callers cannot submit SQL or select a table name.
"""
from datetime import date, datetime, timedelta
from webapp.common import InputError, local_datetime, positive_id


REPORTS = {
 'Q01': ('Đề tài, chủ nhiệm và số thành viên', '''
 SELECT p.project_id,p.project_name,f.faculty_code,owner.full_name AS principal_investigator,
 COALESCE(m.member_count,0) AS member_count,p.total_budget
 FROM research_project p JOIN faculty f ON f.personnel_id=p.pi_personnel_id
 JOIN personnel owner ON owner.personnel_id=f.personnel_id
 LEFT JOIN (SELECT project_id,COUNT(*) AS member_count FROM project_member GROUP BY project_id) m
 ON m.project_id=p.project_id ORDER BY p.project_id''', ''),
 'Q02': ('Thành viên và chứng chỉ còn hiệu lực', '''
 SELECT p.project_id,p.project_name,person.full_name,pm.project_role,pm.enroll_date,
 (SELECT COUNT(*) FROM personnel_certificate pc WHERE pc.personnel_id=pm.personnel_id
 AND pc.issue_date<=CURRENT_DATE() AND pc.expiry_date>=CURRENT_DATE()) AS active_certificate_count
 FROM project_member pm JOIN research_project p ON p.project_id=pm.project_id
 JOIN personnel person ON person.personnel_id=pm.personnel_id
 ORDER BY p.project_id,person.full_name''', ''),
 'Q03': ('Thiết bị theo phòng, bảo trì gần nhất', '''
 SELECT room.room_name,a.asset_id,a.asset_name,e.serial_number,a.status,mh.last_maintenance
 FROM equipment e JOIN lab_asset a ON a.asset_id=e.asset_id
 JOIN lab_room room ON room.room_id=a.room_id
 LEFT JOIN (SELECT asset_id,MAX(maint_date) AS last_maintenance FROM maintenance_log GROUP BY asset_id) mh
 ON mh.asset_id=e.asset_id WHERE a.status<>'RETIRED' ORDER BY room.room_name,a.asset_name''', ''),
 'Q04': ('Lịch đặt giao với khoảng thời gian', '''
 SELECT b.booking_id,a.asset_name,e.serial_number,p.full_name AS booked_by,pr.project_name,
 b.start_time,b.end_time,b.purpose,b.booking_status FROM equipment_booking b
 JOIN equipment e ON e.asset_id=b.asset_id JOIN lab_asset a ON a.asset_id=e.asset_id
 JOIN personnel p ON p.personnel_id=b.personnel_id
 LEFT JOIN research_project pr ON pr.project_id=b.project_id
 WHERE b.start_time<%s AND b.end_time>%s ORDER BY b.start_time,a.asset_name,b.booking_id''', 'interval'),
 'Q05': ('Nhân sự có chứng chỉ đạt cấp nguy hiểm', '''
 SELECT p.personnel_id,p.full_name,p.email,
 (SELECT MAX(sc.hazard_level) FROM personnel_certificate pc
 JOIN safety_certificate sc ON sc.cert_id=pc.cert_id
 WHERE pc.personnel_id=p.personnel_id AND pc.issue_date<=CURRENT_DATE()
 AND pc.expiry_date>=CURRENT_DATE()) AS max_valid_hazard_level
 FROM personnel p WHERE EXISTS(SELECT 1 FROM personnel_certificate pc
 JOIN safety_certificate sc ON sc.cert_id=pc.cert_id
 WHERE pc.personnel_id=p.personnel_id AND sc.hazard_level>=%s
 AND pc.issue_date<=CURRENT_DATE() AND pc.expiry_date>=CURRENT_DATE())
 ORDER BY p.personnel_id''', 'hazard'),
 'Q06': ('Hóa chất còn hạn, còn tồn, phòng an toàn', '''
 SELECT c.asset_id,a.asset_name,r.room_name,c.unit,c.stock_qty,c.hazard_level,
 r.safety_category,c.expiry_date FROM chemical_material c
 JOIN lab_asset a ON a.asset_id=c.asset_id JOIN lab_room r ON r.room_id=a.room_id
 WHERE c.stock_qty>0 AND c.expiry_date>=CURRENT_DATE()
 AND r.safety_category>=c.hazard_level ORDER BY c.expiry_date,a.asset_name''', ''),
 'Q07': ('Số lượng hóa chất cấp phát theo đề tài', '''
 SELECT p.project_id,p.project_name,c.asset_id,a.asset_name,c.unit,
 COUNT(*) AS dispense_count,SUM(d.quantity) AS total_dispensed
 FROM chemical_dispense_log d JOIN research_project p ON p.project_id=d.project_id
 JOIN chemical_material c ON c.asset_id=d.asset_id JOIN lab_asset a ON a.asset_id=c.asset_id
 GROUP BY p.project_id,p.project_name,c.asset_id,a.asset_name,c.unit
 ORDER BY p.project_id,total_dispensed DESC''', ''),
 'Q08': ('Số tài sản theo phòng (kể cả phòng trống)', '''
 SELECT r.room_id,r.room_name,r.safety_category,COUNT(DISTINCT a.asset_id) AS asset_count,
 COUNT(DISTINCT CASE WHEN a.asset_type='EQUIPMENT' THEN a.asset_id END) AS equipment_count,
 COUNT(DISTINCT CASE WHEN a.asset_type='CHEMICAL' THEN a.asset_id END) AS chemical_count
 FROM lab_room r LEFT JOIN lab_asset a ON a.room_id=r.room_id
 GROUP BY r.room_id,r.room_name,r.safety_category ORDER BY r.room_id''', ''),
 'Q09': ('Đề tài có ít nhất N tài sản phân bổ khác nhau', '''
 SELECT p.project_id,p.project_name,COUNT(DISTINCT pa.asset_id) AS distinct_allocated_assets
 FROM research_project p JOIN project_asset_allocation pa ON pa.project_id=p.project_id
 GROUP BY p.project_id,p.project_name HAVING COUNT(DISTINCT pa.asset_id)>=%s
 ORDER BY distinct_allocated_assets DESC,p.project_id''', 'threshold'),
 'Q10': ('Bảo trì mới nhất (mỗi thiết bị đúng một hàng)', '''
 SELECT a.asset_id,a.asset_name,e.serial_number,m.maint_date AS last_maintenance_date,
 m.description,tech.full_name AS technician_name
 FROM equipment e JOIN lab_asset a ON a.asset_id=e.asset_id
 LEFT JOIN maintenance_log m ON m.asset_id=e.asset_id AND m.maint_id=(
 SELECT m2.maint_id FROM maintenance_log m2 WHERE m2.asset_id=e.asset_id
 ORDER BY m2.maint_date DESC,m2.maint_id DESC LIMIT 1)
 LEFT JOIN personnel tech ON tech.personnel_id=m.technician_id ORDER BY a.asset_id''', ''),
 'Q11': ('Nhân sự thiếu chứng chỉ đạt cấp nguy hiểm', '''
 SELECT p.personnel_id,p.full_name,p.email FROM personnel p WHERE NOT EXISTS(
 SELECT 1 FROM personnel_certificate pc JOIN safety_certificate sc ON sc.cert_id=pc.cert_id
 WHERE pc.personnel_id=p.personnel_id AND sc.hazard_level>=%s
 AND pc.issue_date<=CURRENT_DATE() AND pc.expiry_date>=CURRENT_DATE())
 ORDER BY p.personnel_id''', 'hazard'),
 'Q12': ('Lượt ra vào và số phút đã hoàn thành', '''
 SELECT p.personnel_id,p.full_name,r.room_id,r.room_name,COUNT(l.access_id) AS access_count,
 SUM(CASE WHEN l.exit_time IS NOT NULL THEN TIMESTAMPDIFF(MINUTE,l.entry_time,l.exit_time)
 ELSE 0 END) AS total_minutes,MAX(l.entry_time) AS last_entry_time
 FROM lab_access_log l JOIN personnel p ON p.personnel_id=l.personnel_id
 JOIN lab_room r ON r.room_id=l.room_id
 GROUP BY p.personnel_id,p.full_name,r.room_id,r.room_name
 ORDER BY access_count DESC,p.personnel_id''', ''),
 'V01': ('View: hóa chất hết hạn hoặc sắp hết hạn', '''
 SELECT asset_id,asset_name,room_name,hazard_level,unit,stock_qty,expiry_date,
 days_to_expiry,expiry_status FROM v_chemical_expiring_soon
 ORDER BY expiry_date,asset_id''', ''),
 'V02': ('View: phân bổ theo từng đề tài và tài sản', '''
 SELECT project_id,project_name,asset_id,asset_name,asset_type,
 allocation_count,total_allocated_qty,last_allocated_at
 FROM v_project_asset_allocation ORDER BY project_id,asset_id''', ''),
}


def get_report(key, args):
    if key not in REPORTS:
        raise KeyError(key)
    title, sql, filter_type = REPORTS[key]
    params = ()
    applied = {}
    if filter_type == 'interval':
        now = datetime.now()
        d0 = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        d1 = (d0.replace(day=28) + timedelta(days=4)).replace(day=1)
        start_text = args.get('from') or d0.strftime('%Y-%m-%dT%H:%M')
        end_text = args.get('to') or d1.strftime('%Y-%m-%dT%H:%M')
        start, end = local_datetime(start_text,'Ngày bắt đầu'), local_datetime(end_text,'Ngày kết thúc')
        if end <= start:
            raise InputError('Khoảng lọc phải có ngày kết thúc sau ngày bắt đầu.')
        params = (end, start)
        applied = {'from': start_text, 'to': end_text}
    elif filter_type == 'hazard':
        val = positive_id(args.get('hazard') or '4', 'Cấp nguy hiểm')
        if val > 5:
            raise InputError('Cấp nguy hiểm chỉ được từ 1 đến 5.')
        params = (val,)
        applied = {'hazard': val}
    elif filter_type == 'threshold':
        val = positive_id(args.get('threshold') or '3', 'Số tài sản tối thiểu')
        if val > 1000:
            raise InputError('Ngưỡng lọc quá lớn.')
        params = (val,)
        applied = {'threshold': val}
    return title, sql.strip(), params, filter_type, applied
