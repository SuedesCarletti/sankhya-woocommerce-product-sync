# app/main.py - CORREÇÃO RÁPIDA
# Remove a tentativa de carregar blueprint NFe que não existe
# Use este arquivo se quiser apenas corrigir o erro 404 rapidamente

import os
import sys
import logging
from datetime import datetime
from werkzeug.exceptions import HTTPException

from app.utils.logger import setup_logger, get_logger

print("main.py: Iniciando imports...")

try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    print("Flask imports OK")
except Exception as e:
    print(f"Flask import error: {e}")
    raise

logger = logging.getLogger(__name__)

def create_app():
    """Factory simplificada para criar aplicação Flask"""
    print("Criando aplicação Flask...")
    
    app = Flask(__name__)
    
    # Configurar logger estruturado
    global logger
    logger = setup_logger(app)
    print("Logger estruturado configurado")
    
    # Configurações mínimas
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-key-for-testing'),
        'DEBUG': os.getenv('FLASK_ENV') == 'development'
    })
    
    # CORS restrito: só as origens listadas em CORS_ORIGINS (vazio = mesma origem)
    CORS(app, origins=[o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()])
    
    print("Flask app criada")
    
    # Rotas essenciais primeiro
    @app.route('/')
    def index():
        return jsonify({
            'service': 'Sankhya-WooCommerce Sync',
            'version': '1.0.0',
            'status': 'running',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @app.route('/health')
    @app.route('/health/')
    @app.route('/health/ping')
    def health_ping():
        return jsonify({
            'status': 'healthy',
            'service': 'sankhya-woocommerce-sync',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @app.route('/health/ready')
    def health_ready():
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @app.route('/health/live')
    def health_live():
        return jsonify({
            'status': 'alive',
            'timestamp': datetime.utcnow().isoformat()
        })
    
    print("Rotas básicas registradas")
    
    # Carregar configurações
    try:
        print("Tentando importar configurações...")
        from app.config.settings import load_config
        config = load_config()
        app.config.update(config)
        print("Configurações carregadas")
    except Exception as e:
        print(f"Erro nas configurações: {e}")
    
    # REGISTRAR APENAS BLUEPRINTS QUE EXISTEM
    try:
        print("Registrando blueprints...")
        
        # API Blueprint
        try:
            from app.routes.api import api_bp
            app.register_blueprint(api_bp, url_prefix='/api/v1')
            print("API Blueprint registrado")
        except Exception as e:
            print(f"API Blueprint falhou: {e}")
        
        # Webhooks Blueprint
        try:
            from app.routes.webhooks import webhooks_bp
            app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
            print("Webhooks Blueprint registrado")
        except Exception as e:
            print(f"Webhooks Blueprint falhou: {e}")
        
        # NFE Blueprint - CORREÇÃO: Ativar o proxy para rotear para o Repo 1
        try:
            from app.routes.nfe_proxy import nfe_bp
            app.register_blueprint(nfe_bp, url_prefix='/nfe')
            print("NFe Proxy Blueprint registrado em /nfe")
        except Exception as e:
            print(f"NFe Proxy Blueprint falhou: {e}")
            
    except Exception as e:
        print(f"Erro geral nos blueprints: {e}")
    
    # Log de request básico
    @app.before_request
    def log_request():
        if not request.path.startswith('/health'):
            logger.info(f"{request.method} {request.path}")
    
    # Handlers de erro
    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        logger.warning(f"Erro HTTP {e.code}: {e.name} em {request.path}")
        return jsonify({
            'error': e.name,
            'description': e.description,
            'status_code': e.code,
            'timestamp': datetime.utcnow().isoformat()
        }), e.code

    @app.errorhandler(Exception)
    def handle_internal_error(e):
        logger.error(f"Erro Crítico Interno (500): {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Erro interno do servidor',
            'description': 'Ocorreu um erro não tratado no servidor.',
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    
    print("Aplicação Flask criada com sucesso!")
    print(f"Blueprints registrados:")
    print(f"   - /api/v1 (API)")
    print(f"   - /webhooks (Webhooks)")
    print(f"   - /nfe (NFe) - ATIVADO VIA PROXY")
    
    return app

# Para debug local
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print(f"Iniciando na porta {port} (debug: {debug})")
    
    app = create_app()
    app.run(host='0.0.0.0', port=port, debug=debug)
