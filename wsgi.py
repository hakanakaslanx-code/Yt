"""
Gunicorn WSGI entry point — production server.
Başlatmak için:
  gunicorn -w 1 --worker-class gthread --threads 4 \
           -b 0.0.0.0:5000 --timeout 600 \
           --log-level info --access-logfile - \
           wsgi:app
"""
from app import app   # _startup() modül import edilince otomatik çalışır

__all__ = ['app']
