"""INI-backed authentication and administrative account management."""
import argparse
from contextlib import contextmanager
from datetime import timedelta
from getpass import getpass
import hmac
from pathlib import Path
import secrets
import sqlite3
import threading
import time

from flask import abort, g, redirect, render_template, request, session
from dashboard.config import ROOT, load_settings
from dashboard.account_store import (IniUserStore, AccountStoreError, public_account,
                                     verify_password, account_token, valid_password)
from dashboard.access import TABS, ENDPOINT_TABS, can_view, home

AUTH_DIR = ROOT / 'instance'

@contextmanager
def connect_users(folder):
    folder.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(folder / 'users.sqlite3')
    connection.row_factory = sqlite3.Row
    connection.execute('CREATE TABLE IF NOT EXISTS users ('
                       'username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, '
                       'location TEXT, is_admin INTEGER NOT NULL DEFAULT 0)')
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def install_auth(app, settings, live):
    enabled = settings.getboolean('security', 'enabled', fallback=False)
    app.config['SPEL_AUTH_ENABLED'] = enabled
    app.config['MAX_CONTENT_LENGTH'] = 128 * 1024
    folder = Path(settings.get('security', 'account_directory', fallback=str(AUTH_DIR)))
    if not folder.is_absolute():
        folder = ROOT / folder
    user_path = Path(settings.get('security', 'user_file', fallback=str(folder / 'users.ini')))
    if not user_path.is_absolute():
        user_path = ROOT / user_path
    store = IniUserStore(user_path, settings.get('security', 'password_storage', fallback='plain'),
                         settings.getint('security', 'minimum_password_length', fallback=8))
    app.extensions['user_store'] = store
    if enabled:
        store.initialize(folder)
        folder.mkdir(parents=True, exist_ok=True)
        secret_path = folder / 'session.key'
        try:
            with secret_path.open('x', encoding='ascii') as stream:
                stream.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        app.secret_key = secret_path.read_text(encoding='ascii')
        app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                          SESSION_COOKIE_SECURE=settings.getboolean('security', 'cookie_secure', fallback=False),
                          PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    attempts = {}
    lock = threading.Lock()

    def csrf_check():
        expected = session.get('csrf', '')
        if not expected or not hmac.compare_digest(expected.encode(), request.form.get('csrf', '').encode()):
            abort(400)

    @app.before_request
    def identify_user():
        g.dashboard_user = None
        if not enabled or request.endpoint == 'static':
            return
        try:
            data = store.read()
        except AccountStoreError:
            abort(503, description='Account configuration unavailable. Contact the administrator.')
        account = data['users'].get(session.get('username'))
        if account and account['enabled'] and session.get('revision') == account_token(account):
            g.dashboard_user = public_account(account)
        elif session.get('username'):
            session.clear()
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if request.endpoint is None:
            return
        if request.endpoint not in ('login', 'setup') and not g.dashboard_user:
            return redirect('/login' if data['users'] else '/setup')
        if g.dashboard_user:
            if request.endpoint in ('settings_users', 'attendance') and not g.dashboard_user['is_admin']:
                abort(403)
            tab = ENDPOINT_TABS.get(request.endpoint)
            if tab and not can_view(tab):
                if request.endpoint == 'machines':
                    return redirect(home(g.dashboard_user))
                abort(403)
            session.permanent = True

    @app.after_request
    def private_dashboard(response):
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response

    @app.context_processor
    def user_context():
        return dict(dashboard_user=getattr(g, 'dashboard_user', None), can_view_tab=can_view,
                    auth_enabled=enabled, csrf_token=session.get('csrf', '') if enabled else '')

    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        if not enabled:
            return redirect('/')
        if store.read()['users']:
            return redirect('/login')
        if request.remote_addr not in ('127.0.0.1', '::1'):
            abort(403, description='Create the first administrator on the server using localhost.')
        error = None
        if request.method == 'POST':
            csrf_check()
            try:
                store.save_user(request.form.get('username', ''), password=request.form.get('password', ''),
                                is_admin=True, all_locations=True, tabs=list(TABS), create=True, bootstrap=True)
                return redirect('/login')
            except (ValueError, AccountStoreError) as exc:
                error = str(exc)
        return render_template('account_setup.html', error=error, minimum=store.minimum_password_length)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if not enabled:
            return redirect('/')
        if not store.read()['users']:
            return redirect('/setup')
        if g.dashboard_user:
            return redirect(home(g.dashboard_user))
        error = None
        if request.method == 'POST':
            csrf_check()
            username = request.form.get('username', '').strip().casefold()
            key = (request.remote_addr, username)
            now = time.monotonic()
            with lock:
                for expired in [k for k, (_, until) in attempts.items() if until <= now]:
                    attempts.pop(expired, None)
                count, until = attempts.get(key, (0, now + 900))
            if count >= 5:
                return render_template('login.html', error='Too many attempts. Try again in 15 minutes.'), 429
            account = store.read()['users'].get(username)
            if account and account['enabled'] and verify_password(account, request.form.get('password', '')):
                with lock:
                    attempts.pop(key, None)
                session.clear()
                session.update(username=username, revision=account_token(account), csrf=secrets.token_urlsafe(32))
                session.permanent = True
                return redirect(home(account))
            with lock:
                attempts[key] = (count + 1, until)
            error = 'Username or password is incorrect.'
        return render_template('login.html', error=error)

    @app.post('/logout')
    def logout():
        if enabled:
            csrf_check()
        session.clear()
        return redirect('/login')

    @app.route('/settings', methods=['GET', 'POST'])
    def settings_users():
        if not enabled:
            abort(403, description='Enable authentication to manage users.')
        error = None
        if request.method == 'POST':
            csrf_check()
            try:
                if request.form.get('action') == 'location':
                    store.save_location(request.form.get('label', ''), request.form.get('hr_units', '').splitlines())
                elif request.form.get('action') in ('create', 'edit'):
                    result = store.save_user(request.form.get('username', ''),
                        password=request.form.get('password', ''), enabled='enabled' in request.form,
                        is_admin='is_admin' in request.form, all_locations='all_locations' in request.form,
                        tabs=request.form.getlist('tabs'), locations=request.form.getlist('locations'),
                        create=request.form['action'] == 'create')
                    if result['username'] == g.dashboard_user['username']:
                        session['revision'] = account_token(store.read()['users'][result['username']])
                else:
                    raise ValueError('Unknown settings action.')
                return redirect('/settings?saved=1')
            except (ValueError, AccountStoreError) as exc:
                error = str(exc)
        data = store.read()
        return render_template('settings.html', error=error, saved=request.args.get('saved') == '1',
            accounts=[public_account(v) for _, v in sorted(data['users'].items())],
            location_map=data['locations'], tabs=TABS, storage=store.password_storage,
            minimum=store.minimum_password_length)

    @app.route('/account', methods=['GET', 'POST'])
    def account_password():
        if not enabled:
            abort(403)
        error = None
        if request.method == 'POST':
            csrf_check()
            try:
                password = request.form.get('password', '')
                if not password:
                    raise ValueError('Enter a new password.')
                if password != request.form.get('confirm_password', ''):
                    raise ValueError('New passwords must match.')
                result = store.change_password(g.dashboard_user['username'],
                    request.form.get('current_password', ''), password, session['revision'])
                session['revision'] = account_token(store.read()['users'][result['username']])
                return redirect('/account?saved=1')
            except (ValueError, AccountStoreError) as exc:
                error = str(exc)
        return render_template('account_password.html', error=error, saved=request.args.get('saved') == '1',
                               minimum=store.minimum_password_length)


def main():
    parser = argparse.ArgumentParser(description='Create/reset a local INI dashboard account.')
    parser.add_argument('--username', required=True)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--admin', action='store_true')
    scope.add_argument('--location', action='append')
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    settings = load_settings(args.config)
    folder = args.directory or Path(settings.get('security', 'account_directory', fallback=str(AUTH_DIR)))
    if not folder.is_absolute():
        folder = ROOT / folder
    path = folder / 'users.ini' if args.directory else Path(settings.get('security', 'user_file', fallback=str(folder / 'users.ini')))
    if not path.is_absolute():
        path = ROOT / path
    store = IniUserStore(path, settings.get('security', 'password_storage', fallback='plain'),
                         settings.getint('security', 'minimum_password_length', fallback=8))
    store.initialize(folder)
    password = getpass('New password: ')
    if password != getpass('Confirm password: '):
        parser.error('Passwords must match.')
    if not valid_password(password, store.minimum_password_length):
        parser.error('Password is too short or contains surrounding spaces/control characters.')
    try:
        for label in args.location or []:
            if label not in store.read()['locations']:
                store.save_location(label, [])
        store.save_user(args.username, password=password, is_admin=args.admin, all_locations=args.admin,
            tabs=list(TABS) if args.admin else ['machines', 'alerts', 'directory'], locations=args.location or [],
            create=args.username.strip().casefold() not in store.read()['users'])
    except (ValueError, AccountStoreError) as exc:
        parser.error(str(exc))
    print('Dashboard account saved. SQL data was not changed.')


if __name__ == '__main__':
    main()
