"""No Flask/MySQL needed: source, validation, SQL and Jinja checks."""
import ast
import hashlib
from pathlib import Path
import re
import sys
from types import SimpleNamespace
from datetime import datetime, date

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp.common import (InputError, choice, local_datetime, optional_day,
                           page_number, positive_id, present, quantity, date_window, inclusive_day_end)
from webapp.services.reports import REPORTS, get_report


@pytest.mark.parametrize('raw,expected', [('1',1),('002',None),('2147483647',2147483647)])
def test_id_rules(raw, expected):
    if expected is None:
        with pytest.raises(InputError): positive_id(raw)
    else:
        assert positive_id(raw)==expected


@pytest.mark.parametrize('raw', ['0','0.000','-1','2.1119','1e3','10,0','nan','9999999999',''])
def test_reject_invalid_quantity(raw):
    with pytest.raises(InputError): quantity(raw)


@pytest.mark.parametrize('raw', ['0.001','1','20.250','999999999.999'])
def test_valid_quantity_preserves_precision(raw):
    assert str(quantity(raw)) == raw


def test_local_datetime_and_date():
    assert local_datetime('2026-11-23T10:11').strftime('%Y-%m-%d %H:%M')=='2026-11-23 10:11'
    with pytest.raises(InputError): local_datetime('2026-02-30T14:00')
    assert optional_day('2026-11-23').year==2026
    with pytest.raises(InputError): optional_day('2026-13-01')
    assert page_number('500000')==100000
    assert present(None)=='—'
    assert present(datetime(2026,11,23,10,0))=='23/11/2026 10:00'


@pytest.mark.parametrize('key',list(REPORTS))
def test_each_report_sql_is_parameterized(key):
    title, sql, params, filter_kind, applied = get_report(key, {'from':'2026-11-01T00:00','to':'2026-12-01T00:00'})
    assert title and 'SELECT' in sql.upper()
    assert sql.count('%s') == len(params)
    assert not re.search(r'\b(?:DELETE|UPDATE|DROP|INSERT)\b',sql,re.I)
    assert ' ORDER BY ' in sql.upper()


def test_report_corrected_logic():
    assert len(REPORTS)==14
    assert 'SUM(pa.allocated_qty)' not in REPORTS['Q09'][1]
    assert 'm2.maint_date DESC,m2.maint_id DESC' in REPORTS['Q10'][1]
    assert 'b.start_time<%s AND b.end_time>%s' in REPORTS['Q04'][1]
    with pytest.raises(KeyError): get_report('Q99', {})
    with pytest.raises(InputError): get_report('Q04', {'from':'2026-12-01T10:00','to':'2026-12-01T09:00'})
    with pytest.raises(InputError): get_report('Q05', {'hazard':'6'})


def test_sql_sources_unchanged():
    manifest=(ROOT/'SQL_MANIFEST_SHA256.txt').read_text(encoding='utf-8')
    pairs=re.findall(r'([0-9a-f]{64})  (sql/[\w\d_.]+\.sql)',manifest)
    assert len(pairs)==9
    if not (ROOT/'sql').exists():
        pytest.skip('Bộ ZIP tích hợp không chứa SQL gốc; chạy sau khi ghép vào FINAL/sql')
    for expected,path in pairs:
        actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        assert actual==expected, path


def test_every_route_and_template_valid():
    app_tree=ast.parse((ROOT/'webapp/app.py').read_text(encoding='utf-8'))
    endpoints={n.name for n in ast.walk(app_tree) if isinstance(n,ast.FunctionDef)}|{'static'}
    env=Environment(loader=FileSystemLoader(str(ROOT/'webapp/templates')))
    for path in (ROOT/'webapp/templates').glob('*.html'):
        contents=path.read_text(encoding='utf-8')
        env.parse(contents)
        assert 'http://cdn' not in contents and 'https://cdn' not in contents
        assert 'password_hash' not in contents
        for endpoint in re.findall(r'url_for\([\'"]([\w_]+)[\'"]',contents):
            assert endpoint in endpoints, (path.name, endpoint)


def test_source_has_no_destructive_startup():
    s=(ROOT/'webapp/app.py').read_text(encoding='utf-8')
    assert 'DROP DATABASE' not in s
    assert 'CREATE TABLE' not in s
    assert 'DELETE FROM' not in s
    assert 'GRANT ALL' not in s
    assert 'sqlite3' not in s
    assert "'sp_dispense_chemical'" in s
    assert "'sp_book_equipment'" in s
    assert "'sp_app_checkin'" in s
    assert "'sp_app_checkout'" in s


def test_jinja_renders_all_common_pages_with_example_context_only():
    env=Environment(loader=FileSystemLoader(str(ROOT/'webapp/templates')),autoescape=True,undefined=StrictUndefined)
    env.filters['display']=present
    env.globals.update(url_for=lambda name,**args:'/'+name,csrf_token=lambda:'fixture-token',
                       get_flashed_messages=lambda **kwargs:[],page_url=lambda p:f'/p/{p}',
                       now_local=datetime.now)
    user={'full_name':'Nguyễn Văn A','personnel_id':1,'operator':True,'email':'abc@example.test','roles':{'OPERATOR'}}
    request=SimpleNamespace(endpoint='dashboard',path='/test',args={},form={},method='GET')
    g=SimpleNamespace(user=user)
    columns=[{'key':'asset_id','label':'Mã'},{'key':'asset_name','label':'Tên'}]
    rows=[{'asset_id':1,'asset_name':'Thiết bị thử','detail_url':'/equipment/1'}]
    standard={'g':g,'request':request,'title':'Trang thử','description':'Thông tin thử',
       'columns':columns,'rows':rows,'total':1,'page':1,'pages':1,'filters':[],
       'filter_values':{},'actions':[], 'fields':[], 'values':{},'submit':'Gửi',
       'error':None,'note':None,'back':None,'action':'/test','reservations':[],
       'eligibility':None, 'stats':{'Thiết bị':12},'own_booking_count':0,
       'own_visit':None,'cert_count':1,'upcoming':[],'operator_stats':{},'expiry':[],
       'properties':[('Mã',1)],'sections':[{'title':'Mục','columns':columns,'rows':rows,'empty':'Trống','note':None}],
       'grouped':[],'report_key':'Q01','filter_type':'','applied':{},'reports':REPORTS,
       'visit':None,'rooms':[],'preselected':'','all_history':False,'history_filters':[]}
    for template in ('dashboard.html','table.html','detail.html','form.html','operations.html',
                     'access.html','report_index.html','report_detail.html'):
        result=env.get_template(template).render(**standard)
        assert '<html lang="vi">' in result
        assert 'Trang thử' in result or template in ('access.html','report_index.html')
    guest=dict(standard)
    guest['g']=SimpleNamespace(user=None)
    assert 'Nhập email của bạn' in env.get_template('login.html').render(**guest)
    guest.update(code=503,message='Dữ liệu đang bảo trì')
    assert '503' in env.get_template('error.html').render(**guest)


@pytest.mark.parametrize('a,b,expected',[
    ('2026-12-01','2026-12-31',True),
    ('2026-12-31','2026-12-01',False),
    ('9999-12-31','9999-12-31',True),
])
def test_date_window_order_and_max_date(a,b,expected):
    if expected:
        first,last=date_window({'from':a,'to':b})
        assert (first.isoformat(),last.isoformat())==(a,b)
        assert inclusive_day_end(last).date()==last
        assert inclusive_day_end(last).time().microsecond==999999
    else:
        with pytest.raises(InputError): date_window({'from':a,'to':b})


def test_live_preview_templates_and_local_favicon():
    assert (ROOT/'webapp/static/favicon.svg').exists()
    assert 'url_for(\'static\', filename=\'favicon.svg\')' in (ROOT/'webapp/templates/base.html').read_text(encoding='utf-8')
    env=Environment(loader=FileSystemLoader(str(ROOT/'webapp/templates')),
                    autoescape=True,undefined=StrictUndefined)
    env.filters['display']=present
    env.globals.update(url_for=lambda name,**args:'/'+name,
                       csrf_token=lambda:'fixture-token',
                       get_flashed_messages=lambda **kw:[],
                       now_local=datetime.now)
    g=SimpleNamespace(user={'full_name':'Người thử','operator':True,
                            'personnel_id':1,'roles':{'OPERATOR'}})
    req=SimpleNamespace(endpoint='booking_new',path='/bookings/new',args={},method='GET')
    base={'g':g,'request':req,'title':'Đặt lịch','description':'Mô tả','fields':[],
          'values':{},'note':'', 'reservations':[], 'eligibility':None,
          'action':'/bookings/new','submit':'Lưu','back':None,'error':None}
    assert 'data-preview-kind="booking"' in env.get_template('form.html').render(**base)
    req.endpoint='dispense_new'
    assert 'data-preview-kind="dispense"' in env.get_template('form.html').render(**base)
    assert 'credentials: \'same-origin\'' in (ROOT/'webapp/static/js/app.js').read_text(encoding='utf-8')
