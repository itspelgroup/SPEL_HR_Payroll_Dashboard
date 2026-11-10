"""Location-based inferred presence, exceptions and employee details."""
from dashboard.access import location_allowed, safe_location_filter
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import render_template, request

from dashboard.attendance import AttendanceUnavailable, PAKISTAN, SharedAttendanceCache
from dashboard.employees import SqlEmployees, demo_employees


def normalized_location(value, aliases=None):
    value = ' '.join((value or '').split()).casefold()
    return (aliases or {}).get(value, value)


def employee_location(unit):
    unit = ' '.join((unit or '').split()).upper()
    if unit in ('OFFICE', 'UNIT6'):
        return 'HeadOffice'
    if unit in ('UNIT1', 'UNIT2', 'UNIT3', 'UNIT4', 'UNIT7', 'OFFICE_P'):
        return 'Pandoki'
    if unit in ('UNIT5RYK', 'UNIT5SEZ'):
        return 'RahimYarkhan'
    if unit in ('UNIT8', 'UNIT9'):
        return 'Karachi'
    return 'Other'


def register_employee_overview(app, settings, live):
    interval = settings.getint('employee_overview', 'refresh_seconds')
    long_hours = settings.getfloat('employee_overview', 'long_stay_hours')
    lookback = settings.getint('employee_overview', 'lookback_hours')
    if not 10 <= interval <= 3600 or not 0 < long_hours < lookback <= 168:
        raise ValueError('Employee settings require refresh 10–3600 seconds and 0 < long_stay_hours < lookback_hours <= 168.')
    aliases = {normalized_location(key):normalized_location(value)
               for key,value in settings.items('employee_location_aliases')} if settings.has_section('employee_location_aliases') else {}
    cache = SharedAttendanceCache(SqlEmployees(settings) if live else demo_employees, interval)
    app.extensions['employee_overview_cache'] = cache

    @app.get('/employees')
    def employee_overview():
        now = datetime.now(PAKISTAN)
        location = request.args.get('location', '')
        location = safe_location_filter(location, aliases=aliases)
        base = dict(today=now.strftime('%d %b %Y'), live=live, ttl=interval,
                    location=location, long_hours=long_hours, lookback=lookback,
                    location_label='', error=False,
                    wall_display=dict(settings.items('wall_display')),
                    ui_colors=app.config['SPEL_UI_COLORS'])
        try:
            snapshot, stale = cache.get(now.date())
        except AttendanceUnavailable:
            return render_template('employees.html', **base | {'error': True}), 503
        locations = {}
        for person in snapshot.employees:
            place = person.in_location
            if person.in_time is not None and place and place.strip() and location_allowed(place, aliases=aliases):
                locations.setdefault(json.dumps(place.strip().casefold()), place.strip())
        if location and location not in locations:
            location = ''
            base['location'] = ''
        base['location_label'] = locations.get(location, '')
        def matches(places):
            allowed = [place for place in places if place and location_allowed(place, aliases=aliases)]
            # Unknown locations are visible only to accounts with unrestricted access.
            return (bool(allowed) or location_allowed('', aliases=aliases)) and (not location or location in {json.dumps(place.strip().casefold()) for place in allowed})
        inside = [person for person in snapshot.employees if person.in_time is not None
                  and person.in_location and matches((person.in_location,))]
        inside_ids = {person.id for person in inside}
        overdue_ids = set()
        for person in inside:
            elapsed_seconds = int((now - person.in_time).total_seconds())
            elapsed_hours = (Decimal(elapsed_seconds) / Decimal(3600)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)
            if elapsed_hours > Decimal(str(long_hours)):
                overdue_ids.add(person.id)
        employee_locations = {person.id: employee_location(person.unit) for person in snapshot.employees}
        mismatch_ids = {person.id for person in inside
                        if not (person.id.isdecimal() and 9901 <= int(person.id) <= 9999)
                        and normalized_location(employee_locations[person.id], aliases)
                        != normalized_location(person.in_location, aliases)}
        guest_ids = {person.id for person in inside
                     if person.id.isdecimal() and 9901 <= int(person.id) <= 9999}
        summaries = {}
        for key, getter in (
            ('branch', lambda person: person.branch_name),
            ('unit', lambda person: person.unit),
            ('department', lambda person: person.department),
        ):
            counts = Counter((getter(person) or '').strip() or 'Not assigned' for person in inside)
            summaries[key] = [
                {'name': name, 'count': count}
                for name, count in sorted(counts.items(), key=lambda item: item[0].casefold())
            ]
        details = []
        for person in sorted(snapshot.employees, key=lambda value: value.id):
            if person.id not in inside_ids:
                continue
            unit, department = person.unit or 'Not assigned', person.department or 'Not assigned'
            seconds = max(0,int((now-person.in_time).total_seconds())) if person.id in inside_ids else None
            elapsed_hours = ((Decimal(seconds) / Decimal(3600)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP) if seconds is not None else None)
            mapped_location = employee_locations[person.id]
            details.append(dict(id=person.id, name=person.name, unit=unit, department=department,
                          branch=person.branch_name or 'Not assigned',
                          employee_location=mapped_location,
                          physical=person.physical_location or 'Not assigned',
                          in_location=person.in_location or person.last_event_location or '—',
                          in_time=person.in_time.strftime('%d %b %Y %H:%M:%S') if person.id in inside_ids else '—',
                          last_in=person.last_in_time.strftime('%d %b %Y %H:%M:%S') if person.last_in_time else '—',
                          last_out=person.last_out_time.strftime('%d %b %Y %H:%M:%S') if person.last_out_time else '—',
                          last_in_hours=f'{elapsed_hours:.2f}' if elapsed_hours is not None else '—',
                          duration=f'{seconds // 3600}h {(seconds % 3600) // 60}m' if seconds is not None else '—',
                          inside=person.id in inside_ids, overdue=person.id in overdue_ids,
                          working_hours_limit=person.id in overdue_ids,
                          mismatch=person.id in mismatch_ids,
                          from_other_location=person.id in mismatch_ids,
                          guest=person.id in guest_ids,
                          elapsed_seconds=seconds))
        return render_template('employees.html', **base, locations=sorted(locations.items(), key=lambda item:item[1].casefold()),
                               inside=len(inside), overdue=len(overdue_ids), mismatch=len(mismatch_ids),
                               guest=len(guest_ids), summaries=summaries,
                               details=details, stale=stale, loaded_at=snapshot.loaded_at.strftime('%H:%M:%S'))
