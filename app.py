"""Attendance dashboard. SQL access requires explicit live configuration."""
import ipaddress
import json
import os
from datetime import datetime

from flask import Flask, render_template, request, g

from dashboard.access import location_allowed, safe_location_filter
from dashboard.attendance import (AttendanceUnavailable, PAKISTAN,
                                  SharedAttendanceCache, SqlAttendance, demo_snapshot)
from dashboard.config import load_settings
from dashboard.machines import SqlMachines, demo_machines, machine_status, recent_punch
from dashboard.users import install_auth
from dashboard.employee_views import register_employee_overview
from dashboard.employees import direction_from_name
from dashboard.employee_directory import register_employee_directory
from dashboard.hr_hours import register_hr_hours


def create_app(config_path=None, provider=None, machine_provider=None):
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
    host = (os.environ.get('SPEL_HOST') or settings.get('application', 'host')).strip()
    if not host:
        raise ValueError('application.host or SPEL_HOST must not be empty.')
    try:
        network_bind = not ipaddress.ip_address(host).is_loopback
    except ValueError:
        network_bind = host.casefold() != 'localhost'
    if live and network_bind and not settings.getboolean('security', 'enabled'):
        raise ValueError('Authentication is required before binding live data to a network interface.')
    ttl = settings.getint('cache', 'ttl_seconds')
    if not 10 <= ttl <= 3600:
        raise ValueError('Cache TTL must be between 10 and 3600 seconds.')
    for name in ('connection_timeout_seconds', 'query_timeout_seconds'):
        if not 1 <= settings.getint('database', name) <= 120:
            raise ValueError('Database timeouts must be between 1 and 120 seconds.')
    app.config.update(SPEL_HOST=host, SPEL_PORT=port,
                      DEBUG=settings.getboolean('application', 'debug'))
    threads = settings.getint('server', 'threads')
    if not 1 <= threads <= 64:
        raise ValueError('server.threads must be between 1 and 64.')
    app.config['SPEL_THREADS'] = threads
    install_auth(app, settings, live)
    register_employee_overview(app, settings, live)
    register_employee_directory(app, settings, live)
    register_hr_hours(app, settings, live)
    cache = SharedAttendanceCache(provider or (SqlAttendance(settings) if live else demo_snapshot), ttl)
    app.extensions['attendance_cache'] = cache
    refresh = settings.getint('dashboard', 'auto_refresh_seconds')
    history_limit = settings.getint('punch_history', 'limit')
    if not 10 <= refresh <= 3600:
        raise ValueError('dashboard.auto_refresh_seconds must be between 10 and 3600.')
    if not 1 <= history_limit <= 100:
        raise ValueError('punch_history.limit must be between 1 and 100.')
    wall_display = dict(settings.items('wall_display'))
    ui_colors = {}
    for name in ('healthy', 'attention', 'critical', 'information', 'direction_in', 'direction_out'):
        values = [int(value.strip()) for value in settings.get('ui_colors', name).split(',')]
        if len(values) != 3 or any(value < 0 or value > 255 for value in values):
            raise ValueError('ui_colors.' + name + ' must contain three RGB components from 0 to 255.')
        ui_colors[name] = ', '.join(str(value) for value in values)
    app.config['SPEL_UI_COLORS'] = ui_colors
    for name in ('reference_tile_width', 'reference_tile_height', 'gap_pixels',
                 'compact_gap_pixels', 'compact_breakpoint_pixels', 'max_font_scale'):
        if not 0 < float(wall_display[name]) <= 10000:
            raise ValueError('wall_display.' + name + ' must be positive and at most 10000.')
    machine_cache = SharedAttendanceCache(
        machine_provider or (SqlMachines(settings) if live else demo_machines), refresh)
    app.extensions['machine_cache'] = machine_cache
    recent = settings.getint('machine_activity', 'recent_minutes')
    delayed = settings.getint('machine_activity', 'delayed_minutes')
    if not 0 < recent < delayed:
        raise ValueError('Machine thresholds must satisfy 0 < recent_minutes < delayed_minutes.')

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
    def machines():
        now = datetime.now(PAKISTAN)
        location = request.args.get('location', '')
        location = safe_location_filter(location)
        base = dict(today=now.strftime('%d %b %Y'), live=live, ttl=refresh,
                    location=location, recent=recent, delayed=delayed, error=False,
                    history_limit=history_limit, wall_display=wall_display, ui_colors=ui_colors)
        try:
            snapshot, stale = machine_cache.get(now.date())
        except AttendanceUnavailable:
            return render_template('machines.html', **base | {'error': True}), 503
        locations = {}
        for machine in snapshot.machines:
            value = (machine.location or '').strip()
            if not location_allowed(value):
                continue
            locations.setdefault(token(value.casefold()), value or 'Not assigned')
        rows = []
        for machine in snapshot.machines:
            value = (machine.location or '').strip()
            if not location_allowed(value):
                continue
            if location and token(value.casefold()) != location:
                continue
            status = machine_status(machine, now, recent, delayed)
            rows.append(dict(machine=machine, status=status, direction=direction_from_name(machine.name) or 'UNKNOWN'))
        return render_template('machines.html', **base, rows=sorted(rows, key=lambda r: r['machine'].code),
                               machine_groups=[dict(direction=direction, rows=sorted(
                                   [row for row in rows if row['direction'] == direction], key=lambda row:row['machine'].code))
                                   for direction in ('IN','OUT','UNKNOWN') if any(row['direction'] == direction for row in rows)],
                               recent_punch=lambda value: recent_punch(value, now, recent),
                               locations=sorted(locations.items(), key=lambda item: item[1].casefold()),
                               stale=stale,
                               loaded_at=snapshot.loaded_at.strftime('%d %b %Y %H:%M:%S'))

    @app.get('/attendance')
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
        device_units = snapshot.device_units
        if device_units is None:
            device_units = tuple((loc, e.unit) for e in mapped
                                 for loc in (e.locations or (None,)))
        location_labels = {}
        for value, device_unit in device_units:
            if value:
                location_labels.setdefault(token(value.casefold()), value)
        def at_location(employee):
            values = [token(value.casefold()) for value in employee.locations]
            return not location or (location == 'null' and not values) or location in values
        located = [e for e in mapped if at_location(e)]
        allowed_units = {device_unit for loc, device_unit in device_units
                         if not location or (location == 'null' and not loc)
                         or (loc and token(loc.casefold()) == location)}
        # A location change or bookmarked URL can carry a unit outside this scope.
        # Reset it so the displayed selection and attendance totals agree.
        if location and unit and unit not in {token(value) for value in allowed_units}:
            unit = ''
            base['unit'] = unit
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
            has_unassigned=any(not loc for loc, _ in device_units),
            units=[(token(v), label(v)) for v in sorted(allowed_units, key=label)],
            unit_options=[dict(value=token(v), label=label(v),
                               locations=sorted({token(loc.casefold()) for loc, u in device_units if u == v and loc}),
                               unassigned=any(not loc for loc, u in device_units if u == v))
                          for v in sorted({u for _, u in device_units}, key=label)],
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
