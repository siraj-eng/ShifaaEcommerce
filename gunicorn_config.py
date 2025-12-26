"""
Gunicorn configuration for Render deployment
"""
import os
import multiprocessing

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', 5000)}"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "shifaa_herbal"

# Server mechanics
daemon = False
preload_app = True

# Performance
max_requests = 1000
max_requests_jitter = 50

