# app/routes/health.py
"""
Health checks e monitoramento
"""

import logging
from flask import Blueprint, jsonify
from datetime import datetime

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)

@health_bp.route('/', methods=['GET'])
@health_bp.route('/ping', methods=['GET'])
def ping():
    """Health check básico"""
    return jsonify({
        'status': 'healthy',
        'service': 'sankhya-woocommerce-sync',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

@health_bp.route('/ready', methods=['GET'])
def ready():
    """Readiness check - verifica se está pronto para receber tráfego"""
    try:
        # Verificações básicas
        checks = {
            'database': True,  # Adicionar verificação se usar BD
            'sankhya_config': True,  # Verificar se configs estão presentes
            'woocommerce_config': True
        }
        
        # Verificar configurações essenciais
        from app.config.settings import load_config
        config = load_config()
        
        required_configs = [
            'SANKHYA_TOKEN', 'SANKHYA_APPKEY', 
            'WOOCOMMERCE_URL', 'WOOCOMMERCE_CONSUMER_KEY'
        ]
        
        for cfg in required_configs:
            if not config.get(cfg):
                checks[f'config_{cfg.lower()}'] = False
        
        all_healthy = all(checks.values())
        
        return jsonify({
            'status': 'ready' if all_healthy else 'not_ready',
            'checks': checks,
            'timestamp': datetime.utcnow().isoformat()
        }), 200 if all_healthy else 503
        
    except Exception as e:
        logger.error(f"Erro no health check: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@health_bp.route('/live', methods=['GET'])
def live():
    """Liveness check - verifica se a aplicação está viva"""
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat()
    }), 200