"""Server-side tab and location permissions, including explicit HR unit scopes."""
import json

from flask import abort, current_app, g

TABS = {
    'machines': ('Machines', '/'),
    'alerts': ('Attendance Alerts', '/employees'),
    'directory': ('Employees', '/employee-directory'),
    'hr_hours': ('HR Hours', '/hr-hours'),
}
ENDPOINT_TABS = {'machines': 'machines', 'employee_overview': 'alerts',
                 'employee_directory': 'directory', 'hr_hours': 'hr_hours',
                 'hr_comparison': 'hr_hours'}


def normalize(value, aliases=None):
    value = ' '.join(str(value or '').split()).casefold()
    return (aliases or {}).get(value, value)


def user():
    return getattr(g, 'dashboard_user', None)


def location_scope(account=None, aliases=None):
    account = user() if account is None else account
    if not account or account.get('is_admin') or account.get('all_locations'):
        return None
    values = account.get('locations', [account.get('location', '')])
    return {normalize(value, aliases) for value in values if normalize(value, aliases)}


def location_allowed(value, account=None, aliases=None):
    scope = location_scope(account, aliases)
    return scope is None or normalize(value, aliases) in scope


def safe_location_filter(value, account=None, aliases=None):
    if not value:
        return ''
    try:
        decoded = json.loads(value)
        if not isinstance(decoded, str):
            return ''
    except (ValueError, TypeError):
        return ''
    return value if location_allowed(decoded, account, aliases) else ''


def can_view(tab, account=None):
    account = user() if account is None else account
    return not account or account.get('is_admin') or tab in account.get('tabs', ())


def home(account):
    return next((url for key, (_, url) in TABS.items() if can_view(key, account)), '/account')


def hr_scope():
    """No inferred location join: restricted accounts require explicit HR units."""
    account = user()
    if location_scope(account) is None:
        return None
    store = current_app.extensions.get('user_store')
    if store is None:
        abort(403)
    units = store.hr_units(account.get('locations', [account.get('location', '')]))
    if not units:
        abort(403, description='No HR units are mapped to your assigned locations. Contact an administrator.')
    return {normalize(unit) for unit in units}


def unit_allowed(unit, scope):
    return scope is None or normalize(unit) in scope
