"""Flask client tests with mocked DB; do NOT claim MySQL integrations from these."""
import importlib
import os
from pathlib import Path
import sys

import pytest

flask = pytest.importorskip('flask')
pytest.importorskip('pymysql')
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SECRET_KEY','test-only-secret-not-for-production')
    import webapp.app as app_module
    from webapp import db
    import webapp.notifications as notices
    monkeypatch.setattr(notices,'counts',lambda:{})
    monkeypatch.setattr(notices,'seen',lambda *a,**k:None)
    monkeypatch.setattr(notices,'seen_registration',lambda:None)
    accounts = {
       1:{'personnel_id':1,'full_name':'Người điều hành','email':'dh001@gmail.com',
          'student_code':'SV001','is_active':True,'password_hash':generate_password_hash('demo1')},
       6:{'personnel_id':6,'full_name':'Người dùng','email':'sv001@gmail.com',
          'student_code':'SV006','is_active':True,'password_hash':generate_password_hash('demo6')},
       7:{'personnel_id':7,'full_name':'Giảng viên','email':'gv001@gmail.com',
          'student_code':None,'is_active':True,'password_hash':generate_password_hash('demo7')},
    }
    def fake_one(sql, params=()):
        if 'SELECT 1 AS ready' in sql: return {'ready':1}
        if 'FROM v_app_identity' in sql and 'WHERE personnel_id=' in sql:
            return accounts.get(params[0])
        if 'FROM personnel p' in sql and 'WHERE p.personnel_id=' in sql:
            x=accounts.get(params[0])
            return None if x is None else {**x,'phone':None,'major':None,'gpa':None,
                'faculty_code':None,'academic_rank':None,'staff_code':None,'shift':None}
        return None
    def fake_all(sql, params=()):
        if 'FROM v_app_identity' in sql:
            i=str(params[0]).casefold()
            return [r.copy() for r in accounts.values() if r['email'].casefold()==i ]
        if 'FROM app_account_role' in sql:
            return [{'role_code':'OPERATOR' if params[0]==1 else 'MEMBER'}]
        return []
    monkeypatch.setattr(db,'fetch_one',fake_one)
    monkeypatch.setattr(db,'fetch_all',fake_all)
    monkeypatch.setattr(db,'scalar',lambda *args,**kwargs:0)
    monkeypatch.setattr(db,'procedure',lambda *args,**kwargs:123)
    app = app_module.create_app({'TESTING':True,'SECRET_KEY':'test-only-secret',
                                 'DB_PASSWORD':'not-used-for-mocked-tests'})
    return app.test_client()


def csrf(client):
    client.get('/login')
    with client.session_transaction() as sess:
        return sess['_csrf']


def login(client, user='sv001@gmail.com',password='demo6'):
    token=csrf(client)
    response=client.post('/login',data={'_csrf':token,'identifier':user,'password':password})
    if response.status_code == 302 and '/dashboard' in response.headers.get('Location',''):
        # Login rotates the session. The authenticated CSRF token is minted on
        # the first protected-page render, not on the redirect response.
        assert client.get('/dashboard').status_code == 200
    return response


def test_health_responses(client, monkeypatch):
    assert client.get('/health').status_code==200
    from webapp import db
    monkeypatch.setattr(db,'fetch_one',lambda *a,**k: (_ for _ in ()).throw(db.DatabaseUnavailable()))
    r=client.get('/health')
    assert r.status_code==503 and r.json['error']=='database_unavailable'


def test_login_logout_and_nonstudent_email(client):
    assert login(client,'sv001@gmail.com').status_code==302
    assert client.get('/profile').status_code==200
    with client.session_transaction() as sess:
        token=sess['_csrf']
    assert client.post('/logout',data={'_csrf':token}).status_code==302
    assert client.get('/profile').status_code==302
    assert login(client,'gv001@gmail.com','demo7').status_code==302


def test_casefold_email_student_login(client):
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    assert client.get('/reports').status_code==200


def test_member_cannot_escalate_via_query_or_post(client):
    assert login(client).status_code==302
    assert client.get('/reports').status_code==403
    assert client.get('/personnel').status_code==403
    assert client.get('/bookings?scope=all').status_code==403
    assert client.get('/dispenses?scope=all').status_code==403
    assert client.get('/access?scope=all').status_code==403
    with client.session_transaction() as sess: token=sess['_csrf']
    assert client.post('/allocations',data={'_csrf':token,'role':'OPERATOR'}).status_code==403
    assert client.post('/maintenance',data={'_csrf':token,'role':'OPERATOR'}).status_code==403


def test_bad_csrf_blocks_writes(client):
    assert login(client).status_code==302
    assert client.post('/access/check-in',data={'room_id':'1'}).status_code==400


def test_failed_login_has_generic_error(client):
    result=login(client,'unknown@example.test','badpass')
    assert result.status_code==200
    assert 'Email hoặc mật khẩu không đúng' in result.get_data(as_text=True)
    assert client.get('/profile').status_code==302


def test_private_identity_comes_from_session_not_form(client, monkeypatch):
    assert login(client).status_code==302
    from webapp import db
    captured=[]
    monkeypatch.setattr(db,'procedure',lambda name,args,out: captured.append((name,args)) or 42)
    with client.session_transaction() as sess: token=sess['_csrf']
    result=client.post('/access/check-in',data={'_csrf':token,'room_id':'1',
                      'personnel_id':'1','role_code':'OPERATOR'},follow_redirects=False)
    assert result.status_code==302
    assert captured[0][0]=='sp_app_checkin'
    assert captured[0][1][0]==6


def test_booking_uses_session_identity_and_half_open_times(client, monkeypatch):
    assert login(client).status_code==302
    from webapp import db
    called=[]
    monkeypatch.setattr(db,'procedure',lambda name,args,out: called.append((name,args,out)) or 88)
    with client.session_transaction() as s: token=s['_csrf']
    r=client.post('/bookings/new',data={
       '_csrf':token,'asset_id':'1','project_id':'','personnel_id':'1',
       'start_time':'2026-12-20T09:00','end_time':'2026-12-20T10:00',
       'purpose':'Thử đặt lịch'},follow_redirects=False)
    assert r.status_code==302
    assert called and called[0][0]=='sp_book_equipment'
    assert called[0][1][1]==6
    assert called[0][1][2] is None
    called.clear()
    r=client.post('/bookings/new',data={
       '_csrf':token,'asset_id':'1','start_time':'2026-12-20T10:00',
       'end_time':'2026-12-20T09:00'})
    assert r.status_code==200 and 'kết thúc phải sau' in r.get_data(as_text=True)
    assert not called


def test_operator_dispense_calls_procedure_once_and_redirects_to_stock(client,monkeypatch):
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    from webapp import db
    old_one=db.fetch_one
    monkeypatch.setattr(db,'fetch_one',lambda sql,params=(): {'expiry_date':__import__('datetime').date(2099,1,1),'stock_qty':100} if sql.startswith('SELECT expiry_date,stock_qty') else old_one(sql,params))
    invoked=[]
    monkeypatch.setattr(db,'procedure',lambda name,args,out: invoked.append((name,args,out)) or 999)
    with client.session_transaction() as s:token=s['_csrf']
    r=client.post('/dispenses/new',data={
       '_csrf':token,'asset_id':'20','personnel_id':'6','project_id':'',
       'quantity':'0.125','purpose':'Thử cấp phát'},follow_redirects=False)
    assert r.status_code==302
    assert '/chemicals/20' in r.headers['Location']
    assert invoked[0][0]=='sp_dispense_chemical' and len(invoked)==1
    assert str(invoked[0][1][3])=='0.125'
    assert invoked[0][1][1]==6


def test_favicon_does_not_invalidate_credential_form(client):
    page=client.get('/login')
    assert page.status_code==200
    with client.session_transaction() as sess:
        original=sess['_csrf']
    assert client.get('/favicon.ico').status_code==204
    with client.session_transaction() as sess:
        assert sess['_csrf']==original
    response=client.post('/login',data={'_csrf':original,'identifier':'sv001@gmail.com','password':'demo6'})
    assert response.status_code==302 and '/dashboard' in response.headers['Location']


def test_two_tab_and_anonymous_unknown_url_preserve_login_csrf(client):
    assert client.get('/login').status_code==200
    with client.session_transaction() as sess: initial=sess['_csrf']
    assert client.get('/login').status_code==200  # second browser tab
    assert client.get('/not-a-real-file.css').status_code==404
    assert client.get('/reports').status_code==302  # guest tries protected link
    with client.session_transaction() as sess: assert sess['_csrf']==initial
    assert client.post('/login',data={'_csrf':initial,'identifier':'gv001@gmail.com',
                                     'password':'demo7'}).status_code==302


def test_expiring_today_is_in_unexpired_chemical_filter(client,monkeypatch):
    assert login(client).status_code==302
    from webapp import db
    observed=[]
    monkeypatch.setattr(db,'scalar',lambda sql,params=(): observed.append(sql) or 0)
    assert client.get('/chemicals?expiry=valid').status_code==200
    assert observed and 'c.expiry_date>=CURRENT_DATE()' in observed[-1]
    assert 'c.expiry_date>CURRENT_DATE()' not in observed[-1]


def test_invalid_and_maximum_day_filters(client):
    assert login(client).status_code==302
    assert client.get('/bookings?from=2026-12-31&to=2026-12-01').status_code==400
    assert client.get('/bookings?from=9999-12-31&to=9999-12-31').status_code==200
    assert client.get('/dispenses?from=9999-12-31&to=9999-12-31').status_code==200


def test_read_only_previews_and_role_guards(client,monkeypatch):
    assert login(client).status_code==302
    from webapp import db
    calls=[]
    old_one=db.fetch_one
    def fake_preview_one(sql,params=()):
        calls.append((sql,params))
        if 'FROM equipment e' in sql:
            return {'asset_id':1,'asset_name':'Máy test','status':'AVAILABLE'}
        return old_one(sql,params)
    monkeypatch.setattr(db,'fetch_one',fake_preview_one)
    r=client.get('/bookings/preview?asset_id=1')
    assert r.status_code==200 and r.json['selected'] is True
    assert r.json['asset_name']=='Máy test'
    assert client.get('/dispenses/preview?asset_id=20').status_code==403
    assert all('UPDATE ' not in query and 'INSERT ' not in query for query,_ in calls)


def test_operator_dispense_preview_is_read_only(client,monkeypatch):
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    from webapp import db
    old_one=db.fetch_one
    def preview_one(sql,params=()):
        if 'FROM chemical_material c' in sql:
            return {'asset_id':20,'asset_name':'Hóa chất kiểm thử','status':'AVAILABLE',
                'hazard_level':5,'stock_qty':10,'unit':'ml','expiry_date':__import__('datetime').date(2027,12,31),
                'expired':False}
        if 'AS max_valid_level FROM personnel p' in sql:
            return {'full_name':'Người nhận thử','max_valid_level':4}
        return old_one(sql,params)
    monkeypatch.setattr(db,'fetch_one',preview_one)
    r=client.get('/dispenses/preview?asset_id=20&personnel_id=6')
    assert r.status_code==200 and r.json['selected'] is True
    assert r.json['has_recipient'] is True and r.json['certificate_eligible'] is False
    assert r.json['unit']=='ml'
    assert client.get('/dispenses/preview?asset_id=abc').status_code==400


def test_operator_uses_email_not_student_identifier(client):
    assert login(client,'SV001','demo1').status_code==200
    assert client.get('/reports').status_code==302
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    assert client.get('/reports').status_code==200


def test_member_requires_email_instead_of_student_identifier(client):
    assert login(client,'sV006','demo6').status_code==200
    assert client.get('/profile').status_code==302
    assert login(client,'SV001@GMAIL.COM','demo6').status_code==302
    assert client.get('/profile').status_code==200
    assert client.get('/reports').status_code==403


def test_old_operator_session_requires_email_login_again(client):
    with client.session_transaction() as sess:
        sess['personnel_id']=1
    assert client.get('/reports').status_code==302
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    assert client.get('/reports').status_code==200


def test_expired_chemical_is_rejected_before_procedure(client, monkeypatch):
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    from webapp import db
    old_one=db.fetch_one
    monkeypatch.setattr(db,'fetch_one',lambda sql,params=(): {'expiry_date':__import__('datetime').date(2000,1,1),'stock_qty':100} if sql.startswith('SELECT expiry_date,stock_qty') else old_one(sql,params))
    calls=[]
    monkeypatch.setattr(db,'procedure',lambda *a,**k:calls.append(a))
    with client.session_transaction() as s: token=s['_csrf']
    r=client.post('/dispenses/new',data={'_csrf':token,'asset_id':'22','personnel_id':'6','project_id':'','quantity':'1','purpose':'test'})
    assert r.status_code==200 and 'Hóa chất đã hết hạn' in r.get_data(as_text=True)
    assert calls==[]


def test_receipt_is_operator_only_and_requires_current_lot(client,monkeypatch):
    assert login(client).status_code==302
    assert client.get('/chemicals/new').status_code==403
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    from webapp import db
    calls=[]
    monkeypatch.setattr(db,'procedure',lambda *a,**k:calls.append(a) or 123)
    with client.session_transaction() as s: token=s['_csrf']
    data={'_csrf':token,'name':'Lo moi','room':'2','hazard':'1','unit':'g','stock':'12.5','concentration':'','expiry':'2000-01-01'}
    assert client.post('/chemicals/new',data=data).status_code==200
    assert calls==[]
    data['expiry']='2099-01-01'
    assert client.post('/chemicals/new',data=data).status_code==302
    assert len(calls)==1 and calls[0][0]=='sp_create_chemical'


def test_chemical_tabs_group_only_matching_expiry_and_units(client,monkeypatch):
    assert login(client).status_code==302
    from webapp import db
    captured=[]
    monkeypatch.setattr(db,'scalar',lambda sql,params=():captured.append(sql) or 0)
    r=client.get('/chemicals')
    assert r.status_code==200
    assert 'Còn hạn' in r.get_data(as_text=True) and 'Hết hạn' in r.get_data(as_text=True)
    assert 'c.expiry_date>=CURRENT_DATE()' in captured[-1]
    assert 'GROUP BY a.asset_name,c.unit,c.hazard_level,c.concentration' in captured[-1]
    assert client.get('/chemicals?expiry=expired').status_code==200
    assert 'c.expiry_date<CURRENT_DATE()' in captured[-1]


def test_member_lot_dates_are_scoped_to_own_dispenses(client,monkeypatch):
    assert login(client).status_code==302
    from webapp import db
    old_one=db.fetch_one
    monkeypatch.setattr(db,'fetch_one',lambda sql,params=():{'asset_name':'NaCl','unit':'g','concentration':None,'hazard_level':1} if 'SELECT a.asset_name,c.unit,c.concentration' in sql else old_one(sql,params))
    captured=[]
    old_all=db.fetch_all
    def capture_lots(sql,params=()):
        if 'AS last_dispense' in sql:
            captured.append((sql,params));return []
        return old_all(sql,params)
    monkeypatch.setattr(db,'fetch_all',capture_lots)
    assert client.get('/chemicals/22/lots?expiry=expired').status_code==200
    sql,params=captured[-1]
    assert 'AND d.personnel_id=%s' in sql and params[0]==6
    assert 'c.expiry_date<CURRENT_DATE()' in sql


def test_quick_receipt_reuses_server_profile_and_redirects_to_new_lot(client,monkeypatch):
    assert login(client,'dh001@gmail.com','demo1').status_code==302
    from webapp import db
    old_one=db.fetch_one
    monkeypatch.setattr(db,'fetch_one',lambda sql,params=():{'asset_name':'NaCl','room_id':5,'room_name':'Lab 5','unit':'g','concentration':None,'hazard_level':1} if 'SELECT a.asset_name,a.room_id,r.room_name' in sql else old_one(sql,params))
    calls=[]
    monkeypatch.setattr(db,'procedure',lambda name,args,out:calls.append((name,args,out)) or 99)
    assert client.get('/chemicals/22/replenish').status_code==200
    with client.session_transaction() as session:token=session['_csrf']
    fields={'_csrf':token,'unit':'g','quantity':'12.5','expiry':'2099-01-01','received_on':'2026-01-01','room_id':'999','hazard':'0'}
    r=client.post('/chemicals/22/replenish',data=fields)
    assert r.status_code==302 and '/chemicals/99/lots?expiry=valid' in r.location
    assert calls[0][0]=='sp_receive_chemical' and calls[0][1][0]==22 and calls[0][1][-1]==1
    fields['expiry']='2000-01-01'
    assert client.post('/chemicals/22/replenish',data=fields).status_code==200
    assert len(calls)==1


def test_quick_receipt_denies_members(client):
    assert login(client).status_code==302
    assert client.get('/chemicals/22/replenish').status_code==403


def test_booking_rejects_past_and_off_grid_before_db(client,monkeypatch):
    from datetime import datetime,timedelta,timezone
    from webapp import db
    assert login(client).status_code==302
    calls=[]
    monkeypatch.setattr(db,'procedure',lambda *a,**k:calls.append(a) or 77)
    with client.session_transaction() as session:token=session['_csrf']
    now=datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
    def submit(start,end):
        return client.post('/bookings/new',data={'_csrf':token,'asset_id':'1','project_id':'','start_time':start.strftime('%Y-%m-%dT%H:%M'),'end_time':end.strftime('%Y-%m-%dT%H:%M'),'purpose':'time grid test'})
    past=(now-timedelta(days=1)).replace(hour=9,minute=0)
    assert submit(past,past+timedelta(hours=1)).status_code==200
    future=(now+timedelta(days=2)).replace(hour=9,minute=17)
    assert submit(future,future+timedelta(hours=1)).status_code==200
    assert calls==[]
    start=future.replace(minute=30)
    assert submit(start,start+timedelta(minutes=15)).status_code==302
    assert len(calls)==1
    html=client.get('/bookings/new').get_data(as_text=True)
    assert 'name="start_time_minute"' in html and 'data-booking-time-grid' in html
    assert 'value="45"' in html and 'type="datetime-local"' not in html


def test_admin_booking_tabs_and_latest_request_order(client,monkeypatch):
    from webapp import db
    old_one=db.fetch_one
    monkeypatch.setattr(db,'fetch_one',lambda sql,params=():{'operator_id':1,'email':'dh001@gmail.com','display_name':'Admin','is_active':True} if 'FROM app_operator_account WHERE operator_id=' in sql else old_one(sql,params))
    with client.session_transaction() as session:session['operator_account_id']=1
    captured=[];old_all=db.fetch_all
    def capture(sql,params=()):
        if 'p.full_name AS booked_by' in sql:captured.append(sql)
        return old_all(sql,params)
    monkeypatch.setattr(db,'fetch_all',capture)
    r=client.get('/bookings?booking_status=PENDING')
    assert r.status_code==200 and 'Chưa duyệt' in r.get_data(as_text=True)
    assert 'Đã duyệt' in r.get_data(as_text=True)
    assert 'ORDER BY b.booking_id DESC' in captured[-1]


def test_split_booking_controls_preserve_45_minutes_and_date(client,monkeypatch):
    from webapp import db
    assert login(client).status_code==302
    calls=[]
    monkeypatch.setattr(db,'procedure',lambda name,args,out:calls.append(args) or 99)
    with client.session_transaction() as session:token=session['_csrf']
    fields={'_csrf':token,'asset_id':'1','project_id':'','purpose':'45 minute regression',
       'start_time':'2099-04-15T04:04','end_time':'2099-04-15T04:04',
       'start_time_date':'2099-04-15','start_time_hour':'04','start_time_minute':'45',
       'end_time_date':'2099-04-15','end_time_hour':'05','end_time_minute':'00'}
    assert client.post('/bookings/new',data=fields).status_code==302
    assert calls[0][3].isoformat()=='2099-04-15T04:45:00'
    assert calls[0][4].isoformat()=='2099-04-15T05:00:00'
    fields['start_time_minute']='04'
    assert client.post('/bookings/new',data=fields).status_code==200
    assert len(calls)==1


def test_shared_schedule_clips_midnight_and_omits_personal_details(client,monkeypatch):
    from webapp import db
    from datetime import datetime
    assert login(client).status_code==302
    old_all=db.fetch_all;queries=[]
    def data(sql,params=()):
        if 'SELECT e.asset_id,a.asset_name,a.status,r.room_name' in sql:
            return [{'asset_id':1,'asset_name':'Máy kiểm thử','status':'AVAILABLE','room_name':'Lab A'}]
        if 'SELECT b.asset_id,b.start_time,b.end_time,b.booking_status' in sql:
            queries.append((sql,params))
            return [{'asset_id':1,'start_time':datetime(2099,3,9,23),'end_time':datetime(2099,3,10,1),'booking_status':'APPROVED'},
                    {'asset_id':1,'start_time':datetime(2099,3,10,23,30),'end_time':datetime(2099,3,11,1),'booking_status':'PENDING'}]
        return old_all(sql,params)
    monkeypatch.setattr(db,'fetch_all',data)
    r=client.get('/equipment/schedule?day=2099-03-10')
    html=r.get_data(as_text=True)
    assert r.status_code==200 and '00:00–01:00' in html and '23:30–24:00' in html
    assert 'Chờ duyệt' in html and 'Đã duyệt' in html and 'data-schedule-book' in html
    sql,params=queries[-1]
    assert "b.booking_status IN ('PENDING','APPROVED')" in sql
    assert 'personnel_id' not in sql and 'purpose' not in sql
    assert params==(datetime(2099,3,11),datetime(2099,3,10))
    assert client.get('/equipment/schedule?day=not-a-date').status_code==400


def test_admin_shared_schedule_does_not_offer_personal_booking(client,monkeypatch):
    from webapp import db
    old_one=db.fetch_one
    monkeypatch.setattr(db,'fetch_one',lambda sql,params=():{'operator_id':1,'email':'dh001@gmail.com','display_name':'Admin','is_active':True} if 'FROM app_operator_account WHERE operator_id=' in sql else old_one(sql,params))
    with client.session_transaction() as session:session['operator_account_id']=1
    r=client.get('/equipment/schedule?day=2099-03-10')
    assert r.status_code==200 and 'data-schedule-book' not in r.get_data(as_text=True)


def test_schedule_shortcut_prefills_booking_time(client):
    assert login(client).status_code==302
    html=client.get('/bookings/new?asset_id=1&start_time=2099-03-10T14:45&end_time=2099-03-10T15:45').get_data(as_text=True)
    assert 'value="2099-03-10T14:45"' in html and 'value="2099-03-10T15:45"' in html


@pytest.mark.parametrize('with_proof',[False,True])
def test_certificate_evidence_is_optional_without_skipping_approval(client,monkeypatch,tmp_path,with_proof):
    from io import BytesIO
    from webapp import db
    assert login(client).status_code==302
    old_one=db.fetch_one
    def cert_one(sql,params=()):
        if sql.startswith('SELECT cert_id FROM safety_certificate'):return {'cert_id':1}
        if sql.startswith('SELECT personnel_id,proof_file FROM certificate_update_request'):return {'personnel_id':6,'proof_file':None}
        return old_one(sql,params)
    monkeypatch.setattr(db,'fetch_one',cert_one)
    captured=[]
    monkeypatch.setattr(db,'insert',lambda sql,params:captured.append((sql,params)) or 99)
    client.application.config['CERTIFICATE_STORAGE']=str(tmp_path/'proofs')
    with client.session_transaction() as session:token=session['_csrf']
    fields={'_csrf':token,'cert_id':'1','issue_date':'2020-01-01','expiry_date':'2099-01-01'}
    if with_proof:fields['proof']=(BytesIO(b'%PDF-1.4\nevidence'),'proof.pdf')
    response=client.post('/certificates',data=fields)
    assert response.status_code==302 and len(captured)==1
    assert captured[0][1][0]==6
    assert bool(captured[0][1][-1])==with_proof
    assert ('status' not in captured[0][0])  # PENDING database default, no automatic approval.
    assert (tmp_path/'proofs').exists()==with_proof
    assert client.get('/certificates/99/proof').status_code==404
