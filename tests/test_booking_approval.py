"""Booking lifecycle and concurrent reservations on disposable MySQL only."""
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from test_mysql_live_optional import disposable_app


def test_pending_reserves_rejection_releases_and_approval_is_final(disposable_app):
    from webapp import db
    from pymysql import MySQLError
    app=disposable_app
    t=datetime(2097,3,10,9)
    with app.app_context():
        bid=db.procedure('sp_book_equipment',[1,6,None,t,t+timedelta(hours=1),'Approval lifecycle'],out=True)
        assert db.fetch_one('SELECT booking_status FROM equipment_booking WHERE booking_id=%s',(bid,))['booking_status']=='PENDING'
        with pytest.raises(MySQLError):db.procedure('sp_book_equipment',[1,7,None,t,t+timedelta(hours=1),'Conflicting pending'],out=True)
        admin=app.test_client()
        with admin.session_transaction() as session:session['operator_account_id']=1
        response=admin.get('/bookings?booking_status=PENDING')
        assert response.status_code==200 and f'/bookings/{bid}/review' in response.get_data(as_text=True)
        with admin.session_transaction() as session:token=session['_csrf']
        assert admin.post(f'/bookings/{bid}/review',data={'_csrf':token,'decision':'reject','note':'Không phù hợp'}).status_code==302
        second=db.procedure('sp_book_equipment',[1,7,None,t,t+timedelta(hours=1),'Released slot'],out=True)
        db.procedure('sp_review_booking',[second,1,True,None],out=False)
        row=db.fetch_one('SELECT booking_status,reviewed_by_operator,reviewed_at FROM equipment_booking WHERE booking_id=%s',(second,))
        assert row['booking_status']=='APPROVED' and row['reviewed_by_operator']==1 and row['reviewed_at']
        with pytest.raises(MySQLError):db.procedure('sp_review_booking',[second,1,False,'Repeat review'],out=False)
        with pytest.raises(MySQLError):db.procedure('sp_book_equipment',[1,6,None,t,t+timedelta(hours=1),'Conflicting approved'],out=True)
    member=app.test_client()
    with member.session_transaction() as s:s['personnel_id']=6
    member.get('/bookings')
    with member.session_transaction() as s:token=s['_csrf']
    assert member.post(f'/bookings/{second}/review',data={'_csrf':token,'decision':'approve'}).status_code==403


def test_simultaneous_requests_cannot_reserve_same_slot(disposable_app):
    from webapp import db
    from pymysql import MySQLError
    app=disposable_app;barrier=Barrier(2);t=datetime(2097,4,10,9)
    def book(pid):
        with app.app_context():
            barrier.wait(timeout=10)
            try:return db.procedure('sp_book_equipment',[2,pid,None,t,t+timedelta(hours=1),'Concurrent reservation'],out=True)
            except MySQLError:return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(book,pid) for pid in [6,7]]
        results=[future.result(timeout=30) for future in futures]
    assert sum(value is not None for value in results)==1
    with app.app_context():
        assert db.scalar('SELECT COUNT(*) AS n FROM equipment_booking WHERE asset_id=2 AND start_time=%s',(t,))==1


def test_mysql_rejects_past_off_grid_and_seconds(disposable_app):
    from webapp import db
    from pymysql import MySQLError
    with disposable_app.app_context():
        count=db.scalar('SELECT COUNT(*) AS n FROM equipment_booking')
        for start,end in [(datetime(2000,1,1,9),datetime(2000,1,1,10)),
                          (datetime(2096,1,1,9,17),datetime(2096,1,1,10)),
                          (datetime(2096,1,1,9,15,1),datetime(2096,1,1,10))]:
            with pytest.raises(MySQLError):db.procedure('sp_book_equipment',[3,6,None,start,end,'invalid time'],out=True)
        assert db.scalar('SELECT COUNT(*) AS n FROM equipment_booking')==count
        bid=db.procedure('sp_book_equipment',[3,6,None,datetime(2096,1,1,9,15),datetime(2096,1,1,9,30),'valid quarter'],out=True)
        assert bid
