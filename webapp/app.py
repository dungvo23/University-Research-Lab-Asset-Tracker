"""INT1313 lab operations web UI; works with existing 19-table MySQL schema.

Windows entry point: python -m flask --app webapp/app.py run --host=127.0.0.1
No DDL, seed, or database administrator privilege is used by this module.
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import logging
import os

from dotenv import load_dotenv
from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from pymysql import MySQLError

from webapp import db
from webapp.auth import (authenticate, check_csrf, clear_failures, csrf_token,
                         current_user, login_required, operator_required,
                         rate_limited, record_failure)
from webapp.common import (InputError, choice, filters_page_url, limited_text, optional_day,
                           local_datetime, date_window, inclusive_day_end,
                           page_number, positive_id, present, quantity, safe_db_message)
from webapp.services.reports import REPORTS, get_report

PAGE_SIZE = 20
STATUS_CHOICES = ['AVAILABLE', 'IN_USE', 'MAINTENANCE', 'RETIRED']


def C(key, label):
    return {'key': key, 'label': label}


def F(name, label, kind='text', *, options=None, placeholder='', required=False, help=None, step=None, min_value=None):
    return {'name': name, 'label': label, 'kind': kind, 'options': options or [],
            'placeholder': placeholder, 'required': required, 'help': help, 'step':step, 'min_value':min_value}


def _rooms_options():
    return [(str(r['room_id']), r['room_name'] + ' · cấp ' + str(r['safety_category']))
            for r in db.fetch_all('SELECT room_id,room_name,safety_category FROM lab_room ORDER BY room_name')]


def _equipment_options():
    return [(str(r['asset_id']), f"{r['asset_name']} · {r['serial_number']} (#{r['asset_id']})")
            for r in db.fetch_all('''SELECT e.asset_id,a.asset_name,e.serial_number FROM equipment e
            JOIN lab_asset a ON a.asset_id=e.asset_id ORDER BY a.asset_name''')]


def _project_options():
    return [(str(r['project_id']), f"{r['project_name']} (#{r['project_id']})")
            for r in db.fetch_all('SELECT project_id,project_name FROM research_project ORDER BY project_id')]


def _chemical_options(usable=False):
    return [(str(r['asset_id']), f"{r['asset_name']} (#{r['asset_id']}) — {present(r['stock_qty'])} {r['unit']}, cấp {r['hazard_level']}")
            for r in db.fetch_all('''SELECT c.asset_id,a.asset_name,c.stock_qty,c.unit,c.hazard_level
            FROM chemical_material c JOIN lab_asset a ON a.asset_id=c.asset_id''' + (' WHERE c.expiry_date>=CURRENT_DATE() AND c.stock_qty>0' if usable else '') + ' ORDER BY a.asset_name')]


def _person_options():
    return [(str(r['personnel_id']), f"{r['full_name']} · {r['reference_code']} (#{r['personnel_id']})")
            for r in db.fetch_all('''SELECT p.personnel_id,p.full_name,
              COALESCE(s.student_code,f.faculty_code,t.staff_code,p.email) AS reference_code
              FROM personnel p LEFT JOIN student s ON s.personnel_id=p.personnel_id
              LEFT JOIN faculty f ON f.personnel_id=p.personnel_id
              LEFT JOIN lab_technician t ON t.personnel_id=p.personnel_id
              ORDER BY p.full_name,p.personnel_id''')]


def _technician_options():
    return [(str(r['personnel_id']), f"{r['full_name']} · {r['staff_code']}")
            for r in db.fetch_all('''SELECT t.personnel_id,p.full_name,t.staff_code FROM lab_technician t
            JOIN personnel p ON p.personnel_id=t.personnel_id ORDER BY p.full_name''')]


def _assets_options():
    # Third option item supplies a local (read-only) unit preview for chemicals.
    return [(str(r['asset_id']),
             f"{r['asset_name']} ({present(r['asset_type'])}"
             + (f" · {r['unit']}" if r['unit'] else '') + f"; #{r['asset_id']})",
             r['unit'] or '') for r in db.fetch_all('''SELECT a.asset_id,a.asset_name,
             a.asset_type,c.unit FROM lab_asset a
             LEFT JOIN chemical_material c ON c.asset_id=a.asset_id ORDER BY a.asset_name''')]


def _value_map(fields, defaults=None):
    values = (defaults or {}).copy()
    if request.method == 'POST':
        for f in fields:
            values[f['name']] = request.form.get(f['name'], '')
    return values


def _render_form(title, description, fields, *, action=None, submit='Lưu thông tin',
                 values=None, error=None, note=None, back=None, reservations=None, eligibility=None):
    return render_template('form.html', title=title, description=description, fields=fields,
        values=values or {}, error=error, action=action or request.path, submit=submit,
        note=note, back=back, reservations=reservations or [], eligibility=eligibility)


def _handle_write(callable_fn, success_label, redirect_endpoint, redirect_kwargs=None):
    try:
        new_id = callable_fn()
    except InputError as exc:
        return None, str(exc)
    except db.DatabaseUnavailable:
        raise
    except MySQLError as exc:
        logging.getLogger(__name__).warning('Rejected database write, code=%s', exc.args[0] if exc.args else '?')
        return None, safe_db_message(exc)
    except RuntimeError:
        logging.getLogger(__name__).exception('Procedure return invariant failed')
        return None, 'Không xác nhận được kết quả thao tác. Hãy kiểm tra lịch sử trước khi gửi lại.'
    flash(success_label.format(id=new_id), 'success')
    return redirect(url_for(redirect_endpoint, **(redirect_kwargs or {}))), None


def _listing(title, desc, from_sql, params, select_sql, order_sql, columns, *, filters=None,
             actions=None, decorate=None):
    page = page_number(request.args.get('page'))
    total = int(db.scalar('SELECT COUNT(*) AS n ' + from_sql, params))
    rows = db.fetch_all(select_sql + ' ' + from_sql + ' ' + order_sql + ' LIMIT %s OFFSET %s',
                        (*params, PAGE_SIZE, (page - 1) * PAGE_SIZE))
    if decorate:
        for row in rows:
            decorate(row)
    if request.endpoint=='bookings' and not g.user.get('operator_account_id'):
        from webapp.notifications import seen
        seen('BOOKING',[row['booking_id'] for row in rows if row.get('booking_status') in ('APPROVED','REJECTED')])
    return render_template('table.html', title=title, description=desc, columns=columns,
        rows=rows, total=total, page=page, pages=max(1, (total + PAGE_SIZE - 1)//PAGE_SIZE),
        filters=filters or [], actions=actions or [], filter_values=request.args,
        listing=True)


def _detail(title, desc, properties, *, sections=None, actions=None, note=None):
    return render_template('detail.html', title=title, description=desc, properties=properties,
                           sections=sections or [], actions=actions or [], note=note)


def _section(title, cols, rows, empty='Chưa có dữ liệu.', note=None):
    return {'title': title, 'columns': cols, 'rows': rows, 'empty': empty, 'note': note}


def _get_or_404(sql, params):
    row = db.fetch_one(sql, params)
    if row is None:
        abort(404)
    return row


def _try_filter_id(name):
    val = request.args.get(name, '').strip()
    return positive_id(val, name, optional=True)


def create_app(test_config=None):
    folder = Path(__file__).resolve().parent
    load_dotenv(folder / '.env', override=False)
    app = Flask(__name__, template_folder=str(folder / 'templates'), static_folder=str(folder / 'static'))
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY'), DB_HOST=os.environ.get('DB_HOST', '127.0.0.1'),
        DB_PORT=int(os.environ.get('DB_PORT', '13317')),
        DB_NAME=os.environ.get('DB_NAME', 'university_lab_tracker'),
        DB_USER=os.environ.get('DB_USER', 'lab_app'),
        DB_PASSWORD=os.environ.get('DB_PASSWORD', ''),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        MAX_CONTENT_LENGTH=5*1024*1024, TEMPLATES_AUTO_RELOAD=False,
    )
    if test_config:
        app.config.update(test_config)
    # Do not mint a hard-coded development secret in production.
    app.jinja_env.globals.update(csrf_token=csrf_token, page_url=filters_page_url,
                                 format_value=present, now_local=datetime.now)
    app.jinja_env.filters['display'] = present

    @app.context_processor
    def attention_badges():
        from webapp.notifications import counts
        try:return {'notification_counts':counts()}
        except (db.DatabaseUnavailable,MySQLError):return {'notification_counts':{}}

    @app.before_request
    def security_gate():
        g.user = None
        # Unknown routes and automatic browser icon requests must not invalidate an
        # anonymous login form: its CSRF token belongs to the same cookie session.
        if request.endpoint in ('static', 'health', 'favicon') or request.endpoint is None:
            return
        if not app.config.get('SECRET_KEY'):
            return render_template('error.html', code=503, title='Chưa cấu hình ứng dụng',
                message='Cần cấu hình SECRET_KEY trong webapp/.env trước khi sử dụng.'), 503
        if request.method == 'POST':
            check_csrf()
        if request.endpoint in ('login', 'health', 'registration.register', 'registration.submitted'):
            return
        g.user = current_user()
        if g.user is None:
            # Clear only a revoked authenticated identity. A guest visiting a
            # protected URL in another tab must retain the login form's CSRF.
            if session.get('personnel_id') is not None or session.get('operator_account_id') is not None:
                session.clear()
            return redirect(url_for('login'))

        if g.user and g.user.get('operator_account_id') and request.endpoint in ('booking_new','checkin','checkout','access_checkin','access_checkout'):
            abort(403,description='Tài khoản quản trị không thực hiện hoạt động cá nhân. Hãy đăng nhập tài khoản giảng viên hoặc thành viên.')
    @app.after_request
    def private_response(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Cache-Control'] = 'no-store, private'
        return response

    @app.errorhandler(db.DatabaseUnavailable)
    def no_database(error):
        if request.endpoint == 'health':
            return jsonify(ok=False, error='database_unavailable'), 503
        return render_template('error.html', code=503, title='Tạm thời không kết nối được',
                message='Máy chủ dữ liệu chưa sẵn sàng hoặc cấu hình kết nối chưa chính xác. Vui lòng liên hệ người quản trị.'), 503

    @app.errorhandler(MySQLError)
    def database_error(error):
        logging.getLogger(__name__).error('MySQL request failed; code=%s', error.args[0] if error.args else '?')
        return render_template('error.html', code=500, title='Không thể tải dữ liệu',
            message='Hệ thống gặp lỗi khi truy vấn dữ liệu. Vui lòng thử lại hoặc báo người phụ trách.'), 500

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def http_error(err):
        code = getattr(err, 'code', 500)
        descriptions = {400: 'Yêu cầu không hợp lệ hoặc phiên làm việc đã hết hạn.',
                        403: 'Tài khoản của bạn không có quyền xem hoặc thao tác tại đây.',
                        404: 'Không tìm thấy trang hoặc bản ghi yêu cầu.',
                        500: 'Có lỗi bất ngờ. Vui lòng thử lại.'}
        return render_template('error.html', code=code,
            title={400:'Yêu cầu không hợp lệ',403:'Không có quyền',404:'Không tìm thấy',500:'Lỗi hệ thống'}.get(code,'Lỗi'),
            message=descriptions.get(code,'Không thể xử lý yêu cầu.')), code

    @app.errorhandler(InputError)
    def invalid_input(err):
        return render_template('error.html', code=400, title='Bộ lọc không hợp lệ', message=str(err)), 400

    @app.get('/favicon.ico')
    def favicon():
        # Legacy browsers request this path even with an SVG rel=icon. Avoid
        # a redirect that could invalidate an anonymous CSRF cookie.
        return '', 204

    @app.route('/health')
    def health():
        if not app.config.get('SECRET_KEY'):
            return jsonify(ok=False, error='configuration_missing'), 503
        try:
            db.fetch_one('SELECT 1 AS ready')
        except (db.DatabaseUnavailable, MySQLError):
            return jsonify(ok=False, error='database_unavailable'), 503
        return jsonify(ok=True, database='connected'), 200

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            identifier = (request.form.get('identifier') or '').strip()
            password = request.form.get('password') or ''
            if not identifier or not password or len(identifier) > 160 or len(password) > 4096:
                error = 'Thông tin đăng nhập không hợp lệ.'
            elif rate_limited(identifier):
                error = 'Đã thử đăng nhập quá nhiều lần. Vui lòng thử lại sau 15 phút.'
            else:
                user = authenticate(identifier, password)
                if user is None:
                    record_failure(identifier)
                    error = 'Email hoặc mật khẩu không đúng, hoặc tài khoản không khả dụng.'
                else:
                    clear_failures(identifier)
                    session.clear()
                    if user.get('operator_account_id'):
                        session['operator_account_id']=user['operator_account_id']
                    else:
                        session['personnel_id'] = int(user['personnel_id'])
                    session['operator_email_login'] = bool(user['operator'])
                    session.permanent = True
                    return redirect(url_for('dashboard'))
        return render_template('login.html', title='Đăng nhập', error=error)

    @app.post('/logout')
    @login_required
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/')
    @app.route('/dashboard')
    @login_required
    def dashboard():
        pid = g.user['personnel_id']
        stats = {
            'Thiết bị': db.scalar('SELECT COUNT(*) AS n FROM equipment'),
            'Hóa chất': db.scalar('SELECT COUNT(*) AS n FROM chemical_material'),
            'Phòng thí nghiệm': db.scalar('SELECT COUNT(*) AS n FROM lab_room'),
            'Đề tài nghiên cứu': db.scalar('SELECT COUNT(*) AS n FROM research_project'),
        }
        own_booking_count = db.scalar('''SELECT COUNT(*) AS n FROM equipment_booking
            WHERE personnel_id=%s AND booking_status IN ('PENDING','APPROVED') AND end_time>=CURRENT_TIMESTAMP''', (pid,))
        own_visit = db.fetch_one('''SELECT l.access_id,l.entry_time,r.room_name FROM lab_access_log l
            JOIN lab_room r ON r.room_id=l.room_id
            WHERE l.personnel_id=%s AND l.exit_time IS NULL ORDER BY l.entry_time DESC LIMIT 1''', (pid,))
        cert_count = db.scalar('''SELECT COUNT(*) AS n FROM personnel_certificate
            WHERE personnel_id=%s AND issue_date<=CURRENT_DATE() AND expiry_date>=CURRENT_DATE()''', (pid,))
        upcoming = db.fetch_all('''SELECT b.booking_id,a.asset_name,r.room_name,b.start_time,b.end_time
            FROM equipment_booking b JOIN lab_asset a ON a.asset_id=b.asset_id
            JOIN lab_room r ON r.room_id=a.room_id
            WHERE b.personnel_id=%s AND b.booking_status IN ('PENDING','APPROVED') AND b.end_time>=CURRENT_TIMESTAMP
            ORDER BY b.start_time LIMIT 6''', (pid,))
        operator_stats = {}
        if g.user['operator']:
            operator_stats = {
                'Lượt vào phòng chưa kết thúc': db.scalar('SELECT COUNT(*) AS n FROM lab_access_log WHERE exit_time IS NULL'),
                'Lịch sắp tới (toàn hệ thống)': db.scalar("SELECT COUNT(*) AS n FROM equipment_booking WHERE booking_status IN ('PENDING','APPROVED') AND end_time>=CURRENT_TIMESTAMP"),
                'Hóa chất đã hết hạn': db.scalar('SELECT COUNT(*) AS n FROM chemical_material WHERE expiry_date<CURRENT_DATE()'),
                'Hóa chất tồn dưới 5 (theo đơn vị riêng)': db.scalar('SELECT COUNT(*) AS n FROM chemical_material WHERE stock_qty<5'),
            }
        expiry = db.fetch_all('''SELECT asset_id,asset_name,room_name,expiry_date,days_to_expiry,expiry_status
            FROM v_chemical_expiring_soon ORDER BY expiry_date LIMIT 6''') if g.user['operator'] else []
        return render_template('dashboard.html', title='Tổng quan', stats=stats,
            own_booking_count=own_booking_count, own_visit=own_visit,
            cert_count=cert_count, upcoming=upcoming, operator_stats=operator_stats, expiry=expiry)

    @app.get('/equipment')
    @login_required
    def equipment():
        search = request.args.get('q', '').strip()[:100]
        room = _try_filter_id('room')
        status = choice(request.args.get('status',''), STATUS_CHOICES, 'Trạng thái')
        conditions = ['1=1']
        params = []
        if search:
            conditions.append('(a.asset_name LIKE %s OR e.serial_number LIKE %s OR e.model LIKE %s)')
            params += [f'%{search}%'] * 3
        if room:
            conditions.append('a.room_id=%s'); params.append(room)
        if status:
            conditions.append('a.status=%s'); params.append(status)
        from_sql = '''FROM equipment e JOIN lab_asset a ON a.asset_id=e.asset_id
                      JOIN lab_room r ON r.room_id=a.room_id WHERE ''' + ' AND '.join(conditions)
        def dec(row):
            row['detail_url'] = url_for('equipment_detail', asset_id=row['asset_id'])
        return _listing('Thiết bị', 'Tra cứu thiết bị, phòng lưu trữ và lịch sử bảo trì.',
            from_sql, tuple(params), '''SELECT a.asset_id,a.asset_name,e.serial_number,e.model,
            r.room_name,a.status, (SELECT MAX(m.maint_date) FROM maintenance_log m
            WHERE m.asset_id=a.asset_id) AS latest_maintenance''',
            'ORDER BY a.asset_name,a.asset_id',
            [C('asset_id','Mã'),C('asset_name','Thiết bị'),C('serial_number','Số sê-ri'),
             C('model','Model'),C('room_name','Phòng'),C('status','Trạng thái'),C('latest_maintenance','Bảo trì gần nhất')],
            filters=[F('q','Tìm kiếm',placeholder='Tên, sê-ri, model'),
                     F('room','Phòng','select',options=[('','Tất cả phòng')]+_rooms_options()),
                     F('status','Trạng thái','select',options=[('','Tất cả')]+[(v,present(v)) for v in STATUS_CHOICES])],
            actions=[] if g.user.get('operator_account_id') else [{'label':'Đặt thiết bị', 'url':url_for('booking_new')}], decorate=dec)

    @app.get('/equipment/<int:asset_id>')
    @login_required
    def equipment_detail(asset_id):
        row = _get_or_404('''SELECT a.asset_id,a.asset_name,a.status,r.room_name,e.serial_number,e.model
            FROM equipment e JOIN lab_asset a ON a.asset_id=e.asset_id
            JOIN lab_room r ON r.room_id=a.room_id WHERE e.asset_id=%s''', (asset_id,))
        booked = db.fetch_all('''SELECT booking_id,start_time,end_time,booking_status FROM equipment_booking
            WHERE asset_id=%s AND booking_status IN ('PENDING','APPROVED') AND end_time>=CURRENT_TIMESTAMP ORDER BY start_time LIMIT 25''', (asset_id,))
        maintenance = db.fetch_all('''SELECT m.maint_id,m.maint_date,m.description,p.full_name AS technician
            FROM maintenance_log m JOIN personnel p ON p.personnel_id=m.technician_id
            WHERE m.asset_id=%s ORDER BY m.maint_date DESC,m.maint_id DESC LIMIT 25''', (asset_id,))
        return _detail(row['asset_name'], 'Thông tin thiết bị và lịch sử sử dụng.',
            [(v,row[k]) for k,v in [('asset_id','Mã tài sản'),('serial_number','Số sê-ri'),
                ('model','Model'),('room_name','Phòng'),('status','Trạng thái')]],
            actions=[{'label':'Đặt thiết bị này', 'url':url_for('booking_new',asset_id=asset_id)}],
            sections=[_section('Lịch đặt sắp tới', [C('booking_id','Mã lịch'),C('start_time','Bắt đầu'),C('end_time','Kết thúc'),C('booking_status','Trạng thái')], booked,
               'Không có lịch đặt sắp tới.', 'Danh sách khung giờ; không hiển thị dữ liệu riêng tư của người đặt.'),
            _section('Lịch sử bảo trì',[C('maint_id','Mã'),C('maint_date','Thời điểm'),C('technician','Kỹ thuật viên'),C('description','Nội dung')], maintenance)])

    @app.get('/equipment/schedule')
    @login_required
    def equipment_schedule():
        today=datetime.now(timezone(timedelta(hours=7))).date()
        day=optional_day(request.args.get('day'),'Ngày xem lịch') or today
        if not date(1900,1,2)<=day<=date(9998,12,30):raise InputError('Ngày xem lịch nằm ngoài phạm vi hỗ trợ.')
        room=_try_filter_id('room')
        begin=datetime.combine(day,datetime.min.time());finish=begin+timedelta(days=1)
        devices=db.fetch_all("""SELECT e.asset_id,a.asset_name,a.status,r.room_name
            FROM equipment e JOIN lab_asset a USING(asset_id) JOIN lab_room r ON r.room_id=a.room_id"""+
            (' WHERE a.room_id=%s' if room else '')+' ORDER BY r.room_name,a.asset_name', (room,) if room else ())
        # Shared occupancy contains no names, emails, purposes or project details.
        bookings=db.fetch_all("""SELECT b.asset_id,b.start_time,b.end_time,b.booking_status
            FROM equipment_booking b JOIN lab_asset a ON a.asset_id=b.asset_id
            WHERE b.booking_status IN ('PENDING','APPROVED') AND b.start_time<%s AND b.end_time>%s"""+
            (' AND a.room_id=%s' if room else '')+' ORDER BY b.start_time,b.booking_id',
            (finish,begin,room) if room else (finish,begin))
        first,last=7,19
        if request.args.get('hours')=='all':first,last=0,24
        else:
            for booking in bookings:
                lo=max(begin,booking['start_time']);hi=min(finish,booking['end_time'])
                first=min(first,int((lo-begin).total_seconds()//3600))
                last=max(last,int(((hi-begin).total_seconds()+3599)//3600))
        first=max(0,first);last=min(24,last);duration=(last-first)*60
        by_asset={d['asset_id']:[] for d in devices}
        for booking in bookings:
            lo=max(begin,booking['start_time']);hi=min(finish,booking['end_time'])
            start_min=(lo-begin).total_seconds()/60;end_min=(hi-begin).total_seconds()/60
            by_asset.get(booking['asset_id'],[]).append({
                'left':round((start_min-first*60)/duration*100,5),
                'width':round((end_min-start_min)/duration*100,5),
                'start':present(booking['start_time']),'end':present(booking['end_time']),
                'label':present(booking['booking_status']),'pending':booking['booking_status']=='PENDING',
                'short_start':lo.strftime('%H:%M'),'short_end':hi.strftime('%H:%M') if hi<finish else '24:00'})
        for device in devices:device['slots']=by_asset[device['asset_id']]
        now=datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
        now_percent=((now-begin).total_seconds()/60-first*60)/duration*100
        return render_template('equipment_schedule.html',title='Lịch thiết bị theo ngày',devices=devices,
            day=day,today=today,previous=day-timedelta(days=1),following=day+timedelta(days=1),
            rooms=_rooms_options(),selected_room=room,hours=range(first,last),first=first,last=last,
            hour_count=last-first,now_percent=now_percent if day==today and 0<=now_percent<=100 else None,
            all_hours=request.args.get('hours')=='all',busy_count=len(bookings),
            may_book=not g.user.get('operator_account_id') and day>=today)

    @app.route('/bookings/new', methods=['GET','POST'])
    @login_required
    def booking_new():
        fields = [F('asset_id','Thiết bị','select',options=[('','Chọn thiết bị')]+_equipment_options(),required=True),
            F('project_id','Đề tài (tùy chọn)','select',options=[('','Không gắn đề tài')]+_project_options()),
            F('start_time','Bắt đầu','booking-datetime',required=True),
            F('end_time','Kết thúc','booking-datetime',required=True),
            F('purpose','Mục đích','textarea',help='Tối đa 255 ký tự')]
        now_vn=datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None)
        next_quarter=(now_vn+timedelta(minutes=15-now_vn.minute%15)).replace(second=0,microsecond=0)
        for field in fields:
            if field['kind']=='booking-datetime':
                field['step']=900
                field['min_value']=next_quarter.strftime('%Y-%m-%dT%H:%M')
                field['help']='Giờ Việt Nam; chỉ chọn phút 00, 15, 30 hoặc 45. Thời gian bắt đầu phải ở tương lai.'
        defaults = {'asset_id':request.args.get('asset_id',''),
                    'start_time': (datetime.now() + timedelta(days=1)).replace(hour=9,minute=0).strftime('%Y-%m-%dT%H:%M'),
                    'end_time': (datetime.now() + timedelta(days=1)).replace(hour=10,minute=0).strftime('%Y-%m-%dT%H:%M')}
        if request.method=='GET':
            for time_key in ('start_time','end_time'):
                if request.args.get(time_key):
                    defaults[time_key]=local_datetime(request.args[time_key]).strftime('%Y-%m-%dT%H:%M')
        values = _value_map(fields,defaults)
        if request.method=='POST':
            for time_name in ('start_time','end_time'):
                if time_name+'_date' in request.form:
                    values[time_name]=(request.form.get(time_name+'_date','')+'T'+request.form.get(time_name+'_hour','')+':'+request.form.get(time_name+'_minute',''))
        try:
            selected_asset = positive_id(values.get('asset_id'), 'Thiết bị', optional=True)
        except InputError:
            selected_asset = None
        reservations = (db.fetch_all('''SELECT start_time,end_time FROM equipment_booking
              WHERE asset_id=%s AND booking_status IN ('PENDING','APPROVED') AND end_time>=CURRENT_TIMESTAMP
              ORDER BY start_time LIMIT 8''', (selected_asset,)) if selected_asset else [])
        if request.method == 'POST':
            def do():
                asset = positive_id(values['asset_id'],'Thiết bị')
                project = positive_id(values['project_id'],'Đề tài',optional=True)
                start = local_datetime(values['start_time'],'Bắt đầu')
                end = local_datetime(values['end_time'],'Kết thúc')
                if start <= datetime.now(timezone(timedelta(hours=7))).replace(tzinfo=None):
                    raise InputError('Thời gian bắt đầu phải sau thời điểm hiện tại (giờ Việt Nam).')
                if start.minute%15 or end.minute%15:
                    raise InputError('Chỉ được đặt phút 00, 15, 30 hoặc 45.')
                if end <= start:
                    raise InputError('Thời gian kết thúc phải sau thời gian bắt đầu.')
                reason = limited_text(values.get('purpose'),'Mục đích',255)
                return db.procedure('sp_book_equipment',
                   [asset,g.user['personnel_id'],project,start,end,reason],out=True)
            response,error = _handle_write(do, 'Đã gửi lịch #{id}, đang chờ ADMIN duyệt. Khung giờ được giữ tạm.', 'bookings')
            if response: return response
            return _render_form('Đặt lịch thiết bị','Lịch trùng sẽ bị từ chối bởi MySQL.',fields,
                    values=values,error=error,submit='Gửi yêu cầu đặt lịch',back=url_for('bookings'),reservations=reservations)
        return _render_form('Đặt lịch thiết bị','Người đặt là tài khoản đang đăng nhập: '+g.user['full_name'],
            fields,values=values,submit='Gửi yêu cầu đặt lịch',back=url_for('bookings'),
            note='Hai lịch sát nhau có thể hợp lệ. Lịch chờ duyệt giữ chỗ tạm. Chỉ sử dụng thiết bị sau khi ADMIN duyệt; lịch từ chối sẽ nhả chỗ.', reservations=reservations)

    @app.get('/bookings/preview')
    @login_required
    def booking_preview():
        # Read-only availability without revealing other bookers' details.
        raw=request.args.get('asset_id','').strip()
        if not raw:
            return jsonify(selected=False, message='Chọn thiết bị để xem lịch đã đặt.', reservations=[])
        asset=positive_id(raw,'Thiết bị')
        current=db.fetch_one('''SELECT e.asset_id,a.asset_name,a.status FROM equipment e
             JOIN lab_asset a ON a.asset_id=e.asset_id WHERE e.asset_id=%s''',(asset,))
        if current is None:
            return jsonify(selected=False,message='Thiết bị không còn tồn tại.',reservations=[]),404
        reservations=db.fetch_all('''SELECT b.start_time,b.end_time,b.booking_status FROM equipment_booking b
             WHERE b.asset_id=%s AND b.booking_status IN ('PENDING','APPROVED') AND b.end_time>=CURRENT_TIMESTAMP
             ORDER BY b.start_time LIMIT 8''',(asset,))
        return jsonify(selected=True,asset_name=current['asset_name'],
            asset_status=present(current['status']),
            reservations=[{'start':present(r['start_time']),'end':present(r['end_time']),'status':present(r.get('booking_status','APPROVED'))}
                          for r in reservations],
            message=('Các khoảng dưới đây đang giữ chỗ (chờ duyệt hoặc đã duyệt). Hai lịch chạm biên được phép.'
                     if reservations else 'Chưa có lịch đặt sắp tới cho thiết bị này.'))

    @app.get('/bookings')
    @login_required
    def bookings():
        scope = request.args.get('scope','')
        if g.user.get('operator_account_id'): scope='all'
        if scope not in ('','own','all'):
            raise InputError('Phạm vi lịch không hợp lệ.')
        if scope == 'all' and not g.user['operator']:
            abort(403)
        is_all = g.user['operator'] and scope=='all'
        booking_status=choice(request.args.get('booking_status',''),['PENDING','APPROVED','REJECTED'],'Trạng thái lịch')
        equip = _try_filter_id('asset')
        day_from, day_to = date_window(request.args)
        where = []
        params = []
        if not is_all:
            where.append('b.personnel_id=%s'); params.append(g.user['personnel_id'])
        if booking_status:
            where.append('b.booking_status=%s');params.append(booking_status)
        if equip:
            where.append('b.asset_id=%s'); params.append(equip)
        if day_from:
            where.append('b.end_time>=%s'); params.append(datetime.combine(day_from,datetime.min.time()))
        if day_to:
            where.append('b.start_time<=%s'); params.append(inclusive_day_end(day_to))
        cond = ' AND '.join(where) if where else '1=1'
        f = [F('asset','Thiết bị','select',options=[('','Tất cả thiết bị')]+_equipment_options()),
             F('from','Từ ngày','date'),F('to','Đến ngày','date')]
        if g.user['operator'] and not g.user.get('operator_account_id'):
            f.insert(0,F('scope','Phạm vi','select',options=[('own','Lịch của tôi'),('all','Toàn bộ lịch')]))
        f.append(F('booking_status','Trạng thái','select',options=[('','Tất cả'),('PENDING','Chờ duyệt'),('APPROVED','Đã duyệt'),('REJECTED','Từ chối')]))
        def decorate_booking(row):
            row['can_manage_booking']=bool(g.user.get('operator_account_id'))
            row['review_url']=url_for('booking_review',booking_id=row['booking_id']) if row['booking_status']=='PENDING' and row['can_manage_booking'] else None
        return _listing('Quản lý lịch đặt' if g.user.get('operator_account_id') else 'Lịch của tôi', 'Lịch chờ duyệt giữ chỗ tạm; chỉ lịch đã duyệt được sử dụng. Lịch từ chối không giữ chỗ.',
            '''FROM equipment_booking b JOIN lab_asset a ON a.asset_id=b.asset_id
               JOIN lab_room r ON r.room_id=a.room_id JOIN personnel p ON p.personnel_id=b.personnel_id
               LEFT JOIN research_project pr ON pr.project_id=b.project_id WHERE '''+cond,
            tuple(params), '''SELECT b.booking_id,a.asset_name,r.room_name,
                 p.full_name AS booked_by,pr.project_name,b.start_time,b.end_time,b.purpose,b.booking_status,b.reviewed_at,b.review_note''',
            'ORDER BY b.booking_id DESC',
            [C('booking_id','Mã'),C('asset_name','Thiết bị'),C('booked_by','Người đặt'),
             C('project_name','Đề tài'),C('start_time','Bắt đầu'),C('end_time','Kết thúc'),C('purpose','Mục đích'),C('booking_status','Trạng thái'),C('reviewed_at','Ngày duyệt'),C('review_note','Ghi chú')],
            filters=f,actions=[] if g.user.get('operator_account_id') else [{'label':'Đặt lịch mới','url':url_for('booking_new')}],decorate=decorate_booking)

    @app.post('/bookings/<int:booking_id>/review')
    @operator_required
    def booking_review(booking_id):
        if not g.user.get('operator_account_id'):abort(403)
        decision=request.form.get('decision')
        if decision not in ('approve','reject'):raise InputError('Quyết định không hợp lệ.')
        note=limited_text(request.form.get('note'),'Ghi chú',500,required=decision=='reject')
        try:
            db.procedure('sp_review_booking',[booking_id,g.user['operator_account_id'],decision=='approve',note],out=False)
            flash('Đã duyệt lịch.' if decision=='approve' else 'Đã từ chối lịch; khung giờ đã được nhả.','success')
        except db.DatabaseUnavailable:raise
        except MySQLError as exc:flash(safe_db_message(exc),'error')
        return redirect(url_for('bookings',booking_status='PENDING'))

    @app.get('/chemicals')
    @login_required
    def chemicals():
        search = request.args.get('q','').strip()[:100]
        room = _try_filter_id('room')
        hazard = _try_filter_id('hazard')
        if hazard and hazard > 5:
            raise InputError('Cấp nguy hiểm phải từ 1 đến 5.')
        expiry = choice(request.args.get('expiry','valid'), ['expired','soon','valid'], 'Hạn dùng')
        stock = choice(request.args.get('stock',''), ['positive','zero'], 'Tồn kho')
        clauses, params = ['1=1'], []
        if search:
            clauses.append('a.asset_name LIKE %s'); params.append('%'+search+'%')
        if room:
            clauses.append('a.room_id=%s'); params.append(room)
        if hazard:
            clauses.append('c.hazard_level=%s'); params.append(hazard)
        if expiry=='expired':
            clauses.append('c.expiry_date<CURRENT_DATE()')
        elif expiry=='soon':
            clauses.append('c.expiry_date>=CURRENT_DATE() AND c.expiry_date<=DATE_ADD(CURRENT_DATE(),INTERVAL 30 DAY)')
        elif expiry=='valid':
            clauses.append('c.expiry_date>=CURRENT_DATE()')
        if stock=='positive':
            clauses.append('c.stock_qty>0')
        if stock=='zero':
            clauses.append('c.stock_qty=0')
        grouped='''SELECT MIN(c.asset_id) AS asset_id,a.asset_name,c.unit,c.hazard_level,c.concentration,
            COUNT(*) AS lot_count,SUM(c.stock_qty) AS stock_qty,MIN(c.expiry_date) AS nearest_expiry
            FROM chemical_material c JOIN lab_asset a ON a.asset_id=c.asset_id
            JOIN lab_room r ON r.room_id=a.room_id WHERE '''+ ' AND '.join(clauses) + ' GROUP BY a.asset_name,c.unit,c.hazard_level,c.concentration'
        def dec(row):
            row['detail_url']=url_for('chemical_lots',asset_id=row['asset_id'],expiry=expiry or 'valid')
            row['link_key']='asset_name'
            row['dispensable_qty']=0 if expiry=='expired' else row['stock_qty']
        return _listing('Hóa chất', 'Chọn hóa chất để xem từng lô, số lượng còn lại và ngày cấp phát. Các nồng độ hoặc đơn vị khác nhau được hiển thị riêng.',
            'FROM ('+grouped+') AS grouped_chemicals',tuple(params),
            'SELECT *','ORDER BY asset_name',
            [C('asset_name','Hóa chất'),C('concentration','Nồng độ'),C('hazard_level','Cấp'),
             C('lot_count','Số lô'),C('stock_qty','Tổng tồn'),C('unit','Đơn vị'),
             C('dispensable_qty','Có thể cấp phát'),C('nearest_expiry','Hạn gần nhất')],
            filters=[F('q','Tìm hóa chất'),F('room','Phòng','select',options=[('','Tất cả')]+_rooms_options()),
              F('hazard','Cấp nguy hiểm','select',options=[('','Tất cả')]+[(str(i),str(i)) for i in range(1,6)]),
              F('expiry','Hạn dùng','select',options=[('valid','Còn hạn'),('expired','Hết hạn'),('soon','Sắp hết hạn (30 ngày)')]),
              F('stock','Tồn kho','select',options=[('','Tất cả'),('positive','Còn tồn'),('zero','Hết tồn')])],
            actions=([{'label':'Bổ sung hóa chất','url':url_for('chemical_new')},{'label':'Cấp phát hóa chất','url':url_for('dispense_new')}] if g.user['operator'] else []),decorate=dec)

    @app.get('/chemicals/<int:asset_id>/lots')
    @login_required
    def chemical_lots(asset_id):
        chemical=_get_or_404("""SELECT a.asset_name,c.unit,c.concentration,c.hazard_level
            FROM chemical_material c JOIN lab_asset a USING(asset_id) WHERE c.asset_id=%s""",(asset_id,))
        expiry=choice(request.args.get('expiry','valid'),['valid','expired','soon'],'Hạn dùng') or 'valid'
        condition='c.expiry_date<CURRENT_DATE()' if expiry=='expired' else 'c.expiry_date>=CURRENT_DATE()'
        if expiry=='soon': condition+=' AND c.expiry_date<=DATE_ADD(CURRENT_DATE(),INTERVAL 30 DAY)'
        params=[]
        scope=''
        if not g.user['operator']:
            scope=' AND d.personnel_id=%s';params.append(g.user['personnel_id'])
        params.extend([chemical['asset_name'],chemical['unit'],chemical['concentration'],chemical['hazard_level']])
        lots=db.fetch_all("""SELECT c.asset_id,r.room_name,c.stock_qty,c.unit,c.expiry_date,
            (SELECT received_on FROM chemical_receipt cr WHERE cr.asset_id=c.asset_id) AS received_on,
            (SELECT MAX(d.dispense_date) FROM chemical_dispense_log d WHERE d.asset_id=c.asset_id"""+scope+""") AS last_dispense
            FROM chemical_material c JOIN lab_asset a USING(asset_id) JOIN lab_room r ON r.room_id=a.room_id
            WHERE a.asset_name=%s AND c.unit=%s AND c.concentration <=> %s AND c.hazard_level=%s AND """+condition+
            ' ORDER BY c.expiry_date,c.asset_id',tuple(params))
        for lot in lots:
            lot['detail_url']=url_for('chemical_detail',asset_id=lot['asset_id'])
            lot['link_key']='asset_id'
        return render_template('chemical_lots.html',title=chemical['asset_name'],chemical=chemical,lots=lots,expiry=expiry,
            columns=[C('asset_id','Mã lô'),C('room_name','Phòng'),C('stock_qty','Còn lại'),C('unit','Đơn vị'),
                C('received_on','Ngày nhập lô'),C('expiry_date','Ngày hết hạn'),C('last_dispense','Cấp phát gần nhất' if g.user['operator'] else 'Lần nhận gần nhất của tôi')])

    @app.route('/chemicals/<int:asset_id>/replenish',methods=['GET','POST'])
    @operator_required
    def chemical_replenish(asset_id):
        chemical=_get_or_404("""SELECT a.asset_name,a.room_id,r.room_name,c.unit,c.concentration,c.hazard_level
            FROM chemical_material c JOIN lab_asset a USING(asset_id) JOIN lab_room r ON r.room_id=a.room_id
            WHERE c.asset_id=%s""",(asset_id,))
        fields=[F('unit','Đơn vị',required=True),F('quantity','Số lượng nhập','number',required=True),
            F('expiry','Hạn sử dụng','date',required=True),F('received_on','Ngày nhập lô','date',required=True)]
        values=_value_map(fields,{'unit':chemical['unit'],'received_on':date.today().isoformat()})
        error=None
        if request.method=='POST':
            try:
                unit=limited_text(values.get('unit'),'Đơn vị',20,required=True)
                qty=quantity(values.get('quantity'))
                try:
                    expiry=date.fromisoformat(values.get('expiry',''))
                    received=date.fromisoformat(values.get('received_on',''))
                except ValueError: raise InputError('Vui lòng nhập đủ ngày hợp lệ.')
                if expiry<date.today():raise InputError('Không nhập lô đã hết hạn.')
                if received>date.today() or received>expiry:raise InputError('Ngày nhập không được ở tương lai hoặc sau hạn sử dụng.')
                new_id=db.procedure('sp_receive_chemical',[asset_id,unit,qty,expiry,received,g.user.get('operator_account_id',g.user['personnel_id'])],out=True)
                flash('Đã bổ sung lô #'+str(new_id)+'. Lô mới đã có thể cấp phát.','success')
                return redirect(url_for('chemical_lots',asset_id=new_id,expiry='valid'))
            except InputError as exc:error=str(exc)
            except db.DatabaseUnavailable:raise
            except MySQLError as exc:error=safe_db_message(exc)
        return _render_form('Bổ sung · '+chemical['asset_name'],
            'Phòng: '+chemical['room_name']+' · Cấp nguy hiểm: '+str(chemical['hazard_level'])+' · Nồng độ: '+(chemical['concentration'] or 'Không ghi'),
            fields,values=values,error=error,submit='Bổ sung lô mới',back=url_for('chemical_lots',asset_id=asset_id),
            note='Tạo lô mới cùng hóa chất và phòng. Không sửa lô cũ. Ngày nhập kho khác với ngày cấp phát cho người nhận.')

    @app.get('/chemicals/<int:asset_id>')
    @login_required
    def chemical_detail(asset_id):
        chemical = _get_or_404('''SELECT c.asset_id,a.asset_name,a.status,r.room_name,
            c.hazard_level,c.unit,c.stock_qty,c.concentration,c.expiry_date
            FROM chemical_material c JOIN lab_asset a ON a.asset_id=c.asset_id
            JOIN lab_room r ON r.room_id=a.room_id WHERE c.asset_id=%s''',(asset_id,))
        where='d.asset_id=%s'
        params=[asset_id]
        if not g.user['operator']:
            where+=' AND d.personnel_id=%s'; params.append(g.user['personnel_id'])
        histories=db.fetch_all('''SELECT d.dispense_id,d.quantity,d.dispense_date,d.purpose,
            p.full_name AS recipient,pr.project_name FROM chemical_dispense_log d
            JOIN personnel p ON p.personnel_id=d.personnel_id
            LEFT JOIN research_project pr ON pr.project_id=d.project_id WHERE '''+where+
            ' ORDER BY d.dispense_date DESC,d.dispense_id DESC LIMIT 30',tuple(params))
        status='Đã hết hạn' if chemical['expiry_date']<date.today() else 'Chưa hết hạn'
        actions=[]
        if g.user['operator']:
            actions.append({'label':'Bổ sung','url':url_for('chemical_replenish',asset_id=asset_id)})
            if chemical['expiry_date'] >= date.today() and chemical['stock_qty'] > 0:
                actions.append({'label':'Cấp phát hóa chất này','url':url_for('dispense_new',asset_id=asset_id)})
        return _detail(chemical['asset_name'], 'Thông tin lưu trữ, tồn kho và lịch sử cấp phát được phép xem.',
            [('Có thể cấp phát', 0 if chemical['expiry_date'] < date.today() else chemical['stock_qty'])] + [(label, chemical[key]) for key,label in [('asset_id','Mã tài sản'),('room_name','Phòng'),
              ('status','Trạng thái tài sản'),('hazard_level','Cấp nguy hiểm'),('stock_qty','Số lượng tồn'),
              ('unit','Đơn vị'),('concentration','Nồng độ'),('expiry_date','Hạn dùng')]]+[('Tình trạng hạn',status)],
            sections=[_section('Lịch sử cấp phát'+('' if g.user['operator'] else ' của tôi'),
              [C('dispense_id','Mã'),C('recipient','Người nhận'),C('quantity','Số lượng'),
               C('dispense_date','Thời gian'),C('project_name','Đề tài'),C('purpose','Mục đích')], histories)],actions=actions)

    @app.route('/chemicals/new', methods=['GET','POST'])
    @operator_required
    def chemical_new():
        fields=[F('name','Tên hóa chất / lô nhập',required=True),
            F('room','Phòng lưu trữ','select',options=[('','Chọn phòng')]+_rooms_options(),required=True),
            F('hazard','Cấp nguy hiểm','select',options=[(str(i),str(i)) for i in range(1,6)],required=True),
            F('unit','Đơn vị (g, mL, kg...)',required=True),
            F('stock','Số lượng nhập','number',required=True),
            F('concentration','Nồng độ (tùy chọn)'),
            F('expiry','Hạn sử dụng','date',required=True)]
        values=_value_map(fields)
        error=None
        if request.method=='POST':
            def do():
                name=limited_text(values.get('name'),'Tên hóa chất',150,required=True)
                room=positive_id(values.get('room'),'Phòng')
                hazard=positive_id(values.get('hazard'),'Cấp nguy hiểm')
                if hazard>5: raise InputError('Cấp nguy hiểm từ 1 đến 5.')
                unit=limited_text(values.get('unit'),'Đơn vị',20,required=True)
                stock=quantity(values.get('stock'))
                concentration=limited_text(values.get('concentration'),'Nồng độ',40)
                try: expiry=date.fromisoformat(values.get('expiry',''))
                except ValueError: raise InputError('Hạn sử dụng không hợp lệ.')
                if expiry<date.today(): raise InputError('Không nhập lô hóa chất đã hết hạn.')
                return db.procedure('sp_create_chemical',[name,room,hazard,unit,stock,concentration,expiry],out=True)
            response,error=_handle_write(do,'Đã bổ sung lô hóa chất #{id}.','chemicals')
            if response: return response
        return _render_form('Bổ sung hóa chất','Nhập một lô mới vào phòng; không thay đổi hạn dùng hoặc tồn kho của lô cũ.',fields,
            values=values,error=error,submit='Nhập hóa chất vào phòng',back=url_for('chemicals'),
            note='Mỗi lần nhập tạo lô riêng. Phòng phải đáp ứng cấp nguy hiểm. Không trộn lô mới với hóa chất hết hạn.')

    @app.route('/dispenses/new',methods=['GET','POST'])
    @operator_required
    def dispense_new():
        fields=[F('asset_id','Hóa chất','select',options=[('','Chọn hóa chất')]+_chemical_options(usable=True),required=True),
                F('personnel_id','Người nhận','select',options=[('','Chọn người nhận')]+_person_options(),required=True,
                  help='Chứng chỉ được kiểm tra cho người nhận, không phải người đang cấp phát.'),
                F('project_id','Đề tài (tùy chọn)','select',options=[('','Không gắn đề tài')]+_project_options()),
                F('quantity','Số lượng','number',required=True,help='Số dương; tối đa ba chữ số thập phân. Đơn vị hiển thị trong lựa chọn hóa chất.'),
                F('purpose','Mục đích','textarea',help='Tối đa 255 ký tự')]
        values=_value_map(fields,{'asset_id':request.args.get('asset_id',''),
                                  'personnel_id':request.args.get('personnel_id','')})
        eligibility = None
        try:
            chosen_asset = positive_id(values.get('asset_id'),'Hóa chất',optional=True)
            chosen_recipient = positive_id(values.get('personnel_id'),'Người nhận',optional=True)
        except InputError:
            chosen_asset,chosen_recipient = None,None
        if chosen_asset and chosen_recipient:
            guidance = db.fetch_one('''SELECT c.hazard_level,c.stock_qty,c.unit,c.expiry_date,
              (SELECT MAX(sc.hazard_level) FROM personnel_certificate pc
               JOIN safety_certificate sc ON sc.cert_id=pc.cert_id
               WHERE pc.personnel_id=%s AND pc.issue_date<=CURRENT_DATE()
               AND pc.expiry_date>=CURRENT_DATE()) AS max_valid_level
              FROM chemical_material c WHERE c.asset_id=%s''',(chosen_recipient,chosen_asset))
            if guidance:
                eligible = guidance['hazard_level'] < 2 or (
                    guidance['max_valid_level'] is not None and
                    guidance['max_valid_level'] >= guidance['hazard_level'])
                eligibility = ('Chứng chỉ người nhận: ' +
                    ('Đạt cấp yêu cầu hiện tại.' if eligible else 'Chưa đạt cấp yêu cầu hiện tại.') +
                    ' Cấp hóa chất: '+str(guidance['hazard_level'])+
                    '; cấp chứng chỉ tối đa: '+present(guidance['max_valid_level'])+
                    '. Tồn hiện tại: '+present(guidance['stock_qty'])+' '+guidance['unit']+
                    '. MySQL sẽ xác minh lại khi ghi.')
        if request.method=='POST':
            def do():
                asset=positive_id(values['asset_id'],'Hóa chất')
                person=positive_id(values['personnel_id'],'Người nhận')
                project=positive_id(values['project_id'],'Đề tài',optional=True)
                qty=quantity(values['quantity'])
                reason=limited_text(values.get('purpose'),'Mục đích',255)
                chemical=db.fetch_one('SELECT expiry_date,stock_qty FROM chemical_material WHERE asset_id=%s',(asset,))
                if chemical is None or chemical['expiry_date'] < date.today():
                    raise InputError('Hóa chất đã hết hạn: có thể cấp phát 0. Hãy nhập lô mới.')
                # Never subtract stock in Python; SQL trigger does it once atomically.
                return db.procedure('sp_dispense_chemical',[asset,person,project,qty,reason],out=True)
            response,error=_handle_write(do,'Đã cấp phát thành công, mã nhật ký #{id}.','dispenses')
            if response:
                return redirect(url_for('chemical_detail',asset_id=positive_id(values['asset_id'],'Hóa chất')))
            return _render_form('Cấp phát hóa chất','Hành động này làm giảm tồn kho và ghi nhật ký.',fields,
                    values=values,error=error,submit='Xác nhận cấp phát',back=url_for('dispenses'),
                    note='Cần kiểm tra lại lịch sử nếu kết nối bị ngắt đúng lúc gửi; không gửi lại một cách tự động.',eligibility=eligibility)
        return _render_form('Cấp phát hóa chất','Chọn hóa chất, người nhận và số lượng phù hợp.',fields,
                    values=values,submit='Xác nhận cấp phát',back=url_for('dispenses'),
                    note='Chỉ chứng chỉ của người nhận được đối chiếu. Cấp phát không đồng nghĩa với phân bổ tài sản cho đề tài.',eligibility=eligibility)

    @app.get('/dispenses/preview')
    @operator_required
    def dispense_preview():
        # Read-only eligibility snapshot. SQL trigger is authoritative.
        asset_raw=request.args.get('asset_id','').strip()
        person_raw=request.args.get('personnel_id','').strip()
        if not asset_raw:
            return jsonify(selected=False,message='Chọn hóa chất để xem tồn kho và điều kiện cấp phát.')
        asset=positive_id(asset_raw,'Hóa chất')
        chem=db.fetch_one('''SELECT c.asset_id,a.asset_name,a.status,c.hazard_level,
             c.stock_qty,c.unit,c.expiry_date,
             (c.expiry_date < CURRENT_DATE()) AS expired
             FROM chemical_material c JOIN lab_asset a ON a.asset_id=c.asset_id
             WHERE c.asset_id=%s''',(asset,))
        if chem is None:
            return jsonify(selected=False,message='Hóa chất không còn tồn tại.'),404
        result={'selected':True,'asset_name':chem['asset_name'],
            'stock':present(chem['stock_qty']), 'unit':chem['unit'],
            'hazard_level':chem['hazard_level'], 'status':present(chem['status']),
            'expiry_date':present(chem['expiry_date']),
            'expired':bool(chem['expired']), 'dispensable_stock': '0' if chem['expired'] else present(chem['stock_qty']), 'has_recipient':False,
            'message':'Chọn người nhận để đối chiếu chứng chỉ còn hiệu lực.'}
        if person_raw:
            pid=positive_id(person_raw,'Người nhận')
            recipient=db.fetch_one('''SELECT p.full_name,
                 (SELECT MAX(sc.hazard_level) FROM personnel_certificate pc
                  JOIN safety_certificate sc ON sc.cert_id=pc.cert_id
                  WHERE pc.personnel_id=p.personnel_id
                  AND pc.issue_date<=CURRENT_DATE() AND pc.expiry_date>=CURRENT_DATE())
                  AS max_valid_level FROM personnel p WHERE p.personnel_id=%s''',(pid,))
            if recipient is None:
                return jsonify(selected=False,message='Không tìm thấy người nhận hợp lệ.'),404
            eligible=(chem['hazard_level'] < 2 or
                      (recipient['max_valid_level'] is not None and
                       recipient['max_valid_level']>=chem['hazard_level']))
            result.update(has_recipient=True,recipient=recipient['full_name'],
                max_valid_level=present(recipient['max_valid_level']),
                certificate_eligible=eligible,
                message=('Chứng chỉ người nhận đáp ứng cấp nguy hiểm hiện tại.' if eligible
                         else 'Người nhận chưa có chứng chỉ phù hợp ở thời điểm kiểm tra.'))
        if chem['expired']:
            result['message']='Hóa chất đã hết hạn. Có thể cấp phát: 0. Vui lòng nhập lô mới.'
        return jsonify(result)

    @app.get('/dispenses')
    @login_required
    def dispenses():
        scope = choice(request.args.get('scope',''),['own','all'],'Phạm vi')
        if g.user.get('operator_account_id'):scope='all'
        if scope == 'all' and not g.user['operator']:
            abort(403)
        is_all=g.user['operator'] and scope!='own'
        asset = _try_filter_id('asset')
        day_from, day_to = date_window(request.args)
        cond=[]; params=[]
        if not is_all:
            cond.append('d.personnel_id=%s'); params.append(g.user['personnel_id'])
        if asset:
            cond.append('d.asset_id=%s'); params.append(asset)
        if day_from:
            cond.append('d.dispense_date>=%s'); params.append(datetime.combine(day_from,datetime.min.time()))
        if day_to:
            cond.append('d.dispense_date<=%s'); params.append(inclusive_day_end(day_to))
        where=' AND '.join(cond) if cond else '1=1'
        filt=[F('asset','Hóa chất','select',options=[('','Tất cả')]+_chemical_options()),
              F('from','Từ ngày','date'),F('to','Đến ngày','date')]
        if g.user['operator'] and not g.user.get('operator_account_id'):
            filt.insert(0,F('scope','Phạm vi','select',options=[('all','Toàn bộ'),('own','Chỉ bản thân')]))
        return _listing('Lịch sử cấp phát', 'Số lượng theo từng hóa chất/đơn vị, không cộng gộp khác đơn vị.',
           '''FROM chemical_dispense_log d JOIN chemical_material c ON c.asset_id=d.asset_id
              JOIN lab_asset a ON a.asset_id=d.asset_id JOIN personnel p ON p.personnel_id=d.personnel_id
              LEFT JOIN research_project pr ON pr.project_id=d.project_id WHERE '''+where,
            tuple(params),'''SELECT d.dispense_id,a.asset_name,p.full_name AS recipient,
               d.quantity,c.unit,d.dispense_date,pr.project_name,d.purpose''',
            'ORDER BY d.dispense_date DESC,d.dispense_id DESC',
            [C('dispense_id','Mã'),C('asset_name','Hóa chất'),C('recipient','Người nhận'),
             C('quantity','Số lượng'),C('unit','Đơn vị'),C('dispense_date','Ngày cấp'),
             C('project_name','Đề tài'),C('purpose','Mục đích')],
            filters=filt,actions=([{'label':'Cấp phát mới','url':url_for('dispense_new')}] if g.user['operator'] else []))

    @app.get('/rooms')
    @login_required
    def rooms():
        search=request.args.get('q','').strip()[:100]
        params=('%'+search+'%',) if search else ()
        where='WHERE r.room_name LIKE %s' if search else ''
        return _listing('Phòng thí nghiệm', 'Cấp an toàn và tình trạng sử dụng theo dữ liệu thực.',
           'FROM lab_room r '+where,params,'''SELECT r.room_id,r.room_name,r.safety_category,
             (SELECT COUNT(*) FROM lab_asset a WHERE a.room_id=r.room_id AND a.asset_type='EQUIPMENT') AS equipment_count,
             (SELECT COUNT(*) FROM lab_asset a WHERE a.room_id=r.room_id AND a.asset_type='CHEMICAL') AS chemical_count''',
           'ORDER BY r.room_id',
           [C('room_id','Mã phòng'),C('room_name','Tên phòng'),C('safety_category','Cấp an toàn'),
            C('equipment_count','Thiết bị'),C('chemical_count','Hóa chất')],
           filters=[F('q','Tìm phòng')],
           decorate=lambda r: r.update(detail_url=url_for('room_detail',room_id=r['room_id'])))

    @app.get('/rooms/<int:room_id>')
    @login_required
    def room_detail(room_id):
        room=_get_or_404('SELECT room_id,room_name,safety_category FROM lab_room WHERE room_id=%s',(room_id,))
        assets=db.fetch_all('''SELECT a.asset_id,a.asset_name,a.asset_type,a.status,
           c.hazard_level,c.stock_qty,c.unit
           FROM lab_asset a LEFT JOIN chemical_material c ON c.asset_id=a.asset_id
           WHERE a.room_id=%s ORDER BY a.asset_type,a.asset_name''',(room_id,))
        for a in assets:
            a['detail_url']=url_for('equipment_detail' if a['asset_type']=='EQUIPMENT' else 'chemical_detail',asset_id=a['asset_id'])
        hazard=max((a['hazard_level'] or 0 for a in assets),default=0)
        return _detail(room['room_name'],'Thông tin tài sản và điều kiện an toàn của phòng.',
            [('Mã phòng',room['room_id']),('Cấp an toàn',room['safety_category']),
             ('Cấp nguy hiểm hóa chất cao nhất',hazard)],
            sections=[_section('Tài sản tại phòng',
             [C('asset_id','Mã'),C('asset_name','Tài sản'),C('asset_type','Loại'),
              C('status','Trạng thái'),C('hazard_level','Cấp nguy hiểm'),
              C('stock_qty','Tồn kho'),C('unit','Đơn vị')],assets)],
            actions=[{'label':'Vào phòng này','url':url_for('access',room_id=room_id)}],
            note='Việc cho phép vào phòng được kiểm tra theo hóa chất thực có trong phòng và chứng chỉ còn hiệu lực.')

    @app.route('/access',methods=['GET'])
    @login_required
    def access():
        pid=g.user['personnel_id']
        visit=db.fetch_one('''SELECT l.access_id,l.entry_time,r.room_name,l.purpose
             FROM lab_access_log l JOIN lab_room r ON r.room_id=l.room_id
             WHERE l.personnel_id=%s AND l.exit_time IS NULL
             ORDER BY l.entry_time DESC LIMIT 1''',(pid,))
        scope=choice(request.args.get('scope',''),['all','own'],'Phạm vi')
        if g.user.get('operator_account_id'):scope='all'
        if scope == 'all' and not g.user['operator']:
            abort(403)
        all_history=g.user['operator'] and scope=='all'
        room_filter=_try_filter_id('room')
        from_day,to_day=date_window(request.args)
        parts=[]; params=[]
        if not all_history:
            parts.append('l.personnel_id=%s'); params.append(pid)
        if room_filter:
            parts.append('l.room_id=%s'); params.append(room_filter)
        if from_day:
            parts.append('l.entry_time >= %s'); params.append(datetime.combine(from_day,datetime.min.time()))
        if to_day:
            parts.append('l.entry_time <= %s'); params.append(inclusive_day_end(to_day))
        where=' AND '.join(parts) if parts else '1=1'
        params=tuple(params)
        page=page_number(request.args.get('page'))
        from_sql='''FROM lab_access_log l JOIN personnel p ON p.personnel_id=l.personnel_id
              JOIN lab_room r ON r.room_id=l.room_id WHERE '''+where
        total=int(db.scalar('SELECT COUNT(*) AS n '+from_sql,params))
        rows=db.fetch_all('''SELECT l.access_id,p.full_name,r.room_name,l.entry_time,l.exit_time,l.purpose,
             CASE WHEN l.exit_time IS NULL THEN NULL
                  ELSE TIMESTAMPDIFF(MINUTE,l.entry_time,l.exit_time) END AS duration_minutes '''+
             from_sql+' ORDER BY l.entry_time DESC,l.access_id DESC LIMIT %s OFFSET %s',
             (*params,PAGE_SIZE,(page-1)*PAGE_SIZE))
        return render_template('access.html',title='Ra vào phòng',visit=visit,rows=rows,
            rooms=_rooms_options(),preselected=request.args.get('room_id',''),
            total=total,page=page,pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE),
            all_history=all_history,
            history_filters=[F('room','Phòng','select',options=[('','Tất cả phòng')]+_rooms_options()),
                             F('from','Từ ngày','date'),F('to','Đến ngày','date')])

    @app.post('/access/check-in')
    @login_required
    def access_checkin():
        def do():
            room=positive_id(request.form.get('room_id'),'Phòng')
            reason=limited_text(request.form.get('purpose'),'Mục đích',255)
            return db.procedure('sp_app_checkin',[g.user['personnel_id'],room,reason],out=True)
        response,error=_handle_write(do,'Đã vào phòng, mã lượt #{id}.','access')
        if response: return response
        flash(error,'error')
        return redirect(url_for('access'))

    @app.post('/access/<int:access_id>/check-out')
    @login_required
    def access_checkout(access_id):
        # No form-supplied personnel_id or client event timestamp.
        def do():
            db.procedure('sp_app_checkout',[g.user['personnel_id'],access_id],out=False)
            return access_id
        response,error=_handle_write(do,'Đã ghi nhận rời phòng, mã lượt #{id}.','access')
        if response: return response
        flash(error,'error')
        return redirect(url_for('access'))

    @app.get('/projects')
    @login_required
    def projects():
        search=request.args.get('q','').strip()[:100]
        from_day,to_day = date_window(request.args)
        conditions=[]; params=[]
        if search:
            conditions.append('(p.project_name LIKE %s OR pi.full_name LIKE %s)')
            params.extend(('%'+search+'%',)*2)
        # Overlap with the chosen calendar range, including open-ended projects.
        if from_day:
            conditions.append('(p.end_date IS NULL OR p.end_date >= %s)'); params.append(from_day)
        if to_day:
            conditions.append('p.start_date <= %s'); params.append(to_day)
        from_sql='FROM research_project p JOIN personnel pi ON pi.personnel_id=p.pi_personnel_id'
        if conditions:
            from_sql+=' WHERE '+' AND '.join(conditions)
        return _listing('Đề tài nghiên cứu','Đề tài, giảng viên chủ nhiệm, ngân sách và thành viên.',
            from_sql,tuple(params),'''SELECT p.project_id,p.project_name,p.start_date,p.end_date,
            p.total_budget,p.funding_source,pi.full_name AS pi_name,
            (SELECT COUNT(*) FROM project_member pm WHERE pm.project_id=p.project_id) AS member_count''',
            'ORDER BY p.project_id',
            [C('project_id','Mã'),C('project_name','Đề tài'),C('pi_name','Chủ nhiệm'),
             C('start_date','Ngày bắt đầu'),C('end_date','Ngày kết thúc'),
             C('total_budget','Ngân sách (VND)'),C('member_count','Thành viên')],
            filters=[F('q','Tìm đề tài/PI'),F('from','Hoạt động từ ngày','date'),
                     F('to','Hoạt động đến ngày','date')],
            decorate=lambda r: r.update(detail_url=url_for('project_detail',project_id=r['project_id'])))

    @app.get('/projects/<int:project_id>')
    @login_required
    def project_detail(project_id):
        p=_get_or_404('''SELECT p.*,pi.full_name AS pi_name, f.faculty_code
               FROM research_project p JOIN personnel pi ON pi.personnel_id=p.pi_personnel_id
               JOIN faculty f ON f.personnel_id=p.pi_personnel_id WHERE p.project_id=%s''',(project_id,))
        members=db.fetch_all('''SELECT pm.personnel_id,person.full_name,pm.project_role,pm.enroll_date
             FROM project_member pm JOIN personnel person ON person.personnel_id=pm.personnel_id
             WHERE pm.project_id=%s ORDER BY person.full_name''',(project_id,))
        allocations=db.fetch_all('''SELECT pa.allocation_id,a.asset_name,a.asset_type,
            pa.allocated_qty,CASE WHEN a.asset_type='EQUIPMENT' THEN 'máy' ELSE c.unit END AS unit,pa.allocated_at FROM project_asset_allocation pa
            JOIN lab_asset a ON a.asset_id=pa.asset_id
            LEFT JOIN chemical_material c ON c.asset_id=pa.asset_id
            WHERE pa.project_id=%s ORDER BY pa.allocated_at DESC LIMIT 40''',(project_id,))
        restrict='' if g.user['operator'] else ' AND b.personnel_id=%s'
        booking_params=(project_id,) if g.user['operator'] else (project_id,g.user['personnel_id'])
        bookings=db.fetch_all('''SELECT b.booking_id,a.asset_name,b.start_time,b.end_time FROM equipment_booking b
            JOIN lab_asset a ON a.asset_id=b.asset_id WHERE b.project_id=%s'''+restrict+
            ' ORDER BY b.start_time DESC LIMIT 25',booking_params)
        restrict_d='' if g.user['operator'] else ' AND d.personnel_id=%s'
        dispense_params=(project_id,) if g.user['operator'] else (project_id,g.user['personnel_id'])
        dispenses=db.fetch_all('''SELECT d.dispense_id,a.asset_name,d.quantity,c.unit,d.dispense_date
          FROM chemical_dispense_log d JOIN lab_asset a ON a.asset_id=d.asset_id
          JOIN chemical_material c ON c.asset_id=d.asset_id WHERE d.project_id=%s'''+restrict_d+
            ' ORDER BY d.dispense_date DESC LIMIT 25',dispense_params)
        return _detail(p['project_name'],'Chi tiết đề tài và các quan hệ nghiệp vụ liên quan.',
             [('Mã đề tài',p['project_id']),('Chủ nhiệm',p['pi_name']),('Mã giảng viên',p['faculty_code']),
              ('Bắt đầu',p['start_date']),('Kết thúc',p['end_date']),
              ('Ngân sách (VND)',present(p['total_budget'],'total_budget')),('Nguồn tài trợ',p['funding_source'])],
             sections=[_section('Thành viên',[C('full_name','Họ tên'),C('project_role','Vai trò trong đề tài'),C('enroll_date','Ngày tham gia')],members),
              _section('Phân bổ tài sản',[C('allocation_id','Mã'),C('asset_name','Tài sản'),C('asset_type','Loại'),
               C('allocated_qty','Số lượng'),C('unit','Đơn vị'),C('allocated_at','Ngày phân bổ')],allocations),
              _section('Lịch sử đặt thiết bị được phép xem',[C('booking_id','Mã'),C('asset_name','Thiết bị'),C('start_time','Bắt đầu'),C('end_time','Kết thúc')],bookings),
              _section('Lịch sử cấp phát được phép xem',[C('dispense_id','Mã'),C('asset_name','Hóa chất'),
               C('quantity','Lượng'),C('unit','Đơn vị'),C('dispense_date','Thời gian')],dispenses)],
            note='Vai trò trong đề tài không đồng nghĩa với quyền sử dụng ứng dụng. Các tổng lượng hóa chất không được cộng giữa những đơn vị khác nhau.')

    @app.get('/profile')
    @login_required
    def profile():
        if g.user.get('operator_account_id'):
            return _detail('Tài khoản quản trị hệ thống','Tài khoản bàn giao vận hành, tách biệt với hồ sơ nhân sự và đề tài.',
                [('Tên tài khoản',g.user['full_name']),('Email',g.user['email']),('Quyền','Điều hành hệ thống'),
                 ('Phạm vi','Quản lý toàn hệ thống; không có lịch, đề tài hoặc chứng chỉ cá nhân.')])
        from webapp.notifications import seen_registration
        seen_registration()
        return _person_detail(g.user['personnel_id'], profile=True)

    def _person_detail(personnel_id, profile=False):
        pid=g.user['personnel_id']
        if not profile and not g.user['operator']:
            abort(403)
        if profile and personnel_id!=pid:
            abort(403)
        p=_get_or_404('''SELECT p.personnel_id,p.full_name,p.email,p.phone,
            s.student_code,s.major,s.gpa,f.faculty_code,f.academic_rank,
            t.staff_code,t.shift,co.personnel_id AS collaborator_id,co.home_institution FROM personnel p
            LEFT JOIN student s ON s.personnel_id=p.personnel_id
            LEFT JOIN faculty f ON f.personnel_id=p.personnel_id
            LEFT JOIN lab_technician t ON t.personnel_id=p.personnel_id
            LEFT JOIN collaborator co ON co.personnel_id=p.personnel_id
            WHERE p.personnel_id=%s''',(personnel_id,))
        certificates=db.fetch_all('''SELECT sc.cert_name,sc.hazard_level,pc.issue_date,pc.expiry_date,
          CASE WHEN pc.issue_date>CURRENT_DATE() THEN 'Chưa hiệu lực'
          WHEN pc.expiry_date<CURRENT_DATE() THEN 'Đã hết hạn'
          ELSE 'Còn hiệu lực' END AS certificate_status
          FROM personnel_certificate pc JOIN safety_certificate sc ON sc.cert_id=pc.cert_id
          WHERE pc.personnel_id=%s ORDER BY sc.hazard_level DESC,pc.expiry_date''',(personnel_id,))
        roles=db.fetch_all('SELECT role_code FROM app_account_role WHERE personnel_id=%s',(personnel_id,)) if profile else []
        props=[('Mã nhân sự',p['personnel_id']),('Họ và tên',p['full_name']),('Email',p['email']),('Số điện thoại',p['phone'])]
        if p.get('student_code'):props.extend([('MSSV',p['student_code']),('Ngành học',p['major']),('GPA',p['gpa'])])
        if p.get('faculty_code'):props.extend([('Mã giảng viên',p['faculty_code']),('Học hàm/học vị',p['academic_rank'])])
        if p.get('staff_code'):props.extend([('Mã kỹ thuật viên',p['staff_code']),('Ca trực',p['shift'])])
        if p.get('collaborator_id'):props.extend([('Loại nhân sự','Cộng tác viên ngoài trường'),('Trường/đơn vị',p.get('home_institution') or 'Chưa khai báo')])
        if profile:
            props.append(('Quyền ứng dụng',', '.join(present(x['role_code']) for x in roles) or 'Chưa phân quyền'))
        return _detail('Hồ sơ của tôi' if profile else p['full_name'],
            'Thông tin nhân sự và chứng chỉ an toàn theo dữ liệu thực.',props,
            sections=[_section('Chứng chỉ an toàn',[C('cert_name','Chứng chỉ'),
                C('hazard_level','Cấp nguy hiểm'),C('issue_date','Ngày cấp'),
                C('expiry_date','Ngày hết hạn'),C('certificate_status','Trạng thái')],certificates)],
            actions=[{'label':'Gửi cập nhật chứng chỉ','url':url_for('certificates.index')}] if profile else [],
            note='Cộng tác viên ngoài trường không mang mã SV/GV/KT. Chứng chỉ cập nhật cần ADMIN xác nhận.')

    @app.get('/personnel')
    @operator_required
    def personnel():
        search=request.args.get('q','').strip()[:100]
        cond='''WHERE (p.full_name LIKE %s OR p.email LIKE %s OR CONVERT(s.student_code USING utf8mb4) COLLATE utf8mb4_unicode_ci LIKE %s
                    OR f.faculty_code LIKE %s OR t.staff_code LIKE %s)''' if search else ''
        params=('%'+search+'%',)*5 if search else ()
        from_sql='''FROM personnel p LEFT JOIN student s ON s.personnel_id=p.personnel_id
          LEFT JOIN faculty f ON f.personnel_id=p.personnel_id
          LEFT JOIN lab_technician t ON t.personnel_id=p.personnel_id LEFT JOIN collaborator co ON co.personnel_id=p.personnel_id '''+cond
        return _listing('Nhân sự & chứng chỉ', 'Tra cứu nhân sự, nhiều loại vai trò và giấy chứng nhận.',
           from_sql,params,'''SELECT p.personnel_id,p.full_name,p.email,p.phone,
              s.student_code,f.faculty_code,t.staff_code,CASE WHEN co.personnel_id IS NOT NULL THEN 'Cộng tác viên ngoài trường' ELSE 'Nhân sự trong trường' END AS personnel_type''','ORDER BY p.personnel_id',
           [C('personnel_id','Mã'),C('full_name','Họ tên'),C('email','Email'),
            C('student_code','MSSV'),C('faculty_code','Mã GV'),C('staff_code','Mã KTV'),C('personnel_type','Phân loại')],
           filters=[F('q','Tìm người / mã')],
           decorate=lambda r:r.update(detail_url=url_for('personnel_detail',personnel_id=r['personnel_id'])))

    @app.get('/personnel/<int:personnel_id>')
    @operator_required
    def personnel_detail(personnel_id):
        return _person_detail(personnel_id)

    @app.route('/allocations',methods=['GET','POST'])
    @operator_required
    def allocations():
        # Allocation history and form; insertion is not stock movement.
        fields=[F('project_id','Đề tài','select',required=True,options=[('','Chọn đề tài')]+_project_options()),
                F('asset_id','Tài sản','select',required=True,options=[('','Chọn tài sản')]+_assets_options()),
                F('allocated_qty','Số lượng phân bổ','number',required=True,
                  help='Thiết bị: 1 máy/mã; hóa chất: lượng theo đơn vị lô. Không trừ tồn kho.')]
        values=_value_map(fields)
        if request.method=='POST':
            def do():
                pid=positive_id(values['project_id'],'Đề tài')
                aid=positive_id(values['asset_id'],'Tài sản')
                qty=quantity(values['allocated_qty'])
                asset=db.fetch_one('SELECT asset_type FROM lab_asset WHERE asset_id=%s',(aid,))
                if not asset:raise InputError('Tài sản không tồn tại.')
                if asset['asset_type']=='EQUIPMENT' and qty!=1:
                    raise InputError('Mỗi mã thiết bị là một máy: số lượng phân bổ phải bằng 1.')
                return db.insert('''INSERT INTO project_asset_allocation
                    (project_id,asset_id,allocated_qty) VALUES (%s,%s,%s)''',(pid,aid,qty))
            response,error=_handle_write(do,'Đã phân bổ tài sản, mã #{id}.','allocations')
            if response: return response
            flash(error,'error')
        project=_try_filter_id('project')
        asset_filter=_try_filter_id('asset')
        from_day,to_day=date_window(request.args)
        conds=[]; params=[]
        if project:
            conds.append('pa.project_id=%s'); params.append(project)
        if asset_filter:
            conds.append('pa.asset_id=%s'); params.append(asset_filter)
        if from_day:
            conds.append('pa.allocated_at >= %s'); params.append(datetime.combine(from_day,datetime.min.time()))
        if to_day:
            conds.append('pa.allocated_at <= %s'); params.append(inclusive_day_end(to_day))
        cond='WHERE '+' AND '.join(conds) if conds else ''
        params=tuple(params)
        page=page_number(request.args.get('page'))
        from_sql='''FROM project_asset_allocation pa JOIN research_project p ON p.project_id=pa.project_id
              JOIN lab_asset a ON a.asset_id=pa.asset_id
              LEFT JOIN chemical_material c ON c.asset_id=pa.asset_id '''+cond
        total=int(db.scalar('SELECT COUNT(*) AS n '+from_sql,params))
        rows=db.fetch_all('''SELECT pa.allocation_id,p.project_name,a.asset_name,a.asset_type,
           pa.allocated_qty,CASE WHEN a.asset_type='EQUIPMENT' THEN 'máy' ELSE c.unit END AS unit,pa.allocated_at '''+from_sql+
           ' ORDER BY pa.allocated_at DESC,pa.allocation_id DESC LIMIT %s OFFSET %s',
           (*params,PAGE_SIZE,(page-1)*PAGE_SIZE))
        grouped=db.fetch_all("""SELECT p.project_id,p.project_name,a.asset_id,a.asset_name,a.asset_type,
            COUNT(*) AS allocation_count,
            CASE WHEN a.asset_type='EQUIPMENT' THEN MAX(pa.allocated_qty) ELSE SUM(pa.allocated_qty) END AS total_allocated_qty,
            MAX(pa.allocated_at) AS last_allocated_at,
            CASE WHEN a.asset_type='EQUIPMENT' THEN 'máy' ELSE c.unit END AS unit """+from_sql+
            ' GROUP BY p.project_id,p.project_name,a.asset_id,a.asset_name,a.asset_type,c.unit ORDER BY p.project_id,a.asset_type,a.asset_name,a.asset_id',params)
        allocation_projects={}
        for item in grouped:
            group=allocation_projects.setdefault(item['project_id'],{'project_id':item['project_id'],'project_name':item['project_name'],'equipment':[],'chemicals':[]})
            group['equipment' if item['asset_type']=='EQUIPMENT' else 'chemicals'].append(item)
        return render_template('operations.html',title='Phân bổ tài sản',
            description='Phân bổ tài sản cho đề tài; không phải cấp phát hóa chất và không trừ tồn kho.',
            fields=fields,values=values,submit='Ghi nhận phân bổ',
            rows=rows,total=total,page=page,pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE),
            columns=[C('allocation_id','Mã'),C('project_name','Đề tài'),C('asset_name','Tài sản'),
                C('asset_type','Loại'),C('allocated_qty','Số lượng'),C('unit','Đơn vị'),
                C('allocated_at','Thời điểm')],
            filters=[F('project','Lọc đề tài','select',options=[('','Tất cả')]+_project_options()),
                     F('asset','Tài sản','select',options=[('','Tất cả')]+_assets_options()),
                     F('from','Từ ngày','date'),F('to','Đến ngày','date')],
            allocation_projects=list(allocation_projects.values()),grouped=grouped,grouped_columns=[C('project_name','Đề tài'),C('asset_name','Tài sản'),
                C('allocation_count','Lần'),C('total_allocated_qty','Số lượng (trên một tài sản)'),C('unit','Đơn vị')])

    @app.route('/maintenance',methods=['GET','POST'])
    @operator_required
    def maintenance():
        fields=[F('asset_id','Thiết bị','select',required=True,options=[('','Chọn thiết bị')]+_equipment_options()),
                F('technician_id','Kỹ thuật viên','select',required=True,options=[('','Chọn kỹ thuật viên')]+_technician_options()),
                F('maint_date','Thời điểm bảo trì','datetime-local',required=True),
                F('description','Nội dung bảo trì','textarea',help='Tối đa 500 ký tự')]
        values=_value_map(fields,{'maint_date':datetime.now().strftime('%Y-%m-%dT%H:%M')})
        if request.method=='POST':
            def do():
                aid=positive_id(values['asset_id'],'Thiết bị')
                tid=positive_id(values['technician_id'],'Kỹ thuật viên')
                when=local_datetime(values['maint_date'],'Thời gian bảo trì')
                desc=limited_text(values.get('description'),'Nội dung bảo trì',500)
                return db.insert('''INSERT INTO maintenance_log
                   (asset_id,technician_id,maint_date,description) VALUES (%s,%s,%s,%s)''',
                   (aid,tid,when,desc))
            response,error=_handle_write(do,'Đã ghi nhật ký bảo trì #{id}.','maintenance')
            if response: return response
            flash(error,'error')
        asset=_try_filter_id('asset')
        technician=_try_filter_id('technician')
        from_day,to_day=date_window(request.args)
        conds=[]; params=[]
        if asset:
            conds.append('m.asset_id=%s'); params.append(asset)
        if technician:
            conds.append('m.technician_id=%s'); params.append(technician)
        if from_day:
            conds.append('m.maint_date >= %s'); params.append(datetime.combine(from_day,datetime.min.time()))
        if to_day:
            conds.append('m.maint_date <= %s'); params.append(inclusive_day_end(to_day))
        cond='WHERE '+' AND '.join(conds) if conds else ''
        params=tuple(params)
        page=page_number(request.args.get('page'))
        from_sql='''FROM maintenance_log m JOIN equipment e ON e.asset_id=m.asset_id
          JOIN lab_asset a ON a.asset_id=m.asset_id JOIN personnel p ON p.personnel_id=m.technician_id '''+cond
        total=int(db.scalar('SELECT COUNT(*) AS n '+from_sql,params))
        rows=db.fetch_all('''SELECT m.maint_id,a.asset_name,e.serial_number,p.full_name AS technician,
           m.maint_date,m.description '''+from_sql+
           ' ORDER BY m.maint_date DESC,m.maint_id DESC LIMIT %s OFFSET %s',
           (*params,PAGE_SIZE,(page-1)*PAGE_SIZE))
        return render_template('operations.html',title='Bảo trì thiết bị',
            description='Ghi nhật ký với kỹ thuật viên hợp lệ. Không tự đổi trạng thái tài sản.',
            fields=fields,values=values,submit='Lưu nhật ký bảo trì',rows=rows,total=total,
            page=page,pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE),
            columns=[C('maint_id','Mã'),C('asset_name','Thiết bị'),C('serial_number','Sê-ri'),
             C('technician','Kỹ thuật viên'),C('maint_date','Thời gian'),C('description','Nội dung')],
            filters=[F('asset','Thiết bị','select',options=[('','Tất cả')]+_equipment_options()),
                     F('technician','Kỹ thuật viên','select',options=[('','Tất cả')]+_technician_options()),
                     F('from','Từ ngày','date'),F('to','Đến ngày','date')])

    @app.get('/reports')
    @operator_required
    def reports():
        return render_template('report_index.html',title='Báo cáo SQL',reports=REPORTS)

    @app.get('/reports/<key>')
    @operator_required
    def report_detail(key):
        if key not in REPORTS:
            abort(404)
        title,sql,params,filter_type,applied=get_report(key,request.args)
        # ORDER BY is fixed inside the chosen SQL, never submitted by browser.
        total=int(db.scalar('SELECT COUNT(*) AS n FROM ('+sql+') AS report_count',params))
        page=page_number(request.args.get('page'))
        rows=db.fetch_all(sql+' LIMIT %s OFFSET %s',(*params,PAGE_SIZE,(page-1)*PAGE_SIZE))
        # Labels are only UI metadata, not SQL source.
        label_map={
          'asset_id':'Mã tài sản','room_id':'Mã phòng','project_id':'Mã đề tài',
          'booking_id':'Mã lịch','personnel_id':'Mã nhân sự','project_name':'Đề tài',
          'asset_name':'Tài sản','full_name':'Họ tên','room_name':'Phòng',
          'email':'Email','status':'Trạng thái','unit':'Đơn vị','expiry_date':'Hạn dùng',
          'quantity':'Lượng','start_time':'Bắt đầu','end_time':'Kết thúc',
          'purpose':'Mục đích','hazard_level':'Cấp nguy hiểm','booking_status':'Trạng thái lịch','total_budget':'Ngân sách (VND)',
          'stock_qty':'Tồn kho','asset_type':'Loại tài sản', 'dispense_count':'Số lần cấp phát',
          'total_dispensed':'Tổng cấp phát', 'last_maintenance_date':'Bảo trì gần nhất',
          'technician_name':'Kỹ thuật viên', 'last_entry_time':'Lần vào gần nhất',
          'total_minutes':'Số phút đã đóng lượt','access_count':'Số lượt',
          'member_count':'Số thành viên','principal_investigator':'Giảng viên chủ nhiệm',
          'max_valid_hazard_level':'Cấp hợp lệ tối đa',
          'active_certificate_count':'Chứng chỉ còn hiệu lực',
          'distinct_allocated_assets':'Tài sản khác nhau',
          'faculty_code':'Mã giảng viên', 'project_role':'Vai trò trong đề tài',
          'enroll_date':'Ngày tham gia', 'serial_number':'Số sê-ri',
          'booked_by':'Người đặt', 'safety_category':'Cấp an toàn phòng',
          'equipment_count':'Số thiết bị','chemical_count':'Số hóa chất',
          'asset_count':'Số tài sản','last_maintenance':'Bảo trì gần nhất',
          'description':'Nội dung','allocation_id':'Mã phân bổ',
          'expiry_status':'Trạng thái hạn','days_to_expiry':'Số ngày còn lại',
          'total_allocated_qty':'Tổng (cùng tài sản)','allocation_count':'Số lần phân bổ',
          'last_allocated_at':'Phân bổ mới nhất',
        }
        keys=list(rows[0]) if rows else []
        cols=[C(k,label_map.get(k,k.replace('_',' ').capitalize())) for k in keys]
        return render_template('report_detail.html',title=f'{key} · {title}',
            report_key=key,description='Kết quả truy vấn trực tiếp MySQL.',
            rows=rows,columns=cols,filter_type=filter_type,applied=applied,
            total=total,page=page,pages=max(1,(total+PAGE_SIZE-1)//PAGE_SIZE))

    from webapp.registration import bp as registration_blueprint
    app.register_blueprint(registration_blueprint)
    from webapp.certificates import bp as certificates_blueprint
    app.register_blueprint(certificates_blueprint)
    from webapp.notifications import bp as notifications_blueprint
    app.register_blueprint(notifications_blueprint)
    return app


# Supports `python -m flask --app webapp/app.py run` and VS Code's module launch.
app = create_app()
