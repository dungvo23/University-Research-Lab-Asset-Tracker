"""Registration requests are distinct from usable accounts until approval."""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from werkzeug.security import generate_password_hash
from pymysql import MySQLError
from webapp import db
from webapp.auth import operator_required, rate_limited, record_failure
from webapp.common import InputError, limited_text, positive_id, safe_db_message

bp = Blueprint('registration', __name__)
TYPES = {'STUDENT': 'Sinh viên', 'FACULTY': 'Giảng viên', 'LAB_TECHNICIAN': 'Kỹ thuật viên', 'COLLABORATOR':'Cộng tác viên ngoài trường'}


@bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    values = {k: request.form.get(k, '').strip() for k in ['full_name', 'email', 'phone', 'person_type', 'identity_code','home_institution']}
    if request.method == 'POST':
        try:
            if rate_limited('registration'):
                raise InputError('Bạn đã gửi nhiều yêu cầu. Vui lòng thử lại sau 15 phút.')
            record_failure('registration')
            name = limited_text(values['full_name'], 'Họ tên', 120, required=True)
            email = values['email'].lower()
            if len(email) > 160 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                raise InputError('Vui lòng nhập email hợp lệ.')
            phone = limited_text(values['phone'], 'Số điện thoại', 20)
            kind = values['person_type']
            if kind not in TYPES:
                raise InputError('Vui lòng chọn loại nhân sự hợp lệ.')
            code = values['identity_code']
            school=limited_text(values.get('home_institution'),'Trường/đơn vị bên ngoài',150)
            if kind=='COLLABORATOR':code=None
            if kind!='COLLABORATOR' and not re.fullmatch(r'[A-Za-z0-9]{1,20}', code):
                raise InputError('Mã sinh viên/giảng viên/kỹ thuật viên phải gồm 1–20 chữ hoặc số.')
            sample=re.fullmatch(r'(sv|gv|ctv)([0-9]+)@gmail[.]com',email)
            if sample:
                prefix,suffix=sample.groups();expected={'sv':('STUDENT','SV'),'gv':('FACULTY','GV'),'ctv':('COLLABORATOR',None)}[prefix]
                if kind!=expected[0] or (expected[1] and code.upper()!=expected[1]+f'{int(suffix):03d}'):
                    raise InputError('Loại nhân sự hoặc mã chưa khớp số cuối email (sv001 → SV001, gv001 → GV001; ctv không có mã SV/GV/KT).')
            password = request.form.get('password', '')
            if not 8 <= len(password) <= 128:
                raise InputError('Mật khẩu phải có từ 8 đến 128 ký tự.')
            if password != request.form.get('password_confirm', ''):
                raise InputError('Mật khẩu nhập lại không khớp.')
            if db.fetch_one('SELECT personnel_id FROM v_app_identity WHERE email=%s', (email,)) or db.fetch_one('SELECT operator_id FROM app_operator_account WHERE email=%s',(email,)):
                raise InputError('Email này đã có tài khoản. Vui lòng đăng nhập hoặc liên hệ Điều hành.')
            db.insert('''INSERT INTO app_registration_request
                (full_name,email,phone,person_type,identity_code,password_hash,home_institution)
                VALUES (%s,%s,%s,%s,%s,%s,%s)''',
                (name, email, phone, kind, code, generate_password_hash(password, method='scrypt'),school))
            return redirect(url_for('registration.submitted'))
        except InputError as exc:
            error = str(exc)
        except db.DatabaseUnavailable:
            raise
        except MySQLError as exc:
            error = ('Email này đã gửi yêu cầu. Vui lòng chờ duyệt hoặc liên hệ Điều hành.'
                     if exc.args[0] == 1062 else safe_db_message(exc))
    return render_template('register.html', title='Đăng ký tài khoản', values=values, error=error, types=TYPES)


@bp.get('/register/submitted')
def submitted():
    return render_template('register_submitted.html', title='Đã gửi yêu cầu đăng ký')


@bp.get('/registrations')
@operator_required
def requests_list():
    status = request.args.get('status', 'PENDING')
    if status not in ['PENDING', 'APPROVED', 'REJECTED']:
        raise InputError('Trạng thái yêu cầu không hợp lệ.')
    page = positive_id(request.args.get('page', '1'), 'Trang')
    total = db.scalar('SELECT COUNT(*) AS n FROM app_registration_request WHERE status=%s', (status,))
    rows = db.fetch_all('''SELECT r.request_id,r.full_name,r.email,r.phone,r.person_type,
        r.identity_code,r.home_institution,r.status,r.created_at,r.reviewed_at,r.review_note,COALESCE(o.display_name,p.full_name) AS reviewer
        FROM app_registration_request r LEFT JOIN personnel p ON p.personnel_id=r.reviewed_by
        LEFT JOIN app_operator_account o ON o.operator_id=r.reviewed_operator_id
        WHERE r.status=%s ORDER BY r.created_at DESC,r.request_id DESC LIMIT 20 OFFSET %s''', (status, (page-1)*20))
    return render_template('registrations.html', title='Duyệt đăng ký', rows=rows, types=TYPES,
                           status=status, total=total, page=page, pages=max(1,(total+19)//20))


@bp.post('/registrations/<int:request_id>/review')
@operator_required
def review(request_id):
    action = request.form.get('decision')
    if action not in ['approve', 'reject']:
        raise InputError('Quyết định không hợp lệ.')
    note = limited_text(request.form.get('note'), 'Ghi chú', 500, required=action=='reject')
    try:
        db.procedure('sp_review_registration', [request_id, g.user.get('operator_account_id',g.user['personnel_id']), action=='approve', note], out=False)
        flash('Đã duyệt tài khoản với quyền Thành viên.' if action=='approve' else 'Đã từ chối yêu cầu.', 'success')
    except db.DatabaseUnavailable:
        raise
    except MySQLError as exc:
        messages = {'REQUEST_NOT_PENDING': 'Yêu cầu đã được xử lý hoặc không tồn tại.',
                    'REQUEST_ACCOUNT_EXISTS': 'Email đã có tài khoản; không thể tạo trùng.',
                    'REQUEST_IDENTITY_MISMATCH': 'Mã nhân sự không khớp hồ sơ đã có của email này.',
                    'REQUEST_OPERATOR_REQUIRED': 'Chỉ Điều hành đang hoạt động mới được duyệt.'}
        text = next((v for k,v in messages.items() if k in str(exc)), safe_db_message(exc))
        flash(text, 'error')
    return redirect(url_for('registration.requests_list'))
