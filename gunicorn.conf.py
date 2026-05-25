# gunicorn.conf.py
import multiprocessing

# Número de workers baseado na CPU da VPS
workers = multiprocessing.cpu_count() * 2 + 1

# Worker class assíncrona
worker_class = "gevent"
worker_connections = 100

# Timeouts
timeout = 120
graceful_timeout = 60
keepalive = 5

# Reciclagem de workers (evita memory leak)
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Bind
bind = "0.0.0.0:5002"
