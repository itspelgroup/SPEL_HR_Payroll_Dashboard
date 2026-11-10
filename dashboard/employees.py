"""Cached employee roster and conservative unmatched-IN inference."""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
import csv
import re

from dashboard.attendance import (PAKISTAN, PREFLIGHT_SQL, QUERY_DIR,
                                  AttendanceUnavailable, demo_snapshot, display_name)
from dashboard.config import ROOT, build_connection_string

ROSTER_SQL = (QUERY_DIR / 'employee_roster.sql').read_text(encoding='utf-8')
DEVICES_SQL = (QUERY_DIR / 'employee_devices.sql').read_text(encoding='utf-8')
EVENTS_SQL = (QUERY_DIR / 'employee_latest_events.sql').read_text(encoding='utf-8')


def direction_from_name(name):
    """Only complete IN/OUT name tokens identify a direction."""
    tokens = set(re.split(r'[^A-Z0-9]+', (name or '').strip().upper()))
    directions = tokens & {'IN', 'OUT'}
    return next(iter(directions)) if len(directions) == 1 else None


@dataclass(frozen=True)
class OverviewEmployee:
    id: str
    name: str
    unit: str | None
    department: str | None
    physical_location: str | None
    locations: tuple
    in_time: datetime | None = None
    in_location: str | None = None
    unresolved: bool = False
    exclusion_reason: str = ''
    last_event_time: datetime | None = None
    last_event_location: str | None = None
    last_event_locations: tuple = ()
    branch_name: str | None = None
    last_in_time: datetime | None = None
    last_out_time: datetime | None = None


@dataclass(frozen=True)
class EmployeeSnapshot:
    employees: tuple
    devices: tuple
    loaded_at: datetime
    day: object


def local_time(value):
    return value.replace(tzinfo=PAKISTAN) if value.tzinfo is None else value.astimezone(PAKISTAN)


def build_employees(roster, devices, events, directions, now):
    device_locations = {str(code).strip().casefold(): location for code, location, unit in devices}
    directions = {str(code).strip().casefold(): value for code, value in directions.items()}
    unit_locations = {}
    for code, location, unit in devices:
        if location and location.strip():
            unit_locations.setdefault(unit, {})[location.strip().casefold()] = location.strip()
    latest = {}
    punch_times = {}
    for event in events:
        user_id, punch_time, sensor = event[:3]
        user_id = str(user_id).strip()
        latest.setdefault(user_id, []).append((local_time(punch_time), str(sensor or '').strip().casefold()))
        if len(event) >= 5:
            last_in, last_out = event[3:5]
            values = punch_times.setdefault(user_id, [None, None])
            if last_in is not None:
                last_in = local_time(last_in)
                values[0] = max(values[0], last_in) if values[0] else last_in
            if last_out is not None:
                last_out = local_time(last_out)
                values[1] = max(values[1], last_out) if values[1] else last_out
    result = []
    for employee in roster:
        user_id, pname, unit, department, physical = employee[:5]
        branch_name = employee[5] if len(employee) > 5 else None
        user_id = str(user_id).strip()
        entries = latest.get(user_id, [])
        in_time = in_location = None
        unresolved = False
        reason = 'No punch in configured window'
        stamp = last_location = None
        event_locations = ()
        if entries:
            stamp = max(time for time, _ in entries)
            tied = [(time, sensor) for time, sensor in entries if time == stamp]
            kinds = {directions.get(sensor) for _, sensor in tied}
            places = {(device_locations.get(sensor) or '').strip() for _, sensor in tied}
            last_location = ', '.join(sorted(value for value in places if value)) or None
            event_locations = tuple(sorted(value for value in places if value))
            if stamp > now:
                unresolved = True
                reason = 'Future punch timestamp'
            elif None in kinds:
                unresolved = True
                reason = 'Unknown machine direction'
            elif len(kinds) != 1:
                unresolved = True
                reason = 'Conflicting IN/OUT at latest timestamp'
            elif kinds == {'IN'}:
                if len({value.casefold() for value in places}) == 1 and next(iter(places)):
                    in_time, in_location = stamp, next(iter(places))
                    reason = ''
                else:
                    unresolved = True
                    reason = 'Missing or conflicting IN machine location'
            else:
                reason = 'Latest punch is OUT'
        calculated_in = max((time for time, sensor in entries if directions.get(sensor) == 'IN'), default=None)
        calculated_out = max((time for time, sensor in entries if directions.get(sensor) == 'OUT'), default=None)
        last_in, last_out = punch_times.get(user_id, (calculated_in, calculated_out))
        result.append(OverviewEmployee(user_id, display_name(pname), unit,
                      department, physical, tuple(unit_locations.get(unit, {}).values()),
                      in_time, in_location, unresolved, reason, stamp, last_location, event_locations,
                      branch_name, last_in, last_out))
    return tuple(result)


def demo_employees(day):
    now = datetime.now(PAKISTAN)
    roster = demo_snapshot(day)
    people = []
    for index, person in enumerate(e for e in roster.employees if e.mapped):
        stamp = now - timedelta(hours=(2 if index % 2 else 14)) if index % 3 else None
        people.append(OverviewEmployee(person.id, person.name, person.unit,
                      person.department, None, person.locations, stamp,
                      person.locations[0] if stamp and person.locations else None,
                      last_in_time=stamp))
    with (ROOT / 'reference' / 'devices.csv').open(encoding='utf-8-sig', newline='') as source:
        devices = tuple((row['DeviceCode'], row['Location'], row['Unit']) for row in csv.DictReader(source))
    return EmployeeSnapshot(tuple(people), devices, now, day)


class SqlEmployees:
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, day):
        import pyodbc
        now = datetime.now(PAKISTAN)
        start = (now - timedelta(hours=self.settings.getint('employee_overview', 'lookback_hours'))).replace(tzinfo=None)
        db = self.settings['database']
        with closing(pyodbc.connect(build_connection_string(self.settings), autocommit=True,
                     readonly=True, timeout=db.getint('connection_timeout_seconds'))) as connection:
            connection.timeout = db.getint('query_timeout_seconds')
            with closing(connection.cursor()) as cursor:
                cursor.execute(PREFLIGHT_SQL)
                result = cursor.fetchone()
                if not result or result[0] != 'SPEL_ATTENDENCE' or result[1] != 2:
                    raise AttendanceUnavailable('Unexpected database or session isolation.')
                cursor.execute(ROSTER_SQL)
                roster = cursor.fetchall()
                cursor.execute(DEVICES_SQL)
                device_records = tuple(tuple(row) for row in cursor.fetchall())
                devices = tuple((code, location, unit) for code, location, unit, name in device_records)
                directions = {str(code): direction_from_name(name)
                              for code, location, unit, name in device_records}
                cursor.execute(EVENTS_SQL, start, now.replace(tzinfo=None))
                events = cursor.fetchall()
        people = build_employees(roster, devices, events, directions, now)
        return EmployeeSnapshot(people, devices, datetime.now(PAKISTAN), day)
