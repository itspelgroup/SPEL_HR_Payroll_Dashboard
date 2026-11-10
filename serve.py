"""Single-process threaded server: one cache shared across browser sessions."""
from waitress import serve

from app import create_app

if __name__ == '__main__':
    app = create_app()
    serve(app, host=app.config['SPEL_HOST'], port=app.config['SPEL_PORT'],
          threads=app.config['SPEL_THREADS'])
