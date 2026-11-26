from datetime import datetime,timedelta
from test_mysql_live_optional import disposable_app


def client_for(app,pid=None,admin=False):
    c=app.test_client()
    with c.session_transaction() as s:
        if admin:s['operator_account_id']=1
        else:s['personnel_id']=pid
    return c


def test_unicode_personnel_search_works_on_actual_ascii_code_column(disposable_app):
    admin=client_for(disposable_app,admin=True)
    for query in ['Nguyễn','Đức','Trần','GV001','ctv001']:
        r=admin.get('/personnel',query_string={'q':query})
        assert r.status_code==200,(query,r.status_code)
    assert 'Nguyễn Minh Đức' in admin.get('/personnel?q=Đức').get_data(as_text=True)


def test_attention_is_private_and_seen_results_stay_seen(disposable_app):
    from webapp import db
    app=disposable_app
    admin=client_for(app,admin=True);member=client_for(app,pid=6);other=client_for(app,pid=7)
    admin_before=admin.get('/notifications/status').json['counts']['bookings']
    member_before=member.get('/notifications/status').json['counts']['bookings']
    other_before=other.get('/notifications/status').json['counts']['bookings']
    t=datetime(2094,1,1,9)
    with app.app_context():
        bid=db.procedure('sp_book_equipment',[4,6,None,t,t+timedelta(hours=1),'Notification test'],out=True)
    assert admin.get('/notifications/status').json['counts']['bookings']==admin_before+1
    assert member.get('/notifications/status').json['counts']['bookings']==member_before
    with app.app_context():db.procedure('sp_review_booking',[bid,1,True,None],out=False)
    assert admin.get('/notifications/status').json['counts']['bookings']==admin_before
    assert member.get('/notifications/status').json['counts']['bookings']==member_before+1
    assert other.get('/notifications/status').json['counts']['bookings']==other_before
    # Viewing another person's page cannot clear the owner's result.
    other.get('/bookings')
    assert member.get('/notifications/status').json['counts']['bookings']==member_before+1
    member.get('/bookings?booking_status=PENDING')
    assert member.get('/notifications/status').json['counts']['bookings']==member_before+1
    assert member.get('/bookings').status_code==200
    with app.app_context():
        assert db.scalar("SELECT COUNT(*) AS n FROM notification_seen WHERE personnel_id=6 AND notification_kind='BOOKING' AND item_id=%s",(bid,))==1
    # Session/browser replacement does not reset persistent read receipts.
    fresh=client_for(app,pid=6)
    assert fresh.get('/notifications/status').json['counts']['bookings']<=member_before
