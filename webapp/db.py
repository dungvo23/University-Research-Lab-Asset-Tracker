"""MySQL access for the limited lab_app account. No schema changes on startup."""
from contextlib import contextmanager
from flask import current_app
import pymysql
from pymysql.cursors import DictCursor


class DatabaseUnavailable(Exception):
    """The service account cannot currently connect to MySQL."""


UNAVAILABLE = {1045, 1044, 1049, 2002, 2003, 2006, 2013, 2055}


def classify_db_error(error):
    if isinstance(error, pymysql.MySQLError) and error.args:
        try:
            if int(error.args[0]) in UNAVAILABLE:
                return DatabaseUnavailable()
        except (ValueError, TypeError):
            pass
    return error


def _connect():
    cfg = current_app.config
    try:
        return pymysql.connect(
            host=cfg['DB_HOST'], port=cfg['DB_PORT'],
            user=cfg['DB_USER'], password=cfg['DB_PASSWORD'],
            database=cfg['DB_NAME'], charset='utf8mb4',
            cursorclass=DictCursor, autocommit=False,
            connect_timeout=3, read_timeout=10, write_timeout=10,
            # DATETIME is local wall-clock data; do not convert existing values to UTC.
            init_command="SET time_zone = '+07:00'",
        )
    except pymysql.MySQLError as exc:
        raise classify_db_error(exc) from None


@contextmanager
def connection():
    cn = _connect()
    try:
        yield cn
    except pymysql.MySQLError as exc:
        try:
            cn.rollback()
        finally:
            raise classify_db_error(exc) from None
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()


def fetch_all(sql, params=()):
    with connection() as cn:
        with cn.cursor() as cur:
            cur.execute(sql, params)
            result = cur.fetchall()
        # read-only transaction ends on connection close
        return list(result)


def fetch_one(sql, params=()):
    with connection() as cn:
        with cn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def scalar(sql, params=(), key='n'):
    result = fetch_one(sql, params)
    return result[key] if result else 0


def insert(sql, params=()):
    """Only for tables on which lab_app has INSERT, explicit commit."""
    with connection() as cn:
        with cn.cursor() as cur:
            cur.execute(sql, params)
            new_id = cur.lastrowid
        cn.commit()
        return new_id


# These exact names are the only stored routines lab_app can call.
PROCEDURES = {
    'sp_book_equipment': 6,
    'sp_dispense_chemical': 5,
    'sp_app_checkin': 3,
    'sp_app_checkout': 2,
    'sp_review_registration': 4,
    'sp_create_chemical': 7,
    'sp_receive_chemical': 6,
    'sp_review_booking': 4,
    'sp_review_certificate': 4,
}


def procedure(name, args, out=False):
    """CALL using an OUT session variable; consume result sets before SELECT.

    Booking, dispensing and checkin own transactions inside MySQL. Checkout
    performs a direct UPDATE in its procedure and must be committed by caller.
    """
    if name not in PROCEDURES or len(args) != PROCEDURES[name]:
        raise ValueError('Unsupported procedure signature')
    if out and name in ('sp_app_checkout', 'sp_review_registration', 'sp_review_booking', 'sp_review_certificate'):
        raise ValueError('Checkout does not have an OUT argument')
    if not out and name not in ('sp_app_checkout', 'sp_review_registration', 'sp_review_booking', 'sp_review_certificate'):
        raise ValueError('This procedure requires an OUT argument')
    with connection() as cn:
        with cn.cursor() as cur:
            if out:
                cur.execute('SET @_int1313_out_id = NULL')
            placeholders = ','.join(['%s'] * len(args) + (['@_int1313_out_id'] if out else []))
            # name is a constant allowlisted above, not an HTTP input.
            cur.execute(f'CALL {name}({placeholders})', tuple(args))
            # PyMySQL can otherwise raise "commands out of sync" on the next SELECT.
            while cur.nextset():
                pass
            result = None
            if out:
                cur.execute('SELECT @_int1313_out_id AS new_id')
                row = cur.fetchone()
                result = row['new_id'] if row else None
                if result is None:
                    raise RuntimeError('Procedure did not return an ID')
        cn.commit()
        return result
