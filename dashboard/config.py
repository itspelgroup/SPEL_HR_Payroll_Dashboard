"""INI configuration and ODBC string preparation; this module never connects."""
import configparser
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_settings(path=None):
    # Disable interpolation so passwords containing % are read literally.
    settings = configparser.ConfigParser(interpolation=None)
    settings.read(ROOT / 'config.example.ini', encoding='utf-8')
    local_path = Path(path or os.environ.get('SPEL_CONFIG_FILE', ROOT / 'config.ini'))
    if path is not None and not local_path.is_file():
        raise ValueError('Configuration file does not exist.')
    settings.read(local_path, encoding='utf-8')
    return settings


def build_connection_string(settings):
    """Prepare only. ReadOnly intent is advisory, not a permission boundary."""
    raw = os.environ.get('SPEL_SQL_CONNECTION_STRING') or settings.get(
        'database', 'connection_string', fallback='').strip()
    if raw:
        return raw
    db = settings['database']

    def quoted(value):
        return '{' + value.replace('}', '}}') + '}'

    parts = [f'DRIVER={quoted(db["driver"])}',
             f'SERVER={quoted(db["server"])}',
             f'DATABASE={quoted(db["database"])}']
    auth = db.get('authentication', 'sql').lower()
    if auth == 'windows':
        parts.append('Trusted_Connection=yes')
    elif auth == 'sql':
        password = os.environ.get('SPEL_SQL_PASSWORD', db.get('password', ''))
        if not db.get('username') or not password:
            raise ValueError('SQL username and password are required.')
        parts.extend([f'UID={quoted(db["username"])}', f'PWD={quoted(password)}'])
    else:
        raise ValueError('Database authentication must be sql or windows.')
    parts.extend([
        'Encrypt=' + ('yes' if db.getboolean('encrypt') else 'no'),
        'TrustServerCertificate=' + ('yes' if db.getboolean('trust_server_certificate') else 'no'),
        'ApplicationIntent=ReadOnly',
    ])
    return ';'.join(parts) + ';'
