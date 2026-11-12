# app/routes/nfe_proxy.py
"""
Proxy para redirecionar requisições NFe para o projeto integracaosite
Adicione este arquivo em app/routes/ do sankhya-woocommerce-sync
"""

import logging
import requests
from flask import Blueprint, request, Response, redirect
from app.config.settings import load_config

logger = logging.getLogger(__name__)

nfe_bp = Blueprint('nfe', __name__)

# URL do projeto integracaosite - AJUSTE CONFORME SEU DEPLOYMENT
INTEGRACAOSITE_URL = "https://app-producao.example.com"  # AJUSTE AQUI!

@nfe_bp.route('/view/<int:order_id>', methods=['GET'])
def proxy_view_nfe(order_id):
    """
    Redireciona para integracaosite para visualização da NFe
    """
    logger.info(f"Redirecionando visualização NFe #{order_id} para integracaosite")
    
    # Opção 1: Redirecionamento simples (navegador muda URL)
    target_url = f"{INTEGRACAOSITE_URL}/nfe/view/{order_id}"
    return redirect(target_url, code=302)
    
    # Opção 2: Proxy transparente (mantém URL original) - descomente se preferir
    """
    try:
        target_url = f"{INTEGRACAOSITE_URL}/nfe/view/{order_id}"
        
        # Fazer requisição para integracaosite
        response = requests.get(
            target_url,
            headers={k: v for k, v in request.headers if k != 'Host'},
            params=request.args,
            timeout=30
        )
        
        # Retornar resposta do integracaosite
        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
        
    except Exception as e:
        logger.error(f"Erro no proxy para integracaosite: {e}")
        return {"error": "Erro ao acessar sistema de NFe"}, 503
    """

@nfe_bp.route('/check/<int:order_id>', methods=['GET'])
def proxy_check_nfe(order_id):
    """
    Proxy para verificar NFe no integracaosite
    """
    logger.info(f"Proxy check NFe #{order_id}")
    
    try:
        target_url = f"{INTEGRACAOSITE_URL}/nfe/check/{order_id}"
        
        response = requests.get(
            target_url,
            params=request.args,
            timeout=10
        )
        
        return Response(
            response.content,
            status=response.status_code,
            content_type='application/json'
        )
        
    except Exception as e:
        logger.error(f"Erro no proxy: {e}")
        return {"error": str(e)}, 503

# Se quiser fazer proxy para TODAS as rotas /nfe/*
@nfe_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_all(path):
    """
    Proxy genérico para todas as rotas NFe
    """
    target_url = f"{INTEGRACAOSITE_URL}/nfe/{path}"
    
    logger.info(f"Proxy {request.method} /nfe/{path} → {target_url}")
    
    try:
        # Fazer requisição para integracaosite
        response = requests.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers if k != 'Host'},
            params=request.args,
            data=request.get_data(),
            timeout=30
        )
        
        # Retornar resposta
        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
        
    except Exception as e:
        logger.error(f"Erro no proxy: {e}")
        return {"error": "Erro ao acessar sistema de NFe"}, 503
