# gunicorn.conf.py
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes
workers = int(os.getenv('GUNICORN_WORKERS', '2'))
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv('LOG_LEVEL', 'info').lower()

# Process naming
proc_name = 'sankhya-woocommerce-sync'

# Server mechanics
preload_app = True
daemon = False
pidfile = '/tmp/gunicorn.pid'
user = None
group = None
tmp_upload_dir = None

def when_ready(server):
    server.log.info("Sankhya-WooCommerce Sync iniciado!")

def worker_int(worker):
    worker.log.info("Worker recebeu SIGINT")

def pre_fork(server, worker):
    server.log.info(f"Worker {worker.pid} sendo iniciado")

def post_fork(server, worker):
    server.log.info(f"Worker {worker.pid} iniciado com sucesso")