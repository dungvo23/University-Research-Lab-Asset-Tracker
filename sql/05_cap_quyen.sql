-- Tạo tài khoản lab_app@% bằng mật khẩu riêng trước khi chạy tệp này.
-- Dùng quyền quản trị CSDL để cấp quyền.
GRANT SELECT ON university_lab_tracker.v_app_identity TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.app_account_role TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.personnel TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.student TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.faculty TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.lab_technician TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.safety_certificate TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.personnel_certificate TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.research_project TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.project_member TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.lab_room TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.lab_asset TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.equipment TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.chemical_material TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.equipment_booking TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.chemical_dispense_log TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.lab_access_log TO 'lab_app'@'%';
GRANT SELECT, INSERT ON university_lab_tracker.maintenance_log TO 'lab_app'@'%';
GRANT SELECT, INSERT ON university_lab_tracker.project_asset_allocation TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.v_chemical_expiring_soon TO 'lab_app'@'%';
GRANT SELECT ON university_lab_tracker.v_project_asset_allocation TO 'lab_app'@'%';
GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_book_equipment TO 'lab_app'@'%';
GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_dispense_chemical TO 'lab_app'@'%';
GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_app_checkin TO 'lab_app'@'%';
GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_app_checkout TO 'lab_app'@'%';
GRANT INSERT (full_name,email,phone,person_type,identity_code,password_hash)
 ON university_lab_tracker.app_registration_request TO 'lab_app'@'%';
GRANT SELECT (request_id,full_name,email,phone,person_type,identity_code,status,created_at,reviewed_at,reviewed_by,review_note)
 ON university_lab_tracker.app_registration_request TO 'lab_app'@'%';
GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_review_registration TO 'lab_app'@'%';

GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_create_chemical TO 'lab_app'@'%';

GRANT SELECT ON university_lab_tracker.chemical_receipt TO 'lab_app'@'%';
GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_receive_chemical TO 'lab_app'@'%';

GRANT SELECT ON university_lab_tracker.app_operator_account TO 'lab_app'@'%';

GRANT SELECT (reviewed_operator_id) ON university_lab_tracker.app_registration_request TO 'lab_app'@'%';

GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_review_booking TO 'lab_app'@'%';

GRANT SELECT ON university_lab_tracker.collaborator TO 'lab_app'@'%';

GRANT SELECT (home_institution),INSERT (home_institution) ON university_lab_tracker.app_registration_request TO 'lab_app'@'%';

GRANT SELECT ON university_lab_tracker.certificate_update_request TO 'lab_app'@'%';
GRANT INSERT(personnel_id,cert_id,issue_date,expiry_date,previous_issue,previous_expiry,proof_file) ON university_lab_tracker.certificate_update_request TO 'lab_app'@'%';
GRANT EXECUTE ON PROCEDURE university_lab_tracker.sp_review_certificate TO 'lab_app'@'%';

GRANT SELECT ON university_lab_tracker.notification_seen TO 'lab_app'@'%';
GRANT INSERT(personnel_id,notification_kind,item_id) ON university_lab_tracker.notification_seen TO 'lab_app'@'%';
