"""Private certificate evidence and independently approved certificate changes."""
from pathlib import Path
import secrets
from flask import Blueprint, current_app, request, render_template, g, abort, redirect, url_for, flash, send_file
from pymysql import MySQLError
from webapp import db
from webapp.auth import login_required, operator_required
from webapp.common import InputError, optional_day, positive_id, limited_text, safe_db_message

bp = Blueprint('certificates', __name__)


def storage():
    return Path(current_app.config.get('CERTIFICATE_STORAGE', Path(current_app.root_path).parent / 'private' / 'certificates'))


@bp.route('/certificates', methods=['GET', 'POST'])
@login_required
def index():
    admin = bool(g.user.get('operator_account_id'))
    error = None
    values = request.form
    if request.method == 'POST':
        if admin: abort(403)
        proof_path = None
        try:
            cert = positive_id(values.get('cert_id'), 'Chứng chỉ')
            if not db.fetch_one('SELECT cert_id FROM safety_certificate WHERE cert_id=%s', (cert,)):
                raise InputError('Chứng chỉ không tồn tại.')
            issued = optional_day(values.get('issue_date'), 'Ngày cấp')
            expires = optional_day(values.get('expiry_date'), 'Ngày hết hạn')
            from datetime import datetime, timezone, timedelta
            today = datetime.now(timezone(timedelta(hours=7))).date()
            if not issued or not expires or issued > today or expires < today or expires <= issued:
                raise InputError('Ngày cấp không ở tương lai; hạn phải sau ngày cấp và chưa hết hạn.')
            proof = request.files.get('proof')
            if proof and proof.filename:
                data = proof.read(4 * 1024 * 1024 + 1)
                if len(data) > 4 * 1024 * 1024:
                    raise InputError('Minh chứng tối đa 4 MB.')
                suffix = '.pdf' if data.startswith(b'%PDF-') else '.png' if data.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg' if data.startswith(b'\xff\xd8\xff') else None
                if not suffix: raise InputError('Chỉ nhận nội dung PDF, PNG hoặc JPG.')
                folder = storage(); folder.mkdir(parents=True, exist_ok=True)
                proof_path = folder / (secrets.token_hex(24) + suffix)
                with proof_path.open('xb') as output: output.write(data)
            previous = db.fetch_one('SELECT issue_date,expiry_date FROM personnel_certificate WHERE personnel_id=%s AND cert_id=%s', (g.user['personnel_id'], cert))
            db.insert('''INSERT INTO certificate_update_request
                (personnel_id,cert_id,issue_date,expiry_date,previous_issue,previous_expiry,proof_file)
                VALUES(%s,%s,%s,%s,%s,%s,%s)''',
                (g.user['personnel_id'], cert, issued, expires, previous['issue_date'] if previous else None,
                 previous['expiry_date'] if previous else None, proof_path.name if proof_path else None))
            proof_path = None  # Evidence is now owned by the persisted request.
            flash('Đã gửi chứng chỉ, đang chờ ADMIN xác nhận. Chứng chỉ hiện tại chưa thay đổi.', 'success')
            return redirect(url_for('certificates.index'))
        except InputError as exc: error = str(exc)
        except db.DatabaseUnavailable: raise
        except MySQLError as exc:
            error = 'Bạn đã có yêu cầu chờ duyệt cho chứng chỉ này.' if exc.args[0] == 1062 else safe_db_message(exc)
        finally:
            if proof_path is not None and proof_path.exists(): proof_path.unlink()
    state = request.args.get('status', 'PENDING' if admin else '')
    if state not in ('', 'PENDING', 'APPROVED', 'REJECTED'): raise InputError('Trạng thái không hợp lệ.')
    conditions, params = [], []
    if not admin:
        conditions.append('r.personnel_id=%s'); params.append(g.user['personnel_id'])
    if state:
        conditions.append('r.status=%s'); params.append(state)
    rows = db.fetch_all('''SELECT r.request_id,r.personnel_id,p.full_name,p.email,c.cert_name,c.hazard_level,
        r.issue_date,r.expiry_date,r.proof_file,r.status,r.created_at,r.review_note,r.reviewed_at,o.display_name AS reviewer
        FROM certificate_update_request r JOIN personnel p USING(personnel_id)
        JOIN safety_certificate c USING(cert_id) LEFT JOIN app_operator_account o ON o.operator_id=r.reviewed_operator_id'''
        + (' WHERE ' + ' AND '.join(conditions) if conditions else '') + ' ORDER BY r.request_id DESC', tuple(params))
    if not admin:
        from webapp.notifications import seen
        seen('CERTIFICATE',[row['request_id'] for row in rows if row['status'] in ('APPROVED','REJECTED')])
    catalog = db.fetch_all('SELECT cert_id,cert_name,hazard_level FROM safety_certificate ORDER BY hazard_level,cert_id') if not admin else []
    return render_template('certificates.html', title='Duyệt chứng chỉ' if admin else 'Cập nhật chứng chỉ',
                           admin=admin, rows=rows, catalog=catalog, error=error, values=values, state=state)


@bp.post('/certificates/<int:request_id>/review')
@operator_required
def review(request_id):
    if not g.user.get('operator_account_id'): abort(403)
    decision = request.form.get('decision')
    if decision not in ('approve', 'reject'): raise InputError('Quyết định không hợp lệ.')
    note = limited_text(request.form.get('note'), 'Ghi chú', 500, required=decision == 'reject')
    try:
        db.procedure('sp_review_certificate', [request_id, g.user['operator_account_id'], decision == 'approve', note], out=False)
        flash('Đã xác nhận và cập nhật chứng chỉ.' if decision == 'approve' else 'Đã từ chối; chứng chỉ hiện tại được giữ nguyên.', 'success')
    except db.DatabaseUnavailable: raise
    except MySQLError as exc:
        messages = {'CERT_STALE_REQUEST': 'Chứng chỉ đã thay đổi sau lúc gửi yêu cầu. Hãy từ chối và yêu cầu gửi lại.',
                    'CERT_INVALID_DATES': 'Ngày cấp/hạn dùng không còn hợp lệ.',
                    'REQUEST_NOT_PENDING': 'Yêu cầu đã xử lý hoặc không tồn tại.'}
        flash(next((v for k,v in messages.items() if k in str(exc)), safe_db_message(exc)), 'error')
    return redirect(url_for('certificates.index'))


@bp.get('/certificates/<int:request_id>/proof')
@login_required
def proof(request_id):
    row = db.fetch_one('SELECT personnel_id,proof_file FROM certificate_update_request WHERE request_id=%s', (request_id,))
    if not row: abort(404)
    if not g.user.get('operator_account_id') and row['personnel_id'] != g.user['personnel_id']: abort(403)
    if not row['proof_file']: abort(404)
    folder = storage().resolve(); path = (folder / row['proof_file']).resolve()
    if path.parent != folder or not path.is_file(): abort(404)
    return send_file(path, as_attachment=True, download_name='chung_chi_' + str(request_id) + path.suffix)
