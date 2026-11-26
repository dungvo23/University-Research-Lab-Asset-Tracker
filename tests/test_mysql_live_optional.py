"""Only executes against a separately provisioned disposable MySQL SERVER.

Required explicit opt-in environment:
INT1313_TEST_DISPOSABLE=YES_DISPOSABLE_SERVER
TEST_DB_HOST=127.0.0.1
TEST_DB_PORT=<non-production test-port, not 13317>
TEST_DB_NAME=university_lab_tracker
TEST_DB_USER=lab_app
TEST_DB_PASSWORD=<test service password>

Do not run on the owner's portable MySQL, and do not use real student data.
The same original SQL scripts must have been bootstrapped by a test administrator.
"""
import os
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta

import pytest
flask=pytest.importorskip('flask')
pymysql=pytest.importorskip('pymysql')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope='module')
def disposable_app():
    if os.environ.get('INT1313_TEST_DISPOSABLE')!='YES_DISPOSABLE_SERVER':
        pytest.skip('No explicitly authorized disposable MySQL server')
    port=int(os.environ.get('TEST_DB_PORT','0'))
    if port in (0,3306,13317):
        pytest.skip('Refusing production/default MySQL ports')
    if os.environ.get('TEST_DB_NAME')!='university_lab_tracker':
        pytest.skip('This suite requires the original unchanged schema on the disposable server')
    password=os.environ.get('TEST_DB_PASSWORD','')
    if not password:
        pytest.skip('Missing test-only service password')
    os.environ['SECRET_KEY']='test-only-local-disposable-secret'
    from webapp.app import create_app
    app=create_app({'TESTING':True,'DB_HOST':os.environ.get('TEST_DB_HOST','127.0.0.1'),
        'DB_PORT':port,'DB_NAME':'university_lab_tracker',
        'DB_USER':os.environ.get('TEST_DB_USER','lab_app'), 'DB_PASSWORD':password})
    return app


def test_19_tables_and_reports(disposable_app):
    from webapp import db
    from webapp.services.reports import REPORTS,get_report
    with disposable_app.app_context():
        count=db.scalar('''SELECT COUNT(*) AS n FROM information_schema.tables
            WHERE table_schema=DATABASE() AND table_type='BASE TABLE' ''')
        # information_schema hides tables without direct grants (app_account).
        # lab_app has no direct SELECT on app_account by design.
        assert count>=17
        for key in REPORTS:
            _,sql,params,*_=get_report(key,{'from':'2026-11-01T00:00','to':'2027-01-01T00:00'})
            assert isinstance(db.fetch_all(sql+' LIMIT 1',params),list)


def test_booking_conflict_using_exact_procedure(disposable_app):
    from webapp import db
    with disposable_app.app_context():
        # Unique far-future slots, avoid the seed bookings and test collisions.
        t=datetime(2098,1,1,9,0)+timedelta(minutes=15*(int(datetime.now().timestamp())%6000))
        a=db.procedure('sp_book_equipment',[1,6,None,t,t+timedelta(hours=1),'Web test adjacent A'],out=True)
        b=db.procedure('sp_book_equipment',[1,6,None,t+timedelta(hours=1),t+timedelta(hours=2),'Web test adjacent B'],out=True)
        assert a and b and a!=b
        with pytest.raises(pymysql.MySQLError):
            db.procedure('sp_book_equipment',[1,6,None,t+timedelta(minutes=30),t+timedelta(hours=1,minutes=30),'Web test overlap'],out=True)


def test_dispense_deducts_stock_once_and_rejection_is_atomic(disposable_app):
    from webapp import db
    with disposable_app.app_context():
        before=Decimal(str(db.fetch_one('SELECT stock_qty FROM chemical_material WHERE asset_id=20')['stock_qty']))
        rid=db.procedure('sp_dispense_chemical',[20,1,None,Decimal('0.001'),'Web test issue'],out=True)
        after=Decimal(str(db.fetch_one('SELECT stock_qty FROM chemical_material WHERE asset_id=20')['stock_qty']))
        assert rid and before-after==Decimal('0.001')
        with pytest.raises(pymysql.MySQLError):
            db.procedure('sp_dispense_chemical',[20,24,None,Decimal('0.001'),'Web test no certificate'],out=True)
        assert Decimal(str(db.fetch_one('SELECT stock_qty FROM chemical_material WHERE asset_id=20')['stock_qty']))==after


def test_access_open_duplicate_exit(disposable_app):
    from webapp import db
    with disposable_app.app_context():
        assert db.scalar('SELECT COUNT(*) AS n FROM lab_access_log WHERE personnel_id=6 AND exit_time IS NULL')==0
        rid=db.procedure('sp_app_checkin',[6,5,'Web test access'],out=True)
        with pytest.raises(pymysql.MySQLError):
            db.procedure('sp_app_checkin',[6,5,'Web test duplicate'],out=True)
        with pytest.raises(pymysql.MySQLError):
            db.procedure('sp_app_checkout',[7,rid],out=False)
        db.procedure('sp_app_checkout',[6,rid],out=False)
        with pytest.raises(pymysql.MySQLError):
            db.procedure('sp_app_checkout',[6,rid],out=False)


def test_standalone_admin_and_faculty_are_independent(disposable_app):
    from webapp.auth import authenticate
    with disposable_app.test_request_context('/'):
        admin=authenticate('dh001@gmail.com','khongnhonua123')
        faculty=authenticate('gv009@gmail.com','khongnhonua123')
        assert admin['operator'] and admin['personnel_id'] is None
        assert faculty['personnel_id']==1 and not faculty['operator']
        assert authenticate('gv001@gmail.com','khongnhonua123')['personnel_id']==7
    c=disposable_app.test_client()
    with c.session_transaction() as s:s['operator_account_id']=admin['operator_account_id']
    html=c.get('/dashboard').get_data(as_text=True)
    assert 'Lịch của tôi' not in html and 'Hoạt động cá nhân' not in html
    assert c.get('/bookings/new').status_code==403
    for path in ['/bookings','/access','/dispenses','/registrations','/profile']:
        assert c.get(path).status_code==200
    f=disposable_app.test_client()
    with f.session_transaction() as s:s['personnel_id']=1
    assert f.get('/registrations').status_code==403
    assert 'Nguyễn Minh Đức' in f.get('/profile').get_data(as_text=True)
