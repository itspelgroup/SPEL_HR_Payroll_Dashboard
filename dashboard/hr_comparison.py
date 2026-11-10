"""SQL-aggregated monthly/yearly HR hours; regular + overtime = total."""
from dashboard.access import hr_scope, unit_allowed
from calendar import monthrange
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import json

from flask import abort, g, render_template, request

from dashboard.attendance import AttendanceUnavailable, PAKISTAN, QUERY_DIR
from dashboard.config import build_connection_string
from dashboard.hr_hours import PREFLIGHT, RangeCache, ZERO, hours, text

PERIOD_SQL = (QUERY_DIR / 'hr_hours_periods.sql').read_text(encoding='utf-8')


@dataclass(frozen=True)
class PeriodGroup:
    month: date
    unit: str
    department: str
    worker: str
    direct: str
    records: int
    net: Decimal
    overtime: Decimal
    first_record: date
    last_record: date


@dataclass(frozen=True)
class PeriodSnapshot:
    groups: tuple
    loaded_at: datetime
    day: tuple


def sum_groups(groups):
    net = sum((group.net for group in groups), ZERO)
    overtime = sum((group.overtime for group in groups), ZERO)
    total = net + overtime
    return dict(net=net, overtime=overtime, total=total,
                ot_share=overtime / total * 100 if total > 0 else None,
                records=sum(group.records for group in groups),
                units=len({group.unit for group in groups}),
                departments=len({group.department for group in groups}))


def change(current, baseline):
    if current is None or baseline is None:
        return dict(hours=None, percent=None)
    return dict(hours=current-baseline,
                percent=(current-baseline) / abs(baseline) * 100 if baseline != 0 else None)


def fiscal_start(value):
    return date(value.year if value.month >= 7 else value.year - 1, 7, 1)


def fiscal_label(value):
    start = fiscal_start(value)
    return 'FY ' + str(start.year) + '/' + str(start.year + 1)[-2:]


def period_series(groups, start, end, analysis, fiscal=True, as_of=None):
    bucket = defaultdict(list)
    for group in groups:
        key = (fiscal_start(group.month) if fiscal else date(group.month.year, 1, 1)) if analysis == 'yearly' else group.month
        bucket[key].append(group)
    cursor = (fiscal_start(start) if fiscal else date(start.year, 1, 1)) if analysis == 'yearly' else start.replace(day=1)
    result = []
    while cursor <= end:
        if analysis == 'yearly':
            last = date(cursor.year + 1, 6, 30) if fiscal else date(cursor.year, 12, 31)
            following = date(cursor.year + 1, 7, 1) if fiscal else date(cursor.year+1, 1, 1)
            label = fiscal_label(cursor) if fiscal else str(cursor.year)
            key = 'FY' + str(cursor.year) + '-' + str(cursor.year+1)[-2:] if fiscal else str(cursor.year)
        else:
            last = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
            following = last + timedelta(days=1)
            label, key = cursor.strftime('%b %Y'), cursor.strftime('%Y-%m')
        rows = bucket.get(cursor, [])
        summary = sum_groups(rows)
        result.append(dict(key=key, label=label, start=max(cursor, start).isoformat(),
                           end=min(last, end).isoformat(),
                           fiscal_year=fiscal_label(cursor),
                           partial=start > cursor or end < last or (as_of is not None and cursor <= as_of < last),
                           upcoming=as_of is not None and cursor > as_of,
                           has_data=bool(rows), **summary,
                           first_record=min((row.first_record for row in rows), default=None),
                           last_record=max((row.last_record for row in rows), default=None)))
        cursor = following
    for index, row in enumerate(result):
        previous = result[index-1] if index else None
        row['delta'] = change(row['total'] if row['has_data'] else None,
                              previous['total'] if previous and previous['has_data'] else None)
    return result


class SqlHrPeriods:
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, window):
        import pyodbc
        start_day, end_day = window
        start = datetime.combine(start_day, time.min)
        end = datetime.combine(end_day + timedelta(days=1), time.min)
        limit = self.settings.getint('hr_hours', 'max_period_groups')
        db = self.settings['database']
        with closing(pyodbc.connect(build_connection_string(self.settings), readonly=True,
                     autocommit=True, timeout=db.getint('connection_timeout_seconds'))) as connection:
            connection.timeout = db.getint('query_timeout_seconds')
            with closing(connection.cursor()) as cursor:
                cursor.execute(PREFLIGHT)
                preflight = cursor.fetchone()
                if not preflight or preflight[0] != 1 or preflight[1] != 2:
                    raise AttendanceUnavailable('SBO_AI access or isolation unavailable.')
                cursor.execute(PERIOD_SQL, limit+1, start, end, start, end)
                rows = cursor.fetchmany(limit+1)
                if len(rows) > limit:
                    raise AttendanceUnavailable('Aggregate group limit exceeded.')
                groups = []
                for month, unit, department, worker, direct, count, net, ot, first, last in rows:
                    net, ot = hours(net), hours(ot)
                    if net is None or ot is None:
                        raise AttendanceUnavailable('Invalid aggregate hours.')
                    groups.append(PeriodGroup(month.date() if isinstance(month, datetime) else month,
                        text(unit), text(department), text(worker), text(direct), int(count), net, ot,
                        first.date() if isinstance(first, datetime) else first,
                        last.date() if isinstance(last, datetime) else last))
        return PeriodSnapshot(tuple(groups), datetime.now(PAKISTAN), window)


def demo_periods(window):
    start, end = window
    if start.year == 1753:
        start = date(fiscal_start(end).year - 3, 7, 1)
    month = start.replace(day=1)
    groups = []
    while month <= end:
        last = date(month.year, month.month, monthrange(month.year, month.month)[1])
        first_selected, last_selected = max(start, month), min(end, last)
        days = (last_selected-first_selected).days + 1
        for index, (unit, department, worker) in enumerate((('UNIT3','Production','SPEL'),
                ('UNIT3','Quality','HRSG'),('UNIT8','Production','SPEL'))):
            factor = Decimal((month.year % 10 + 5) * (month.month % 5 + 8) * (index+2))
            net = factor * days
            overtime = net * Decimal(index+1) / 20
            groups.append(PeriodGroup(month,unit,department,worker,str(index % 2),days*(index+10),
                                      net,overtime,first_selected,last_selected))
        month = last + timedelta(days=1)
    return PeriodSnapshot(tuple(groups), datetime.now(PAKISTAN), window)


def comparison_model(groups, today, analysis, first_available=None):
    current = fiscal_start(today)
    previous = date(current.year-1,7,1)
    if analysis == 'monthly':
        start, end = previous, date(current.year+1,6,30)
    else:
        start = fiscal_start(first_available or min((row.month for row in groups),default=current))
        end = today
    series = period_series(groups,start,end,analysis,as_of=today)
    for row in series:
        stamp = date.fromisoformat(row['start'])
        row['role'] = 'current' if fiscal_start(stamp) == current else 'previous'
        row['month_index'] = (stamp.month-7)%12
    if analysis == 'monthly':
        previous_rows=series[:12]
        current_rows=series[12:]
        pairs=[dict(label=previous_rows[index]['label'].split(' ')[0],
                    previous=previous_rows[index],current=current_rows[index]) for index in range(12)]
    else:
        pairs=[]
    return dict(series=series,pairs=pairs,start=start,end=end,
                current_fy=fiscal_label(current),previous_fy=fiscal_label(previous),
                current_summary=sum_groups([row for row in groups if fiscal_start(row.month)==current]))


def register_hr_comparison(app, settings, live):
    group_limit = settings.getint('hr_hours','max_period_groups')
    if not 100 <= group_limit <= 100000:
        raise ValueError('Invalid HR comparison group limit.')
    cache = RangeCache(SqlHrPeriods(settings) if live else demo_periods,
                       settings.getint('hr_hours','refresh_seconds'),
                       settings.getint('hr_hours','cached_ranges'))
    app.extensions['hr_period_cache'] = cache

    @app.get('/hr-hours/comparison')
    def hr_comparison():
        scope = hr_scope()
        now = datetime.now(PAKISTAN)
        analysis = request.args.get('analysis', 'monthly')
        if analysis not in ('monthly','yearly'):
            abort(400)
        current = fiscal_start(now.date())
        # SQL datetime's full range, not an arbitrary last-N-years cutoff.
        # Transfer stays bounded by the existing aggregate-group cap.
        load_start=date(current.year-1,7,1) if analysis=='monthly' else date(1753,1,1)
        filters = {key: request.args.get(key,'') for key in ('unit','department','worker','direct')}
        base = dict(today=now.strftime('%d %b %Y'),live=live,location='',locations=[],active_tab='hr_hours',
            ui_colors=app.config['SPEL_UI_COLORS'],ttl=settings.getint('hr_hours','refresh_seconds'),
            analysis=analysis,filters=filters,error=None,stale=False,as_of=now.date().isoformat(),
            current_fy=fiscal_label(current),previous_fy=fiscal_label(date(current.year-1,7,1)),
            filters_active=any(filters.values()),
            current_start=current.isoformat(),
            fmt=lambda value: format(value,',.2f') if value is not None else 'N/A')
        try:
            snapshot, stale = cache.get((load_start,now.date()))
        except AttendanceUnavailable:
            return render_template('hr_comparison.html',**base | {'error':
                'Hours are unavailable. Please retry shortly; no partial totals are shown.'}),503
        available=[row for row in snapshot.groups if load_start<=row.month<=now.date() and unit_allowed(row.unit, scope)]
        selected = [row for row in available if all(not value or json.dumps(getattr(row,key))==value
                                                   for key,value in filters.items())]
        options = {key:[(json.dumps(value),value or 'Not assigned') for value in sorted(
                        {getattr(row,key) for row in available},key=str.casefold)] for key in filters}
        model=comparison_model(selected,now.date(),analysis,
                               first_available=min((row.month for row in available),default=current))
        def payload(row):
            return dict(key=row['key'],label=row['label'],partial=row['partial'],has_data=row['has_data'],
                        fiscal_year=row['fiscal_year'],upcoming=row['upcoming'],role=row['role'],
                        month_index=row['month_index'],start=row['start'],end=row['end'],records=row['records'],
                        first_record=row['first_record'].isoformat() if row['first_record'] else None,
                        last_record=row['last_record'].isoformat() if row['last_record'] else None,
                        net=str(row['net']) if row['has_data'] else None,
                        overtime=str(row['overtime']) if row['has_data'] else None,
                        total=str(row['total']) if row['has_data'] else None)
        groups = [dict(month=row.month.isoformat(),unit=row.unit or 'Not assigned',
                       department=row.department or 'Not assigned',worker=row.worker or 'Not assigned',
                       unit_filter=json.dumps(row.unit),department_filter=json.dumps(row.department),
                       worker_filter=json.dumps(row.worker),direct_filter=json.dumps(row.direct),
                       direct=row.direct,records=row.records,net=str(row.net),overtime=str(row.overtime),
                       total=str(row.net+row.overtime),first_record=row.first_record.isoformat(),
                       last_record=row.last_record.isoformat()) for row in selected]
        return render_template('hr_comparison.html',**(base|{'stale':stale}),options=options,
            summary=model['current_summary'],series=model['series'],month_pairs=model['pairs'],
            start=model['start'].isoformat(),end=model['end'].isoformat(),
            chart_data=[payload(row) for row in model['series']],groups=groups,
            loaded_at=snapshot.loaded_at.strftime('%d %b %Y %H:%M:%S'))
