"""Fixed attendance SELECT and a shared, single-process cache."""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import re
from threading import Lock
from time import monotonic

from dashboard.config import build_connection_string
from dashboard.demo import EMPLOYEES, PUNCHED_IDS

PAKISTAN = timezone(timedelta(hours=5))
QUERY_DIR = Path(__file__).resolve().parent.parent / 'sql' / 'dashboard'
PREFLIGHT_SQL = (QUERY_DIR / 'connection_preflight.sql').read_text(encoding='utf-8')
EMPLOYEE_SQL = (QUERY_DIR / 'employee_snapshot.sql').read_text(encoding='utf-8')


@dataclass(frozen=True)
class Group:
    unit: str | None
    department: str | None
    registered: int
    punched: int


@dataclass(frozen=True)
class Employee:
    id: str
    name: str
    unit: str | None
    department: str | None
    punched: bool
    mapped: bool
    locations: tuple = ()


def display_name(employee_id, name, pname):
    def proper(value):
        value = (value or '').strip()
        if not value or value.casefold() in {'null', 'none', 'unknown', 'n/a', 'na', '-', 'employee', 'user'}:
            return False
        if value.casefold() == employee_id.strip().casefold():
            return False
        if re.fullmatch(r'(user|employee|emp)[\s_-]*\d+', value, re.I):
            return False
        return any(character.isalpha() for character in value)
    return next((value.strip() for value in (name, pname) if proper(value)), 'Name unavailable')


@dataclass(frozen=True)
class Snapshot:
    groups: tuple
    unmapped: int
    loaded_at: datetime
    day: object
    employees: tuple = ()


def make_snapshot(employees, day):
    groups = {}
    for employee in employees:
        if not employee.mapped:
            continue
        counts = groups.setdefault((employee.unit, employee.department), [0, 0])
        counts[0] += 1
        counts[1] += employee.punched
    return Snapshot(tuple(Group(*key, *counts) for key, counts in groups.items()),
                    sum(not e.mapped for e in employees), datetime.now(PAKISTAN), day,
                    tuple(employees))


class AttendanceUnavailable(Exception):
    """Safe error for display, without driver/connection details."""


def demo_snapshot(day):
    mapping = {'UNIT3': ('Pandoki',), 'UNIT5RYK': ('RahimYarkhan',),
               'UNIT6': ('HeadOffice',), 'UNIT8': ('Karachi',)}
    employees = [Employee(e['id'], 'Sample employee ' + e['id'][-3:], e['unit'],
                          e['department'], e['id'] in PUNCHED_IDS, True,
                          mapping.get(e['unit'], ())) for e in EMPLOYEES]
    employees.extend(Employee(i, 'Name unavailable', None, None, True, False)
                     for i in PUNCHED_IDS - {e['id'] for e in EMPLOYEES})
    return make_snapshot(employees, day)


class SqlAttendance:
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, day):
        # Lazy import/connection: constructing the app never contacts SQL Server.
        import pyodbc
        start = datetime.combine(day, time.min)
        end = start + timedelta(days=1)
        db = self.settings['database']
        with closing(pyodbc.connect(
            build_connection_string(self.settings), autocommit=True, readonly=True,
            timeout=db.getint('connection_timeout_seconds'),
        )) as connection:
            connection.timeout = db.getint('query_timeout_seconds')
            with closing(connection.cursor()) as cursor:
                # Reject overrides pointing elsewhere or unexpected isolation.
                cursor.execute(PREFLIGHT_SQL)
                preflight = cursor.fetchone()
                if not preflight or preflight[0] != 'SPEL_ATTENDENCE' or preflight[1] != 2:
                    raise AttendanceUnavailable('Unexpected database or session isolation.')
                cursor.execute(EMPLOYEE_SQL, start, end)
                records = {}
                for employee_id, name, pname, unit, department, punched_id, location in cursor.fetchall():
                    mapped = employee_id is not None
                    identity = str(employee_id if mapped else punched_id)
                    key = (mapped, identity)
                    if key not in records:
                        records[key] = dict(id=identity, name=display_name(identity, name, pname),
                                            unit=unit, department=department,
                                            punched=punched_id is not None, mapped=mapped,
                                            locations={})
                    if location and location.strip():
                        # SQL often compares locations case-insensitively. Merge
                        # casing variants only; preserve different unit spellings.
                        records[key]['locations'].setdefault(location.strip().casefold(), location.strip())
                employees = [Employee(**(record | {'locations': tuple(record['locations'].values())}))
                             for record in records.values()]
        return make_snapshot(employees, day)


class SharedAttendanceCache:
    """One refresh shared by users/threads; not shared between server processes.

    Date is the cache key; filters never trigger new SQL reads. A failed refresh
    keeps same-day data as stale and backs off one TTL. Yesterday is not reused.
    """
    def __init__(self, loader, ttl, clock=monotonic):
        self.loader, self.ttl, self.clock = loader, ttl, clock
        self.lock = Lock()
        self.snapshot = None
        self.next_refresh = 0
        self.attempt_day = None
        self.failed = False

    def get(self, day):
        with self.lock:
            if self.attempt_day != day or self.clock() >= self.next_refresh:
                try:
                    loaded = self.loader(day)
                except Exception:
                    # Do not log driver exceptions: may contain credentials.
                    self.failed = True
                else:
                    self.snapshot = loaded
                    self.failed = False
                self.attempt_day = day
                self.next_refresh = self.clock() + self.ttl
            if self.snapshot is None or self.snapshot.day != day:
                raise AttendanceUnavailable('Attendance source unavailable.')
            return self.snapshot, self.failed
