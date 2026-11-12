# app/utils/decorators.py
"""
Decoradores para autenticação, validação, etc.
"""

import logging
from functools import wraps
from flask import request, jsonify
from app.config.settings import load_config

logger = logging.getLogger(__name__)
config = load_config()

def require_auth(f):
    """Decorator para exigir autenticação via token (Header OU Query Param)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        query_token = request.args.get('token')
        token = None
        
        # 1. Prioriza Header Bearer
        if auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '')
        # 2. Aceita token via query parameter (para links de download)
        elif query_token:
            token = query_token
        
        if not token:
            return jsonify({'error': 'Token de autenticação requerido'}), 401
        
        expected_token = config.get('API_TOKEN')
        
        if not expected_token or token != expected_token:
            # Adicionado log de aviso para debug
            logger.warning(f"Token inválido. Fornecido: {token[:8]}...")
            return jsonify({'error': 'Token inválido'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

def require_json(f):
    """Decorator para exigir Content-Type JSON"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'Content-Type deve ser application/json'}), 400
        
        return f(*args, **kwargs)
    
    return decorated_function

def validate_webhook_token(f):
    """Decorator para validar token de webhook"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token webhook requerido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        expected_token = config.get('WEBHOOK_SECRET')
        
        if not expected_token or token != expected_token:
            return jsonify({'error': 'Token webhook inválido'}), 401
        
        return f(*args, **kwargs)
    

    return decorated_function
