"""Read-only active biometric employees, grouped by assigned location/unit/department."""
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
import json

from flask import g, render_template, request

from dashboard.attendance import (AttendanceUnavailable, PAKISTAN, PREFLIGHT_SQL, QUERY_DIR,
                                  SharedAttendanceCache, demo_snapshot, display_name)
from dashboard.config import build_connection_string
from dashboard.employee_views import normalized_location

DIRECTORY_SQL = (QUERY_DIR / 'active_employee_directory.sql').read_text(encoding='utf-8')


@dataclass(frozen=True)
class DirectoryEmployee:
    id: str
    name: str
    pname: str | None
    unit: str | None
    department: str | None
    physical: str | None


@dataclass(frozen=True)
class DirectorySnapshot:
    employees: tuple
    loaded_at: datetime
    day: object


class SqlEmployeeDirectory:
    def __init__(self, settings):
        self.settings = settings

    def __call__(self, day):
        import pyodbc
        db = self.settings['database']
        with closing(pyodbc.connect(build_connection_string(self.settings), autocommit=True,
                     readonly=True, timeout=db.getint('connection_timeout_seconds'))) as connection:
            connection.timeout = db.getint('query_timeout_seconds')
            with closing(connection.cursor()) as cursor:
                cursor.execute(PREFLIGHT_SQL)
                row = cursor.fetchone()
                if not row or row[0] != 'SPEL_ATTENDENCE' or row[1] != 2:
                    raise AttendanceUnavailable('Unexpected database or session isolation.')
                cursor.execute(DIRECTORY_SQL)
                employees = tuple(DirectoryEmployee(str(identity).strip(), display_name(str(identity), name, pname),
                                  pname, unit, department, physical)
                                  for identity, name, pname, unit, department, physical in cursor.fetchall())
        return DirectorySnapshot(employees, datetime.now(PAKISTAN), day)


def demo_directory(day):
    snapshot = demo_snapshot(day)
    employees = tuple(DirectoryEmployee(person.id,person.name,person.name,person.unit,
                      person.department,person.locations[0] if person.locations else None)
                      for person in snapshot.employees if person.mapped)
    return DirectorySnapshot(employees,datetime.now(PAKISTAN),day)


def register_employee_directory(app, settings, live):
    interval = settings.getint('employee_directory','refresh_seconds')
    if not 10 <= interval <= 3600:
        raise ValueError('employee_directory.refresh_seconds must be between 10 and 3600.')
    aliases = {normalized_location(key):normalized_location(value)
               for key,value in settings.items('employee_location_aliases')} if settings.has_section('employee_location_aliases') else {}
    cache = SharedAttendanceCache(SqlEmployeeDirectory(settings) if live else demo_directory,interval)
    app.extensions['employee_directory_cache'] = cache

    @app.get('/employee-directory')
    def employee_directory():
        now = datetime.now(PAKISTAN)
        location = request.args.get('location','')
        account = getattr(g,'dashboard_user',None)
        if account and not account['is_admin']:
            location = json.dumps(normalized_location(account['location'],aliases))
        base = dict(today=now.strftime('%d %b %Y'),live=live,ttl=interval,location=location,
                    error=False,ui_colors=app.config['SPEL_UI_COLORS'],
                    wall_display=dict(settings.items('wall_display')))
        try:
            snapshot,stale = cache.get(now.date())
        except AttendanceUnavailable:
            return render_template('employee_directory.html',**base|{'error':True}),503
        locations = {}
        for person in snapshot.employees:
            value = normalized_location(person.physical,aliases)
            locations.setdefault(json.dumps(value), (person.physical or '').strip() or 'Not assigned')
        located = [person for person in snapshot.employees
                   if not location or json.dumps(normalized_location(person.physical,aliases)) == location]
        def label(value):
            return (value or '').strip() or 'Not assigned'
        selected = located
        details = []
        for person in sorted(selected,key=lambda person:person.id):
            employee_unit,employee_department = label(person.unit),label(person.department)
            details.append(dict(id=person.id,name=person.name,pname=person.pname or 'Not available',
                                unit=employee_unit,department=employee_department,physical=label(person.physical)))
        return render_template('employee_directory.html',**base,
                               locations=sorted(locations.items(),key=lambda item:item[1].casefold()),
                               total=len(selected),unit_count=len({label(person.unit) for person in selected}),
                               department_count=len({label(person.department) for person in selected}),
                               details=details,
                               stale=stale,loaded_at=snapshot.loaded_at.strftime('%H:%M:%S'))
