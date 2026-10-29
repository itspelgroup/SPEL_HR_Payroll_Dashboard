"""Attendance dashboard. SQL access requires explicit live configuration."""
import json
from datetime import datetime

from flask import Flask, render_template, request

from dashboard.attendance import (AttendanceUnavailable, PAKISTAN,
                                  SharedAttendanceCache, SqlAttendance, demo_snapshot)
from dashboard.config import load_settings


def create_app(config_path=None, provider=None):
    app = Flask(__name__)
    settings = load_settings(config_path)
    mode = settings.get('application', 'data_mode')
    live = mode == 'live'
    if mode not in ('demo', 'live') or settings.getboolean('database', 'enabled') != live:
        raise ValueError('Use demo/database enabled=false or live/database enabled=true.')
    if live and not settings.getboolean('cache', 'enabled'):
        raise ValueError('Shared application caching is required in live mode.')
    port = settings.getint('application', 'port')
    if not 1 <= port <= 65535 or settings.getint('application', 'timezone_offset_minutes') != 300:
        raise ValueError('Use a valid port and Pakistan timezone offset 300.')
    ttl = settings.getint('cache', 'ttl_seconds')
    if not 10 <= ttl <= 3600:
        raise ValueError('Cache TTL must be between 10 and 3600 seconds.')
    for name in ('connection_timeout_seconds', 'query_timeout_seconds'):
        if not 1 <= settings.getint('database', name) <= 120:
            raise ValueError('Database timeouts must be between 1 and 120 seconds.')
    app.config.update(SPEL_HOST=settings.get('application', 'host'), SPEL_PORT=port,
                      DEBUG=settings.getboolean('application', 'debug'))
    cache = SharedAttendanceCache(provider or (SqlAttendance(settings) if live else demo_snapshot), ttl)
    app.extensions['attendance_cache'] = cache

    @app.after_request
    def prevent_employee_page_storage(response):
        if request.endpoint == 'attendance':
            response.headers['Cache-Control'] = 'no-store'
        return response

    def token(value):
        # Distinguishes unassigned, empty and literal label values.
        return json.dumps(value, ensure_ascii=False)

    def label(value):
        return 'Not assigned' if value is None else value or '(blank)'

    @app.get('/')
    def attendance():
        now = datetime.now(PAKISTAN)
        unit, location = request.args.get('unit', ''), request.args.get('location', '')
        base = dict(today=now.strftime('%d %b %Y'), live=live, ttl=ttl,
                    unit=unit, location=location, error=False)
        try:
            snapshot, stale = cache.get(now.date())
        except AttendanceUnavailable:
            return render_template('attendance.html', **base | {'error': True}), 503
        mapped = [e for e in snapshot.employees if e.mapped]
        location_labels = {}
        for employee in mapped:
            for value in employee.locations:
                location_labels.setdefault(token(value.casefold()), value)
        def at_location(employee):
            values = [token(value.casefold()) for value in employee.locations]
            return not location or (location == 'null' and not values) or location in values
        located = [e for e in mapped if at_location(e)]
        selected = [e for e in located if not unit or token(e.unit) == unit]
        grouped = {}
        for employee in selected:
            counts = grouped.setdefault(employee.unit, [0, 0])
            counts[0] += 1
            counts[1] += employee.punched
        rows = [dict(unit=value, registered=counts[0], punched=counts[1])
                for value, counts in sorted(grouped.items(), key=lambda item: label(item[0]))]
        punched = sum(e.punched for e in selected)
        unmapped = [e for e in snapshot.employees if not e.mapped]
        def detail(employee):
            return dict(id=employee.id, name=employee.name, unit=label(employee.unit),
                        unit_token=token(employee.unit), department=label(employee.department),
                        punched=employee.punched, mapped=employee.mapped,
                        location=', '.join(employee.locations) or 'Not assigned')
        return render_template(
            'attendance.html', **base, rows=rows, label=label, token=token,
            locations=sorted(location_labels.items(), key=lambda item: item[1].casefold()),
            has_unassigned=any(not e.locations for e in mapped),
            units=[(token(v), label(v)) for v in sorted({e.unit for e in located}, key=label)],
            unit_options=[dict(value=token(v), label=label(v),
                               locations=sorted({token(loc.casefold()) for e in mapped if e.unit == v for loc in e.locations}),
                               unassigned=any(not e.locations for e in mapped if e.unit == v))
                          for v in sorted({e.unit for e in mapped}, key=label)],
            registered=len(selected), punched=punched, no_punch=len(selected)-punched,
            unmapped=len(unmapped), distinct_ids=sum(e.punched for e in mapped)+len(unmapped),
            details=[detail(e) for e in sorted(selected+unmapped, key=lambda e: e.id)],
            stale=stale, loaded_at=snapshot.loaded_at.strftime('%H:%M:%S'),
            age=max(0, int((now-snapshot.loaded_at).total_seconds())))

    return app


if __name__ == '__main__':
    application = create_app()
    application.run(host=application.config['SPEL_HOST'],
                    port=application.config['SPEL_PORT'], debug=application.debug)
