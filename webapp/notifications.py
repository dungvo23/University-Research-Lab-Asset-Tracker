"""Attention badges: pending admin work and unseen results for the owner only."""
from flask import Blueprint, g, jsonify
from webapp import db
from webapp.auth import login_required

bp = Blueprint('notifications', __name__)


def counts():
    if not getattr(g, 'user', None): return {}
    if hasattr(g, '_notice_counts'): return g._notice_counts
    if g.user.get('operator_account_id'):
        result = {
            'bookings': db.scalar("SELECT COUNT(*) AS n FROM equipment_booking WHERE booking_status='PENDING'"),
            'certificates.index': db.scalar("SELECT COUNT(*) AS n FROM certificate_update_request WHERE status='PENDING'"),
            'registration.requests_list': db.scalar("SELECT COUNT(*) AS n FROM app_registration_request WHERE status='PENDING'")}
    else:
        pid = g.user['personnel_id']
        result = {
            'bookings': db.scalar('''SELECT COUNT(*) AS n FROM equipment_booking b
                LEFT JOIN notification_seen ns ON ns.personnel_id=b.personnel_id
                  AND ns.notification_kind='BOOKING' AND ns.item_id=b.booking_id
                WHERE b.personnel_id=%s AND b.booking_status IN ('APPROVED','REJECTED')
                  AND b.reviewed_at IS NOT NULL AND ns.item_id IS NULL''', (pid,)),
            'certificates.index': db.scalar('''SELECT COUNT(*) AS n FROM certificate_update_request r
                LEFT JOIN notification_seen ns ON ns.personnel_id=r.personnel_id
                  AND ns.notification_kind='CERTIFICATE' AND ns.item_id=r.request_id
                WHERE r.personnel_id=%s AND r.status IN ('APPROVED','REJECTED') AND ns.item_id IS NULL''', (pid,)),
            'profile': db.scalar('''SELECT COUNT(*) AS n FROM app_registration_request r
                LEFT JOIN notification_seen ns ON ns.personnel_id=%s
                  AND ns.notification_kind='REGISTRATION' AND ns.item_id=r.request_id
                WHERE r.email=%s AND r.status='APPROVED' AND ns.item_id IS NULL''', (pid, g.user['email']))}
    g._notice_counts = {key: int(value or 0) for key, value in result.items()}
    return g._notice_counts


def seen(kind, item_ids):
    if not getattr(g, 'user', None) or g.user.get('operator_account_id'): return
    # IDs originate from the current user's scoped result list, never form input.
    sources = {
        'BOOKING': ("equipment_booking", "booking_id", "booking_status IN ('APPROVED','REJECTED') AND reviewed_at IS NOT NULL"),
        'CERTIFICATE': ("certificate_update_request", "request_id", "status IN ('APPROVED','REJECTED')"),
    }
    if kind not in sources: raise ValueError('Unknown result type')
    ids = list(dict.fromkeys(int(value) for value in item_ids))
    if not ids: return
    table, key, condition = sources[kind]
    placeholders = ','.join(['%s'] * len(ids))
    db.insert(f'''INSERT IGNORE INTO notification_seen(personnel_id,notification_kind,item_id)
        SELECT personnel_id,%s,{key} FROM {table}
        WHERE personnel_id=%s AND {condition} AND {key} IN ({placeholders})''',
        (kind, g.user['personnel_id'], *ids))
    g.pop('_notice_counts', None)


def seen_registration():
    if not getattr(g, 'user', None) or g.user.get('operator_account_id'): return
    db.insert('''INSERT IGNORE INTO notification_seen(personnel_id,notification_kind,item_id)
        SELECT %s,'REGISTRATION',request_id FROM app_registration_request
        WHERE email=%s AND status='APPROVED' ''', (g.user['personnel_id'], g.user['email']))
    g.pop('_notice_counts', None)


@bp.get('/notifications/status')
@login_required
def status():
    return jsonify(counts=counts())
