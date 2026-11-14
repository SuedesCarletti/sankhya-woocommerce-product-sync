# app/routes/nfe_proxy.py
"""
Proxy de NF-e: encaminha consultas de DANFE para o serviço integracaosite.

Segurança:
- exige o mesmo token da API (require_auth) em tudo que for proxy;
- só GET; nenhum header do cliente é repassado (nada de Authorization/Cookie do
  chamador chegando ao serviço interno);
- o token do serviço interno vem do ambiente, nunca da requisição.
"""

import logging
import os

import requests
from flask import Blueprint, Response

from app.utils.decorators import require_auth

logger = logging.getLogger(__name__)

nfe_bp = Blueprint('nfe', __name__)

INTEGRACAOSITE_URL = os.getenv("INTEGRACAOSITE_URL", "").rstrip("/")
INTEGRACAOSITE_TOKEN = os.getenv("INTEGRACAOSITE_TOKEN", "")


def _upstream_headers():
    """Headers enviados ao serviço interno: só o token dele."""
    return {"X-API-Token": INTEGRACAOSITE_TOKEN} if INTEGRACAOSITE_TOKEN else {}


def _configurado():
    return bool(INTEGRACAOSITE_URL)


@nfe_bp.route('/view/<int:order_id>', methods=['GET'])
@require_auth
def proxy_view_nfe(order_id):
    """Busca o DANFE no integracaosite e devolve o PDF (sem expor a URL interna)."""
    if not _configurado():
        return {"error": "Proxy de NF-e não configurado"}, 503
    try:
        resp = requests.get(
            f"{INTEGRACAOSITE_URL}/nfe/pdf/view/{order_id}",
            headers=_upstream_headers(),
            timeout=30,
        )
        return Response(
            resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('Content-Type', 'application/pdf'),
        )
    except requests.RequestException as e:
        logger.error(f"Erro no proxy de NF-e: {e}")
        return {"error": "Erro ao acessar sistema de NF-e"}, 503


@nfe_bp.route('/check/<int:order_id>', methods=['GET'])
@require_auth
def proxy_check_nfe(order_id):
    """Verifica se existe NF-e para o pedido."""
    if not _configurado():
        return {"error": "Proxy de NF-e não configurado"}, 503
    try:
        resp = requests.get(
            f"{INTEGRACAOSITE_URL}/nfe/check/{order_id}",
            headers=_upstream_headers(),
            timeout=10,
        )
        return Response(resp.content, status=resp.status_code, content_type='application/json')
    except requests.RequestException as e:
        logger.error(f"Erro no proxy de NF-e: {e}")
        return {"error": "Erro ao acessar sistema de NF-e"}, 503
