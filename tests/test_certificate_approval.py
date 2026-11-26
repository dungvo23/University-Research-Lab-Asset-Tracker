from io import BytesIO
from datetime import date
import pytest
from test_mysql_live_optional import disposable_app


def token(client):
    client.get('/certificates')
    with client.session_transaction() as s:return s['_csrf']


def test_certificates_change_only_after_admin_review(disposable_app,tmp_path):
    from webapp import db
    app=disposable_app;app.config['CERTIFICATE_STORAGE']=str(tmp_path/'proofs')
    member=app.test_client()
    with member.session_transaction() as s:s['personnel_id']=6
    with app.app_context():
        catalog=db.fetch_all('SELECT cert_id FROM safety_certificate ORDER BY cert_id')
        cert=catalog[0]['cert_id']
        before=db.fetch_one('SELECT issue_date,expiry_date FROM personnel_certificate WHERE personnel_id=6 AND cert_id=%s',(cert,))
    fields={'_csrf':token(member),'cert_id':str(cert),'issue_date':'2020-01-01','expiry_date':'2099-01-01','personnel_id':'7','status':'APPROVED','proof':(BytesIO(b'%PDF-1.4\ncertificate test'),'../../proof.pdf')}
    assert member.post('/certificates',data=fields,content_type='multipart/form-data').status_code==302
    with app.app_context():
        row=db.fetch_one('SELECT request_id,status,proof_file FROM certificate_update_request WHERE personnel_id=6 AND cert_id=%s',(cert,))
        assert row['status']=='PENDING' and '/' not in row['proof_file']
        assert db.fetch_one('SELECT issue_date,expiry_date FROM personnel_certificate WHERE personnel_id=6 AND cert_id=%s',(cert,))==before
    rid=row['request_id']
    other=app.test_client()
    with other.session_transaction() as s:s['personnel_id']=7
    assert other.get(f'/certificates/{rid}/proof').status_code==403
    assert member.get(f'/certificates/{rid}/proof').status_code==200
    assert member.post(f'/certificates/{rid}/review',data={'_csrf':token(member),'decision':'approve'}).status_code==403
    admin=app.test_client()
    with admin.session_transaction() as s:s['operator_account_id']=1
    assert admin.get(f'/certificates/{rid}/proof').status_code==200
    assert admin.post(f'/certificates/{rid}/review',data={'_csrf':token(admin),'decision':'approve'}).status_code==302
    with app.app_context():
        current=db.fetch_one('SELECT issue_date,expiry_date FROM personnel_certificate WHERE personnel_id=6 AND cert_id=%s',(cert,))
        assert current=={'issue_date':date(2020,1,1),'expiry_date':date(2099,1,1)}
        assert db.fetch_one('SELECT status,reviewed_operator_id FROM certificate_update_request WHERE request_id=%s',(rid,))=={'status':'APPROVED','reviewed_operator_id':1}
    # A subsequent rejected request must not overwrite the approved certificate.
    fields={'_csrf':token(member),'cert_id':str(cert),'issue_date':'2021-01-01','expiry_date':'2098-01-01','proof':(BytesIO(b'%PDF-1.4\nnew evidence'),'evidence.pdf')}
    assert member.post('/certificates',data=fields,content_type='multipart/form-data').status_code==302
    with app.app_context():rid2=db.scalar('SELECT MAX(request_id) AS n FROM certificate_update_request')
    assert admin.post(f'/certificates/{rid2}/review',data={'_csrf':token(admin),'decision':'reject','note':'Chưa đủ minh chứng'}).status_code==302
    with app.app_context():assert db.fetch_one('SELECT issue_date,expiry_date FROM personnel_certificate WHERE personnel_id=6 AND cert_id=%s',(cert,))==current


def test_codes_and_external_roles_match_email_suffix(disposable_app):
    from webapp import db
    with disposable_app.app_context():
        rows=db.fetch_all('SELECT p.email,s.student_code,f.faculty_code,t.staff_code,co.personnel_id AS collaborator_id FROM personnel p LEFT JOIN student s USING(personnel_id) LEFT JOIN faculty f USING(personnel_id) LEFT JOIN lab_technician t USING(personnel_id) LEFT JOIN collaborator co USING(personnel_id)')
        for row in rows:
            email=row['email'];suffix=email.split('@')[0][-3:]
            if email.startswith('sv'):assert row['student_code']=='SV'+suffix
            if email.startswith('gv'):assert row['faculty_code']=='GV'+suffix
            if email.startswith('ctv'):
                assert row['collaborator_id'] and not row['student_code'] and not row['faculty_code'] and not row['staff_code']
        assert db.fetch_one('SELECT staff_code FROM lab_technician WHERE personnel_id=1')['staff_code']=='KT009'
        assert db.fetch_one('SELECT staff_code FROM lab_technician WHERE personnel_id=7')['staff_code']=='KT001'
