"""Minimal single-process auth, CSRF, and server-side role checks."""
from collections import defaultdict, deque
from functools import wraps
from hashlib import sha256
import hmac
import secrets
import time

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from webapp import db

# Bounded, process-local attempt records. Restarting or multi-worker deployment resets it.
_ATTEMPTS = defaultdict(deque)
_MAX_KEYS = 2000
_WINDOW_SECONDS = 15 * 60
_MAX_ATTEMPTS = 7


def _attempt_key(identifier):
    ip = (request.remote_addr or 'local')[:90]
    return (ip, sha256(identifier.strip().casefold().encode('utf-8')).hexdigest())


def rate_limited(identifier):
    if len(_ATTEMPTS) > _MAX_KEYS:
        _ATTEMPTS.clear()
    key = _attempt_key(identifier)
    bucket = _ATTEMPTS[key]
    now = time.monotonic()
    while bucket and now - bucket[0] > _WINDOW_SECONDS:
        bucket.popleft()
    return len(bucket) >= _MAX_ATTEMPTS


def record_failure(identifier):
    _ATTEMPTS[_attempt_key(identifier)].append(time.monotonic())


def clear_failures(identifier):
    _ATTEMPTS.pop(_attempt_key(identifier), None)


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


def check_csrf():
    expected = session.get('_csrf', '')
    actual = request.form.get('_csrf', '')
    if not (expected and actual and hmac.compare_digest(expected, actual)):
        abort(400, description='Yêu cầu không hợp lệ hoặc phiên đã hết hạn. Tải lại trang và thử lại.')


def authenticate(identifier, password):
    admin=db.fetch_one('SELECT operator_id,email,display_name,password_hash,is_active FROM app_operator_account WHERE LOWER(email)=LOWER(%s)',(identifier,))
    if admin:
        try: valid=check_password_hash(admin['password_hash'],password)
        except (ValueError,TypeError):valid=False
        if not valid or not admin['is_active']:return None
        return {'operator_account_id':admin['operator_id'],'personnel_id':None,
            'full_name':admin['display_name'],'email':admin['email'],'student_code':None,
            'operator':True,'roles':{'OPERATOR'}}
    # Academic identifiers remain profile data; every account signs in by email.
    records = db.fetch_all('''SELECT personnel_id,full_name,email,student_code,
         password_hash,is_active FROM v_app_identity
         WHERE LOWER(email)=LOWER(%s) LIMIT 2''',
         (identifier,))
    # Keep timing behavior for unknown identities; no user-specific feedback.
    if len(records) != 1:
        try:
            check_password_hash('scrypt:32768:8:1$placeholder$' + '0'*128, password)
        except (ValueError, TypeError):
            pass
        return None
    user = records[0]
    try:
        valid = check_password_hash(user['password_hash'], password)
    except (ValueError, TypeError):
        valid = False
    if not valid or not user['is_active']:
        return None
    roles = db.fetch_all('SELECT role_code FROM app_account_role WHERE personnel_id=%s',
                         (user['personnel_id'],))
    role_codes = {r['role_code'] for r in roles}
    if not role_codes.intersection({'MEMBER', 'OPERATOR'}):
        return None
    # Operating privileges are separate from student/staff subtypes. An operator
    # may also be a student, but must use their personnel email to sign in.
    if identifier.casefold() != user['email'].casefold():
        return None
    return {'personnel_id': user['personnel_id'], 'full_name': user['full_name'],
            'email': user['email'], 'student_code': user['student_code'],
            'roles': role_codes, 'operator': 'OPERATOR' in role_codes}


def current_user():
    operator_id=session.get('operator_account_id')
    if type(operator_id) is int and operator_id>0:
        admin=db.fetch_one('SELECT operator_id,email,display_name,is_active FROM app_operator_account WHERE operator_id=%s',(operator_id,))
        if not admin or not admin['is_active']:return None
        return {'operator_account_id':admin['operator_id'],'personnel_id':None,
            'full_name':admin['display_name'],'email':admin['email'],'student_code':None,
            'operator':True,'roles':{'OPERATOR'}}
    pid = session.get('personnel_id')
    if type(pid) is not int or pid <= 0:
        return None
    record = db.fetch_one('''SELECT personnel_id,full_name,email,student_code,is_active
                              FROM v_app_identity WHERE personnel_id=%s''', (pid,))
    if not record or not record['is_active']:
        return None
    roles = db.fetch_all('SELECT role_code FROM app_account_role WHERE personnel_id=%s', (pid,))
    role_codes = {r['role_code'] for r in roles}
    if not role_codes.intersection({'MEMBER', 'OPERATOR'}):
        return None
    if 'OPERATOR' in role_codes and not session.get('operator_email_login'):
        return None
    return {**record, 'roles': role_codes, 'operator': 'OPERATOR' in role_codes}


def login_required(view):
    @wraps(view)
    def inner(*args, **kwargs):
        if not getattr(g, 'user', None):
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return inner


def operator_required(view):
    @wraps(view)
    def inner(*args, **kwargs):
        if not getattr(g, 'user', None):
            return redirect(url_for('login'))
        if not g.user['operator']:
            abort(403)
        return view(*args, **kwargs)
    return inner
