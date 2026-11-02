"""Local dashboard accounts; independent of attendance database credentials."""
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
from werkzeug.security import check_password_hash, generate_password_hash

from dashboard.config import ROOT

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
    # Authentication is deferred until the user requests its activation.
    enabled = settings.getboolean('security', 'enabled', fallback=False)
    app.config['SPEL_AUTH_ENABLED'] = enabled
    folder = Path(settings.get('security', 'account_directory', fallback=str(AUTH_DIR)))
    if enabled:
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

    @app.before_request
    def identify_user():
        g.dashboard_user = None
        if not enabled or request.endpoint == 'static':
            return
        username = session.get('username')
        if username:
            with connect_users(folder) as connection:
                account = connection.execute('SELECT username, location, is_admin FROM users '
                                             'WHERE username=?', (username,)).fetchone()
            if account:
                g.dashboard_user = dict(account)
        if request.endpoint not in ('login', 'static') and not g.dashboard_user:
            return redirect('/login')
        if request.endpoint == 'attendance' and g.dashboard_user and not g.dashboard_user['is_admin']:
            abort(403)
        if request.endpoint in ('machines', 'attendance'):
            # Employee and machine details must not be stored in browser caches.
            session.permanent = True

    @app.after_request
    def private_dashboard(response):
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.context_processor
    def user_context():
        return dict(dashboard_user=getattr(g, 'dashboard_user', None),
                    csrf_token=session.get('csrf', '') if enabled else '')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if not enabled:
            return redirect('/')
        if g.dashboard_user:
            return redirect('/')
        session.setdefault('csrf', secrets.token_urlsafe(32))
        error = None
        if request.method == 'POST':
            if not hmac.compare_digest(session['csrf'], request.form.get('csrf', '')):
                abort(400)
            username = request.form.get('username', '').strip().casefold()
            key = (request.remote_addr, username)
            now = time.monotonic()
            with lock:
                for expired in [k for k, (_, until) in attempts.items() if until <= now]:
                    attempts.pop(expired, None)
                count, until = attempts.get(key, (0, now + 900))
            if count >= 5:
                return render_template('login.html', error='Too many attempts. Try again in 15 minutes.'), 429
            with connect_users(folder) as connection:
                account = connection.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            if account and check_password_hash(account['password_hash'], request.form.get('password', '')):
                with lock:
                    attempts.pop(key, None)
                session.clear()
                session.update(username=username, csrf=secrets.token_urlsafe(32))
                session.permanent = True
                return redirect('/')
            with lock:
                attempts[key] = (count + 1, until)
            error = 'Username or password is incorrect.'
        return render_template('login.html', error=error)

    @app.post('/logout')
    def logout():
        if enabled and not hmac.compare_digest(session.get('csrf', ''), request.form.get('csrf', '')):
            abort(400)
        session.clear()
        return redirect('/login')


def main():
    parser = argparse.ArgumentParser(description='Create or update a dashboard account locally.')
    parser.add_argument('--username', required=True)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument('--admin', action='store_true')
    scope.add_argument('--location')
    parser.add_argument('--directory', type=Path, default=AUTH_DIR)
    args = parser.parse_args()
    username = args.username.strip().casefold()
    location = (args.location or '').strip()
    if not username or (not args.admin and not location):
        parser.error('Provide a username and an exact device location, or --admin.')
    password = getpass('Password (at least 12 characters): ')
    if len(password) < 12 or password != getpass('Confirm password: '):
        parser.error('Passwords must match and contain at least 12 characters.')
    with connect_users(args.directory) as connection:
        connection.execute('INSERT INTO users VALUES (?, ?, ?, ?) ON CONFLICT(username) '
                           'DO UPDATE SET password_hash=excluded.password_hash, '
                           'location=excluded.location, is_admin=excluded.is_admin',
                           (username, generate_password_hash(password), location or None, int(args.admin)))
    print('Dashboard account saved. Attendance SQL data was not changed.')


if __name__ == '__main__':
    main()
