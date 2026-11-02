"""Read-only machine inventory and receipt-based activity status."""
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import csv

from dashboard.attendance import PAKISTAN, PREFLIGHT_SQL, QUERY_DIR, AttendanceUnavailable
from dashboard.config import ROOT, build_connection_string

MACHINE_SQL = (QUERY_DIR / 'machine_snapshot.sql').read_text(encoding='utf-8')
RECENT_PUNCH_SQL = (QUERY_DIR / 'machine_recent_punches.sql').read_text(encoding='utf-8')


@dataclass(frozen=True)
class MachinePunch:
    event_id: int
    user_id: str
    punch_time: datetime
    received_at: datetime
    pname: str | None
    employee_unit: str | None
    physical_location: str | None


@dataclass(frozen=True)
class Machine:
    code: str
    name: str
    location: str | None
    unit: str | None
    active: bool
    last_punch: datetime | None
    last_received: datetime | None
    user_id: str | None = None
    punch_time: datetime | None = None
    pname: str | None = None
    physical_location: str | None = None
    punches: tuple = ()


@dataclass(frozen=True)
class MachineSnapshot:
    machines: tuple
    loaded_at: datetime
    day: object


def machine_status(machine, now, recent_minutes, delayed_minutes):
    if not machine.active:
        return 'Disabled'
    if machine.last_punch is None:
        return 'No punches received'
    received = machine.last_punch
    if received.tzinfo is None:
        received = received.replace(tzinfo=PAKISTAN)
    age = (now - received).total_seconds() / 60
    if age < 0:
        return 'Check timestamp'
    if age < recent_minutes:
        return 'Recent'
    if age <= delayed_minutes:
        return 'Delayed'
    return 'No recent punches'


def recent_punch(value, now, minutes=10):
    if value is None:
        return False
    value = value.replace(tzinfo=PAKISTAN) if value.tzinfo is None else value
    return 0 <= (now - value).total_seconds() < minutes * 60


def demo_machines(day):
    now = datetime.now(PAKISTAN)
    with (ROOT / 'reference' / 'devices.csv').open(encoding='utf-8-sig', newline='') as source:
        machines = []
        for index, row in enumerate(csv.DictReader(source)):
            received = None if index % 4 == 3 else now - timedelta(minutes=(10, 120, 1800)[index % 4])
            machines.append(Machine(row['DeviceCode'], row['Name'], row['Location'],
                                    row['Unit'], row['Active'] == '1', received, received))
    return MachineSnapshot(tuple(machines), now, day)


class SqlMachines:
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, day):
        import pyodbc
        db = self.settings['database']
        with closing(pyodbc.connect(build_connection_string(self.settings),
                     autocommit=True, readonly=True,
                     timeout=db.getint('connection_timeout_seconds'))) as connection:
            connection.timeout = db.getint('query_timeout_seconds')
            with closing(connection.cursor()) as cursor:
                cursor.execute(PREFLIGHT_SQL)
                result = cursor.fetchone()
                if not result or result[0] != 'SPEL_ATTENDENCE' or result[1] != 2:
                    raise AttendanceUnavailable('Unexpected database or session isolation.')
                cursor.execute(MACHINE_SQL)
                machines = tuple(Machine(*row) for row in cursor.fetchall())
                cursor.execute(RECENT_PUNCH_SQL, self.settings.getint('punch_history', 'limit'))
                history = {}
                for code, event_id, user_id, punch_time, received_at, pname, unit, physical in cursor.fetchall():
                    history.setdefault(code, []).append(MachinePunch(
                        event_id, str(user_id), punch_time, received_at, pname, unit, physical))
                machines = tuple(replace(machine, punches=tuple(history.get(machine.code, ())))
                                 for machine in machines)
        return MachineSnapshot(machines, datetime.now(PAKISTAN), day)
