"""Bounded, read-only SBO_AI hours analysis; all tiles reuse one cached union."""
from dashboard.access import hr_scope, unit_allowed
from collections import Counter, OrderedDict
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from threading import Lock
import json

from flask import abort, g, render_template, request

from dashboard.attendance import AttendanceUnavailable, PAKISTAN, QUERY_DIR, SharedAttendanceCache
from dashboard.config import build_connection_string

PREFLIGHT = (QUERY_DIR / 'hr_hours_preflight.sql').read_text(encoding='utf-8')
RECORDS = (QUERY_DIR / 'hr_hours_records.sql').read_text(encoding='utf-8')
ZERO = Decimal(0)


def text(value):
    return str(value).strip() if value is not None else ''


def hours(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


@dataclass(frozen=True)
class HoursRecord:
    source: str
    unit: str
    worker: str
    employee_id: str
    name: str
    department: str
    doc_date: datetime
    time_in: str
    time_out: str
    direct: int
    net: Decimal | None
    overtime: Decimal | None
    created_at: datetime | None
    flags: tuple = ()


@dataclass(frozen=True)
class HoursSnapshot:
    records: tuple
    loaded_at: datetime
    day: tuple


def annotate(records):
    def key(row):
        return (row.employee_id.casefold(), row.doc_date.date(), row.unit.casefold(),
                row.department.casefold(), row.worker.casefold(), row.direct)
    counts = Counter(key(row) for row in records if row.employee_id)
    result = []
    for row in records:
        flags = []
        for label, value in (('employee ID', row.employee_id), ('unit', row.unit),
                             ('department', row.department), ('worker type', row.worker)):
            if not value:
                flags.append('Missing ' + label)
        for label, value in (('Net hours', row.net), ('Overtime hours', row.overtime)):
            if value is None:
                flags.append(label + ' invalid')
            elif value < 0:
                flags.append(label + ' negative')
            elif value > 24:
                flags.append(label + ' exceeds 24')
        if row.employee_id and counts[key(row)] > 1:
            flags.append('Repeated employee/day/dimensions; verify split shifts or duplication')
        if row.net == ZERO and row.overtime is not None and row.overtime > ZERO:
            flags.append('Overtime with zero net hours')
        result.append(replace(row, flags=tuple(flags)))
    return tuple(result)


def summarize(records):
    net = sum((r.net for r in records if r.net is not None), ZERO)
    overtime = sum((r.overtime for r in records if r.overtime is not None), ZERO)
    identities = {r.employee_id.casefold() for r in records if r.employee_id}
    return dict(net=net, overtime=overtime, total=net + overtime,
                ot_share=overtime / (net + overtime) * 100 if net + overtime > 0 else None,
                employees=len(identities), records=len(records),
                overtime_employees=len({r.employee_id.casefold() for r in records
                                        if r.employee_id and r.overtime is not None and r.overtime > 0}),
                ot_rate=overtime / net * 100 if net > 0 else None,
                review=sum(bool(r.flags) for r in records))


def breakdown(records, dimension):
    groups = {}
    for row in records:
        value = row.doc_date.date().isoformat() if dimension == 'date' else getattr(row, dimension) or 'Not assigned'
        groups.setdefault(value, []).append(row)
    return [dict(label=value, **summarize(rows))
            for value, rows in sorted(groups.items(), key=lambda pair: pair[0].casefold())]


class SqlHrHours:
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, window):
        import pyodbc
        start_day, end_day = window
        start = datetime.combine(start_day, time.min)
        end = datetime.combine(end_day + timedelta(days=1), time.min)
        limit = self.settings.getint('hr_hours', 'max_rows')
        db = self.settings['database']
        with closing(pyodbc.connect(build_connection_string(self.settings), readonly=True,
                                   autocommit=True, timeout=db.getint('connection_timeout_seconds'))) as connection:
            connection.timeout = db.getint('query_timeout_seconds')
            with closing(connection.cursor()) as cursor:
                cursor.execute(PREFLIGHT)
                preflight = cursor.fetchone()
                if not preflight or preflight[0] != 1 or preflight[1] != 2:
                    raise AttendanceUnavailable('SBO_AI access or session isolation unavailable.')
                cursor.execute(RECORDS, limit + 1, start, end, start, end)
                rows = cursor.fetchmany(limit + 1)
                if len(rows) > limit:
                    raise AttendanceUnavailable('Range exceeds configured row limit.')
                records = tuple(HoursRecord(text(s), text(u), text(w), text(i), text(n) or 'Name unavailable',
                                text(d), stamp, text(tin), text(tout), direct,
                                hours(net), hours(ot), created)
                                for s, u, w, i, n, d, stamp, tin, tout, direct, net, ot, created in rows)
        return HoursSnapshot(annotate(records), datetime.now(PAKISTAN), window)


def demo_hours(window):
    start, end = window
    records = []
    for offset in range((end - start).days + 1):
        for index, (unit, department, worker) in enumerate((('UNIT3', 'Production', 'SPEL'),
                ('UNIT3', 'Quality', 'HRSG'), ('UNIT8', 'Production', 'SPEL'), ('UNIT6', 'HR', 'INTERN'))):
            records.append(HoursRecord('HR_MIS_C', unit, worker, 'SAMPLE' + str(index),
                'Sample employee ' + str(index + 1), department,
                datetime.combine(start + timedelta(days=offset), time.min), '08:00', '17:00',
                index % 2, Decimal('8'), Decimal('2') if index % 2 else ZERO, None))
    return HoursSnapshot(annotate(records), datetime.now(PAKISTAN), window)


class RangeCache:
    """Bound memory and reuse one snapshot per date window across all dimensions."""
    def __init__(self, loader, ttl, capacity):
        self.loader, self.ttl, self.capacity = loader, ttl, capacity
        self.entries, self.lock = OrderedDict(), Lock()

    def get(self, window):
        with self.lock:
            cache = self.entries.pop(window, None)
            if cache is None:
                cache = SharedAttendanceCache(self.loader, self.ttl)
            self.entries[window] = cache
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
        return cache.get(window)


def register_hr_hours(app, settings, live):
    from dashboard.hr_comparison import register_hr_comparison
    register_hr_comparison(app, settings, live)
    limits = {}
    for name, low, high in (('refresh_seconds', 60, 3600), ('default_days', 1, 31),
                           ('max_range_days', 1, 93), ('max_rows', 100, 100000), ('cached_ranges', 1, 5)):
        limits[name] = settings.getint('hr_hours', name)
        if not low <= limits[name] <= high:
            raise ValueError('Invalid hr_hours.' + name)
    if limits['default_days'] > limits['max_range_days']:
        raise ValueError('HR default range exceeds maximum range.')
    cache = RangeCache(SqlHrHours(settings) if live else demo_hours,
                       limits['refresh_seconds'], limits['cached_ranges'])
    app.extensions['hr_hours_cache'] = cache

    @app.get('/hr-hours')
    def hr_hours():
        analysis = request.args.get('analysis')
        if analysis in ('monthly', 'yearly') or (not analysis and not request.args.get('start') and not request.args.get('end')):
            return app.view_functions['hr_comparison']()
        scope = hr_scope()
        now = datetime.now(PAKISTAN)
        default_start = now.date() - timedelta(days=limits['default_days'] - 1)
        message = None
        try:
            start = date.fromisoformat(request.args.get('start') or default_start.isoformat())
            end = date.fromisoformat(request.args.get('end') or now.date().isoformat())
            if not 1 <= (end - start).days + 1 <= limits['max_range_days']:
                raise ValueError()
            if start < date(1900, 1, 1) or end >= date(9999, 12, 31):
                raise ValueError()
        except ValueError:
            start, end = default_start, now.date()
            message = 'Choose an ordered date range of at most ' + str(limits['max_range_days']) + ' days.'
        filters = {key: request.args.get(key, '') for key in ('unit', 'department', 'worker', 'direct')}
        base = dict(today=now.strftime('%d %b %Y'), live=live, location='', locations=[],
                    active_tab='hr_hours', ui_colors=app.config['SPEL_UI_COLORS'],
                    ttl=limits['refresh_seconds'], start=start.isoformat(), end=end.isoformat(),
                    filters=filters, error=message, stale=False, max_rows=limits['max_rows'])
        if message:
            return render_template('hr_hours.html', **base), 400
        try:
            snapshot, stale = cache.get((start, end))
        except AttendanceUnavailable:
            return render_template('hr_hours.html', **base | {'error':
                'HR hours unavailable. Check SBO_AI access or narrow the date range; partial totals are never shown.'}), 503
        scoped = [r for r in snapshot.records if unit_allowed(r.unit, scope)]
        rows = [r for r in scoped if all(not value or
                json.dumps(str(r.direct) if key == 'direct' else getattr(r, key)) == value
                for key, value in filters.items())]
        options = {key: [(json.dumps(value), value or 'Not assigned') for value in
                        sorted({str(r.direct) if key == 'direct' else getattr(r, key)
                                for r in scoped}, key=str.casefold)]
                   for key in filters}
        # A blank dimension needs an explicit selectable token, rather than being
        # confused with the All option. Tokens are encoded only in the UI layer.
        details = [dict(source=r.source, unit=r.unit or 'Not assigned', worker=r.worker or 'Not assigned',
                        id=r.employee_id, name=r.name, department=r.department or 'Not assigned',
                        date=r.doc_date.date().isoformat(), time_in=r.time_in, time_out=r.time_out,
                        direct=r.direct, net=str(r.net) if r.net is not None else None,
                        overtime=str(r.overtime) if r.overtime is not None else None,
                        total=str(r.net + r.overtime) if r.net is not None and r.overtime is not None else None,
                        flags=list(r.flags)) for r in rows]
        summary = summarize(rows)
        return render_template('hr_hours.html', **base | {'stale': stale},
                    options=options, summary=summary, details=details,
                    breakdowns={key: breakdown(rows, key) for key in ('unit', 'department', 'worker', 'date')},
                    loaded_at=snapshot.loaded_at.strftime('%d %b %Y %H:%M:%S'),
                    fmt=lambda value: format(value, ',.2f') if value is not None else '—')
