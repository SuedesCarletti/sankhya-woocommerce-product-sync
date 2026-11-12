# app/routes/__init__.py
"""
Rotas da aplicação Flask
"""

from .api import api_bp
from .webhooks import webhooks_bp
from .health import health_bp
from .nfe_proxy import nfe_bp  # FIX: Corrigido de .nfe para .nfe_proxy

__all__ = ['api_bp', 'webhooks_bp', 'health_bp', 'nfe_bp']
