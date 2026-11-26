"""Approval workflow tests. Live cases require a separate disposable MySQL server."""
import os
import sys
from pathlib import Path
from uuid import uuid4
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def registration_app():
    if os.environ.get('INT1313_TEST_DISPOSABLE') != 'YES_DISPOSABLE_SERVER':
        pytest.skip('Registration writes require a disposable server')
    port = int(os.environ.get('TEST_DB_PORT', '0'))
    if port in (0, 3306, 13317):
        pytest.skip('Refusing the production/default MySQL port')
    from webapp.app import create_app
    return create_app({'TESTING': True, 'SECRET_KEY': 'registration-test-only',
        'DB_HOST': os.environ.get('TEST_DB_HOST', '127.0.0.1'), 'DB_PORT': port,
        'DB_NAME': 'university_lab_tracker', 'DB_USER': 'lab_app',
        'DB_PASSWORD': os.environ['TEST_DB_PASSWORD']})


def csrf(client):
    client.get('/register')
    with client.session_transaction() as s:
        return s['_csrf']


def operator(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s['operator_account_id'] = 1
    c.get('/registrations')
    return c


def request_account(app, kind='STUDENT'):
    c = app.test_client()
    suffix = uuid4().hex[:10]
    fields = dict(full_name='Người kiểm thử đăng ký', email=f'{suffix}@example.test',
                  phone='', person_type=kind, identity_code='RG'+suffix,
                  password='Registration123!', password_confirm='Registration123!',
                  role_code='OPERATOR', status='APPROVED', _csrf=csrf(c))
    r = c.post('/register', data=fields)
    assert r.status_code == 302 and r.location.endswith('/register/submitted')
    from webapp import db
    with app.app_context():
        row = db.fetch_one('SELECT request_id,status FROM app_registration_request WHERE email=%s', (fields['email'],))
    assert row['status'] == 'PENDING'
    return c, fields, row['request_id']


def try_login(c, fields):
    return c.post('/login', data={'identifier': fields['email'], 'password':fields['password'], '_csrf':csrf(c)})


def review(c, rid, decision, note=''):
    return c.post(f'/registrations/{rid}/review', data={'decision':decision,'note':note,'_csrf':csrf(c)}, follow_redirects=True)


@pytest.mark.parametrize('kind', ['STUDENT','FACULTY','LAB_TECHNICIAN','COLLABORATOR'])
def test_approval_required_and_grants_member_only(registration_app, kind):
    app = registration_app
    c, fields, rid = request_account(app, kind)
    assert try_login(c, fields).status_code == 200  # pending cannot sign in
    admin = operator(app)
    assert review(admin, rid, 'approve').status_code == 200
    assert try_login(c, fields).status_code == 302
    assert c.get('/profile').status_code == 200
    assert c.get('/registrations').status_code == 403
    from webapp import db
    with app.app_context():
        user = db.fetch_one('SELECT personnel_id FROM v_app_identity WHERE email=%s',(fields['email'],))
        assert db.fetch_all('SELECT role_code FROM app_account_role WHERE personnel_id=%s',(user['personnel_id'],)) == [{'role_code':'MEMBER'}]
    assert review(admin, rid, 'approve').status_code == 200
    with app.app_context():
        assert db.scalar('SELECT COUNT(*) AS n FROM personnel WHERE email=%s',(fields['email'],)) == 1


def test_rejection_and_csrf_and_member_guards(registration_app):
    app = registration_app
    c, fields, rid = request_account(app)
    assert c.post(f'/registrations/{rid}/review',data={'decision':'approve'}).status_code == 400
    assert review(operator(app), rid, 'reject', 'Hồ sơ chưa đáp ứng yêu cầu.').status_code == 200
    assert try_login(c, fields).status_code == 200
    member = app.test_client()
    with member.session_transaction() as s:s['personnel_id'] = 6
    assert review(member, rid, 'approve').status_code == 403


def test_seeded_account_cannot_be_registered_again(registration_app):
    app = registration_app
    from webapp import db
    with app.app_context():
        before = db.fetch_one('SELECT personnel_id,full_name,email FROM personnel WHERE personnel_id=2')
    c=app.test_client()
    fields=dict(full_name='Không thay tên hồ sơ cũ', email=before['email'], phone='',
                person_type='STUDENT',identity_code='SV002',password='Registration123!',password_confirm='Registration123!',_csrf=csrf(c))
    response = c.post('/register', data=fields)
    assert response.status_code == 200
    assert 'Email này đã có tài khoản' in response.get_data(as_text=True)
    with app.app_context():
        assert db.fetch_one('SELECT personnel_id,full_name,email FROM personnel WHERE personnel_id=2') == before
        assert db.scalar('SELECT COUNT(*) AS n FROM app_registration_request WHERE email=%s', (before['email'],)) == 0
