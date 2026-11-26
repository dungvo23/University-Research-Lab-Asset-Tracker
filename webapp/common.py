"""Pure input validation, result presentation, and safe error translation."""
from datetime import datetime, date
from decimal import Decimal
import re
from urllib.parse import urlencode


class InputError(ValueError):
    pass


def positive_id(value, label='Mã', optional=False):
    text = str(value or '').strip()
    if optional and not text:
        return None
    if not re.fullmatch(r'[1-9][0-9]{0,9}', text) or int(text) > 2147483647:
        raise InputError(f'{label} không hợp lệ.')
    return int(text)


def quantity(value, label='Số lượng'):
    text = str(value or '').strip()
    if not re.fullmatch(r'(?:0|[1-9][0-9]{0,8})(?:\.[0-9]{1,3})?', text):
        raise InputError(f'{label} phải là số dương với tối đa 3 chữ số thập phân.')
    val = Decimal(text)
    if val <= 0:
        raise InputError(f'{label} phải lớn hơn 0.')
    return val


def limited_text(value, label='Nội dung', max_length=255, required=False):
    val = str(value or '').strip()
    if len(val) > max_length or (required and not val):
        raise InputError(f'{label} phải có tối đa {max_length} ký tự' + (' và không được trống.' if required else '.'))
    return val or None


def local_datetime(value, label='Thời gian'):
    val = str(value or '').strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', val):
        raise InputError(f'{label} phải có ngày và giờ hợp lệ.')
    try:
        return datetime.strptime(val, '%Y-%m-%dT%H:%M')
    except ValueError as exc:
        raise InputError(f'{label} không hợp lệ.') from exc


def optional_day(value, label='Ngày'):
    val = str(value or '').strip()
    if not val:
        return None
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', val):
        raise InputError(f'{label} không hợp lệ.')
    try:
        return date.fromisoformat(val)
    except ValueError as exc:
        raise InputError(f'{label} không hợp lệ.') from exc


def date_window(args):
    """Parse inclusive date filters; reject reversed ranges before querying MySQL."""
    day_from = optional_day(args.get('from'), 'Từ ngày')
    day_to = optional_day(args.get('to'), 'Đến ngày')
    if day_from is not None and day_to is not None and day_from > day_to:
        raise InputError('Ngày bắt đầu không được sau ngày kết thúc.')
    return day_from, day_to


def inclusive_day_end(day):
    """Index-friendly inclusive upper bound, safe even for 9999-12-31."""
    return datetime.combine(day, datetime.max.time())


def choice(value, allowed, label='Bộ lọc'):
    if value and value not in allowed:
        raise InputError(f'{label} không hợp lệ.')
    return value or ''


def page_number(raw):
    try:
        p = int(raw)
    except (ValueError, TypeError):
        return 1
    return max(1, min(p, 100000))


def filters_page_url(n):
    from flask import request
    params = request.args.to_dict(flat=True)
    params['page'] = str(n)
    return request.path + '?' + urlencode(params)


def present(value, key=''):
    if value is None:
        return '—'
    if key == 'total_budget' and isinstance(value, (Decimal, int, float)):
        amount = Decimal(str(value))
        places = 0 if amount == amount.to_integral_value() else 2
        formatted = format(amount, ',.' + str(places) + 'f')
        return formatted.translate(str.maketrans({',': '.', '.': ','})) + ' VND'
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    if isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    if key in ('allocated_qty','total_allocated_qty') and isinstance(value,(Decimal,int,float)):
        amount=Decimal(str(value))
        return format(amount,'f').rstrip('0').rstrip('.') if '.' in format(amount,'f') else str(amount)
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, bool):
        return 'Có' if value else 'Không'
    if isinstance(value, (int, float)):
        return str(value)
    labels = {'AVAILABLE': 'Sẵn sàng', 'IN_USE': 'Đang sử dụng',
              'MAINTENANCE': 'Đang bảo trì', 'RETIRED': 'Ngừng sử dụng',
              'EQUIPMENT': 'Thiết bị', 'CHEMICAL': 'Hóa chất',
              'EXPIRED': 'Đã hết hạn', 'EXPIRING_WITHIN_30_DAYS': 'Sắp hết hạn',
              'PENDING':'Chờ duyệt','APPROVED':'Đã duyệt','REJECTED':'Từ chối',
              'MEMBER': 'Thành viên', 'OPERATOR': 'Điều hành'}
    return labels.get(str(value), str(value))


BUSINESS_MESSAGES = [
    ('ALLOCATION_EQUIPMENT_ONE','Mỗi mã thiết bị là một máy: số lượng phân bổ phải bằng 1.'),
    ('BOOKING_PAST_TIME','Thời gian bắt đầu phải sau thời điểm hiện tại (giờ Việt Nam).'),
    ('BOOKING_QUARTER_HOUR','Chỉ được đặt phút 00, 15, 30 hoặc 45.'),
    ('BOOKING_NOT_PENDING','Lịch đã được xử lý hoặc không còn chờ duyệt.'),
    ('BOOKING_ALREADY_STARTED','Không thể duyệt lịch đã đến giờ bắt đầu. Hãy từ chối và yêu cầu đặt lại.'),
    ('BOOKING_INVALID_DECISION','Vui lòng nhập lý do khi từ chối lịch.'),
    ('Overlapping equipment booking', 'Thiết bị đã có lịch trong khoảng thời gian này.'),
    ('Invalid booking time interval', 'Thời gian kết thúc phải sau thời gian bắt đầu.'),
    ('No matching valid safety certificate', 'Người nhận chưa có chứng chỉ an toàn hợp lệ.'),
    ('Insufficient chemical stock', 'Số lượng yêu cầu vượt quá tồn kho hiện tại.'),
    ('Chemical has expired', 'Hóa chất đã hết hạn, không thể cấp phát.'),
    ('Unsafe lab access', 'Bạn chưa đáp ứng điều kiện chứng chỉ để vào phòng này.'),
    ('ACCESS_OPEN', 'Bạn đang có một lượt vào phòng chưa kết thúc.'),
    ('ACCESS_NOT_OPEN', 'Lượt truy cập không còn mở hoặc không thuộc tài khoản của bạn.'),
    ('Dispense quantity must be positive', 'Số lượng cấp phát phải lớn hơn 0.'),
]


def safe_db_message(error):
    # Deliberately reveal only known trigger messages. Raw SQL and account details
    # must not reach the browser.
    original = str(error)
    for pattern, message in BUSINESS_MESSAGES:
        if pattern in original:
            return message
    code = error.args[0] if getattr(error, 'args', None) else None
    if code == 1452:
        return 'Dữ liệu liên kết không tồn tại hoặc đã thay đổi. Vui lòng tải lại.'
    if code in (1062, 3819):
        return 'Dữ liệu không hợp lệ hoặc bị trùng theo ràng buộc hệ thống.'
    if code == 1406:
        return 'Nội dung nhập vượt quá độ dài cho phép.'
    if code in (1142, 1370):
        return 'Tài khoản kết nối chưa được cấp quyền cho thao tác này.'
    return 'Cơ sở dữ liệu không chấp nhận thao tác. Kiểm tra dữ liệu và thử lại.'
