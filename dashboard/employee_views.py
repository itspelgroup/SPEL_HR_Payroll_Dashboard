"""Location-based inferred presence, exceptions and employee details."""
import json
from datetime import datetime

from flask import g, render_template, request

from dashboard.attendance import AttendanceUnavailable, PAKISTAN, SharedAttendanceCache
from dashboard.employees import SqlEmployees, demo_employees


def normalized_location(value, aliases=None):
    value = ' '.join((value or '').split()).casefold()
    return (aliases or {}).get(value, value)


def register_employee_overview(app, settings, live):
    interval = settings.getint('employee_overview', 'refresh_seconds')
    long_hours = settings.getfloat('employee_overview', 'long_stay_hours')
    lookback = settings.getint('employee_overview', 'lookback_hours')
    basis = settings.get('employee_overview', 'location_basis')
    if not 10 <= interval <= 3600 or not 0 < long_hours < lookback <= 168:
        raise ValueError('Employee settings require refresh 10–3600 seconds and 0 < long_stay_hours < lookback_hours <= 168.')
    if basis not in ('last_in_machine', 'employee_unit'):
        raise ValueError('employee_overview.location_basis must be last_in_machine or employee_unit.')
    aliases = {normalized_location(key):normalized_location(value)
               for key,value in settings.items('employee_location_aliases')} if settings.has_section('employee_location_aliases') else {}
    cache = SharedAttendanceCache(SqlEmployees(settings) if live else demo_employees, interval)
    app.extensions['employee_overview_cache'] = cache

    @app.get('/employees')
    def employee_overview():
        now = datetime.now(PAKISTAN)
        location = request.args.get('location', '')
        account = getattr(g, 'dashboard_user', None)
        if account and not account['is_admin']:
            location = json.dumps(account['location'].strip().casefold())
        base = dict(today=now.strftime('%d %b %Y'), live=live, ttl=interval,
                    location=location, long_hours=long_hours, lookback=lookback,
                    basis=basis, error=False, wall_display=dict(settings.items('wall_display')),
                    ui_colors=app.config['SPEL_UI_COLORS'])
        try:
            snapshot, stale = cache.get(now.date())
        except AttendanceUnavailable:
            return render_template('employees.html', **base | {'error': True}), 503
        locations = {}
        for _, place, _ in snapshot.devices:
            if place and place.strip():
                locations.setdefault(json.dumps(place.strip().casefold()), place.strip())
        def matches(places):
            return not location or location in {json.dumps(place.strip().casefold()) for place in places if place}
        inside = [person for person in snapshot.employees if person.in_time is not None
                  and person.in_location and matches((person.in_location,) if basis == 'last_in_machine' else person.locations)]
        inside_ids = {person.id for person in inside}
        overdue_ids = {person.id for person in inside
                       if (now - person.in_time).total_seconds() > long_hours * 3600}
        mismatch_ids = {person.id for person in inside if normalized_location(person.physical_location)
                        and normalized_location(person.physical_location, aliases) != normalized_location(person.in_location, aliases)}
        review_ids = {person.id for person in snapshot.employees
                      if person.unresolved and matches(person.last_event_locations or person.locations)}
        # Missing assignment is unknown, not a confirmed location mismatch.
        review_ids |= {person.id for person in inside if not normalized_location(person.physical_location)}
        visible_ids = inside_ids | review_ids
        no_event = sum(person.last_event_time is None and person.in_time is None and matches(person.locations)
                       for person in snapshot.employees)
        details = []
        for person in sorted(snapshot.employees, key=lambda value: value.id):
            if person.id not in visible_ids:
                continue
            unit, department = person.unit or 'Not assigned', person.department or 'Not assigned'
            seconds = max(0,int((now-person.in_time).total_seconds())) if person.id in inside_ids else None
            reason = person.exclusion_reason if person.unresolved else ('PhysicalLocation is not assigned' if person.id in review_ids else '')
            details.append(dict(id=person.id, name=person.name, unit=unit, department=department,
                          physical=person.physical_location or 'Not assigned',
                          in_location=person.in_location or person.last_event_location or '—',
                          in_time=person.in_time.strftime('%d %b %Y %H:%M:%S') if person.id in inside_ids else '—',
                          duration=f'{seconds // 3600}h {(seconds % 3600) // 60}m' if seconds is not None else '—',
                          inside=person.id in inside_ids, overdue=person.id in overdue_ids,
                          mismatch=person.id in mismatch_ids, review=person.id in review_ids,
                          elapsed_seconds=seconds, reason=reason, last_event=person.last_event_time.strftime('%d %b %Y %H:%M:%S') if person.last_event_time else '—'))
        return render_template('employees.html', **base, locations=sorted(locations.items(), key=lambda item:item[1].casefold()),
                               inside=len(inside), overdue=len(overdue_ids), mismatch=len(mismatch_ids),
                               review=len(review_ids), no_event=no_event,
                               details=details, stale=stale, loaded_at=snapshot.loaded_at.strftime('%H:%M:%S'))
