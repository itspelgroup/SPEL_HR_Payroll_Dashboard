"""Atomic local INI account storage. No SQL Server writes or account tables."""
import configparser
from contextlib import closing
import csv
import hmac
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import tempfile
import threading

from werkzeug.security import check_password_hash, generate_password_hash

from dashboard.access import TABS, normalize
from dashboard.config import ROOT


class AccountStoreError(Exception):
    pass


def valid_password(password, minimum=8):
    return (len(password) >= minimum and len(password) <= 512 and password == password.strip()
            and not any(ord(c) < 32 for c in password))


def account_token(account):
    # File edits to credentials or permissions also invalidate existing sessions.
    return hashlib.sha256(json.dumps(account, sort_keys=True).encode('utf-8')).hexdigest()


def verify_password(account, supplied):
    saved = account.get('password', '')
    if account.get('password_format') == 'hash':
        try:
            return check_password_hash(saved, supplied)
        except (ValueError, TypeError):
            return False
    return bool(saved) and hmac.compare_digest(saved.encode('utf-8'), supplied.encode('utf-8'))


def public_account(account):
    return {key: value for key, value in account.items() if key not in ('password', 'password_format')}


class IniUserStore:
    def __init__(self, path, password_storage='plain', minimum_password_length=8):
        self.path = Path(path)
        self.password_storage = password_storage
        self.minimum_password_length = minimum_password_length
        if password_storage not in ('plain', 'hash') or not 8 <= minimum_password_length <= 128:
            raise ValueError('Invalid password storage/minimum length settings.')
        self.lock = threading.RLock()

    def _read(self):
        data = {'users': {}, 'locations': {}}
        if not self.path.exists():
            return data
        parser = configparser.ConfigParser(interpolation=None)
        try:
            with self.path.open(encoding='utf-8-sig') as stream:
                parser.read_file(stream)
            for section in parser.sections():
                values = parser[section]
                if section.startswith('location:'):
                    label = section[9:]
                    units = json.loads(values.get('hr_units', '[]'))
                    if not isinstance(units, list) or not all(isinstance(v, str) for v in units):
                        raise ValueError()
                    data['locations'][label] = units
                elif section.startswith('user:'):
                    name = section[5:]
                    tabs = json.loads(values.get('tabs', '[]'))
                    locations = json.loads(values.get('locations', '[]'))
                    if (not re.fullmatch(r'[a-z0-9_.-]{1,64}', name) or not isinstance(tabs, list)
                            or not all(value in TABS for value in tabs)
                            or not isinstance(locations, list) or not all(isinstance(v, str) for v in locations)):
                        raise ValueError()
                    storage = values.get('password_format', 'plain')
                    if storage not in ('plain', 'hash'):
                        raise ValueError()
                    data['users'][name] = dict(username=name, password=values.get('password', ''),
                        password_format=storage, enabled=values.getboolean('enabled', True),
                        is_admin=values.getboolean('is_admin', False),
                        all_locations=values.getboolean('all_locations', False),
                        tabs=tabs, locations=locations, revision=values.get('revision', 'manual'))
            owners = {}
            labels = set()
            for label, units in data['locations'].items():
                if not normalize(label) or normalize(label) in labels:
                    raise ValueError()
                labels.add(normalize(label))
                for unit in units:
                    key = normalize(unit)
                    if not key or (key in owners and owners[key] != normalize(label)):
                        raise ValueError()
                    owners[key] = normalize(label)
            return data
        except (configparser.Error, ValueError, TypeError, OSError, UnicodeError) as error:
            raise AccountStoreError('User configuration is unavailable or invalid.') from error

    def read(self):
        with self.lock:
            return self._read()

    def _write(self, data):
        parser = configparser.ConfigParser(interpolation=None)
        parser['meta'] = {'format_version': '1', 'new_password_storage': self.password_storage}
        for label, units in sorted(data['locations'].items(), key=lambda pair: pair[0].casefold()):
            parser['location:' + label] = {'hr_units': json.dumps(units, ensure_ascii=False)}
        for name, account in sorted(data['users'].items()):
            parser['user:' + name] = {key: ('true' if value else 'false') if isinstance(value, bool)
                else json.dumps(value, ensure_ascii=False) if isinstance(value, list) else str(value)
                for key, value in account.items() if key != 'username'}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent,
                    prefix='.users-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write('; Local account file. Contains credentials; never publish or commit.\n')
                parser.write(stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def initialize(self, legacy_folder=None):
        with self.lock:
            if self.path.exists():
                self._read()
                return
            data = self._read()
            reference = ROOT / 'reference' / 'devices.csv'
            if reference.exists():
                with reference.open(encoding='utf-8-sig', newline='') as source:
                    for row in csv.DictReader(source):
                        label = row.get('Location', '').strip()
                        if label and normalize(label) not in {normalize(v) for v in data['locations']}:
                            data['locations'][label] = []
            legacy = Path(legacy_folder) / 'users.sqlite3' if legacy_folder else None
            if legacy and legacy.exists():
                # Read-only one-time migration; existing hashes are not decrypted.
                with closing(sqlite3.connect(legacy.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
                    for name, password_hash, location, admin in connection.execute(
                            'SELECT username,password_hash,location,is_admin FROM users'):
                        name = name.strip().casefold()
                        locations = [location.strip()] if location and location.strip() else []
                        data['users'][name] = dict(username=name, password=password_hash,
                            password_format='hash', enabled=True, is_admin=bool(admin),
                            all_locations=bool(admin), tabs=list(TABS) if admin else ['machines','alerts','directory'],
                            locations=locations, revision=secrets.token_hex(16))
                        for label in locations:
                            data['locations'].setdefault(label, [])
            self._write(data)

    def save_user(self, name, *, password='', enabled=True, is_admin=False,
                  all_locations=False, tabs=(), locations=(), create=False, bootstrap=False):
        name = name.strip().casefold()
        if not re.fullmatch(r'[a-z0-9_.-]{1,64}', name):
            raise ValueError('Username must use letters, numbers, dot, hyphen or underscore (max 64).')
        if any(value not in TABS for value in tabs):
            raise ValueError('Unknown tab permission.')
        if not is_admin and (not tabs or (not all_locations and not locations)):
            raise ValueError('Choose at least one tab and one location, or allow all locations.')
        if password and not valid_password(password, self.minimum_password_length):
            raise ValueError('Password must have at least ' + str(self.minimum_password_length) + ' characters, with no surrounding spaces or control characters.')
        with self.lock:
            data = self._read()
            existing = data['users'].get(name)
            if bootstrap and data['users']:
                raise ValueError('Initial setup is already complete.')
            if create and existing:
                raise ValueError('This username already exists.')
            if not create and not existing:
                raise ValueError('User does not exist.')
            if not existing and not password:
                raise ValueError('A password is required for a new user.')
            if any(normalize(label) not in {normalize(v) for v in data['locations']} for label in locations):
                raise ValueError('Add the location before assigning it to a user.')
            saved = generate_password_hash(password) if password and self.password_storage == 'hash' else password
            account = dict(username=name, password=saved if password else existing['password'],
                password_format=self.password_storage if password else existing['password_format'],
                enabled=bool(enabled), is_admin=bool(is_admin), all_locations=bool(all_locations),
                tabs=list(dict.fromkeys(tabs)), locations=list(dict.fromkeys(locations)), revision=secrets.token_hex(16))
            data['users'][name] = account
            if not any(v['is_admin'] and v['enabled'] for v in data['users'].values()):
                raise ValueError('At least one enabled administrator must remain.')
            self._write(data)
            return public_account(account)

    def save_location(self, label, units):
        label = ' '.join(label.split())
        if not label or len(label) > 100 or any(c in label for c in '\r\n[]'):
            raise ValueError('Enter a location name (max 100 characters, without brackets).')
        units = list(dict.fromkeys(text.strip() for text in units if text.strip()))
        if any(len(unit) > 500 or any(ord(c) < 32 for c in unit) for unit in units):
            raise ValueError('Invalid HR unit label.')
        with self.lock:
            data = self._read()
            label = next((old for old in data['locations'] if normalize(old) == normalize(label)), label)
            for other, existing_units in data['locations'].items():
                if other != label and {normalize(v) for v in units} & {normalize(v) for v in existing_units}:
                    raise ValueError('An HR unit cannot belong to multiple locations.')
            data['locations'][label] = units
            self._write(data)

    def hr_units(self, locations):
        allowed = {normalize(value) for value in locations}
        return {unit for label, units in self.read()['locations'].items() if normalize(label) in allowed for unit in units}

    def change_password(self, username, current_password, password, expected_token):
        with self.lock:
            account = self._read()['users'].get(username)
            if (not account or not account['enabled'] or account_token(account) != expected_token
                    or not verify_password(account, current_password)):
                raise ValueError('Current password or session is no longer valid. Sign in again.')
            return self.save_user(username, password=password, enabled=account['enabled'],
                is_admin=account['is_admin'], all_locations=account['all_locations'],
                tabs=account['tabs'], locations=account['locations'])
