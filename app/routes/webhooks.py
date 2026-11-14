# app/routes/webhooks.py
"""
Rotas para receber webhooks do Sankhya ERP - VERSÃO COMPLETA
"""

import hmac
import logging
from flask import Blueprint, request, jsonify
from datetime import datetime

from app.services.sync.engine import SyncEngine
from app.utils.decorators import require_json, validate_webhook_token
from app.config.settings import load_config

# FIX: Importações necessárias para webhook NF-e
# MUDANÇA: Corrigir caminho de importação de SankhyaClient
from app.services.sankhya.auth import SankhyaAuth
# from app.services.sankhya.client import SankhyaClient  # <-- LINHA REMOVIDA
from app.services.sankhya import SankhyaClient          # <-- LINHA ADICIONADA (ou usar .base)
from app.services.woocommerce.client import WooCommerceClient
import os

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/sankhya/estoque-update', methods=['POST'])
@require_json
@validate_webhook_token
def webhook_estoque_update():
    """
    Recebe notificação do Sankhya sobre atualização de estoque (ORIGINAL)
    """
    try:
        data = request.get_json()
        
        logger.info(f"Webhook recebido do Sankhya: NUNOTA {data.get('nunota')}")
        logger.debug(f"Payload: {data}")
        
        # Validações básicas
        nunota = data.get('nunota')
        produtos = data.get('produtos', [])
        
        if not nunota:
            return jsonify({'error': 'NUNOTA obrigatório'}), 400
        
        if not produtos or not isinstance(produtos, list):
            return jsonify({'error': 'Lista de produtos obrigatória'}), 400
        
        logger.info(f"Processando {len(produtos)} produtos do pedido {nunota}")
        
        # Processar sincronização
        sync_engine = SyncEngine()
        resultados = []
        
        for produto in produtos:
            # FIX: Adicionar verificação de tipo para evitar AttributeError
            if not isinstance(produto, dict):
                logger.warning(f"Item inválido no payload de estoque (esperava dict, recebeu {type(produto).__name__}): {produto}")
                continue

            codprod = produto.get('codprod')
            
            if not codprod:
                logger.warning(f"Produto sem CODPROD ignorado: {produto}")
                continue
            
            try:
                resultado = sync_engine.sincronizar_produto_individual(codprod)
                
                resultados.append({
                    'codprod': codprod,
                    'sucesso': resultado['sucesso'],
                    'detalhes': resultado
                })
                
                if resultado['sucesso']:
                    logger.info(f"Produto {codprod}: {resultado.get('mensagem', 'Sincronizado')}")
                else:
                    logger.error(f"Produto {codprod}: {resultado.get('erro', 'Erro desconhecido')}")
                
            except Exception as e:
                logger.error(f"Erro no produto {codprod}: {e}")
                resultados.append({
                    'codprod': codprod,
                    'sucesso': False,
                    'erro': str(e)
                })
        
        # Estatísticas
        sucessos = sum(1 for r in resultados if r['sucesso'])
        erros = len(resultados) - sucessos
        
        resposta = {
            'status': 'processado',
            'nunota': nunota,
            'timestamp': datetime.utcnow().isoformat(),
            'produtos_processados': len(resultados),
            'sucessos': sucessos,
            'erros': erros,
            'detalhes': resultados
        }
        
        logger.info(f"Webhook processado: {sucessos}/{len(resultados)} sucessos")
        
        return jsonify(resposta), 200
        
    except Exception as e:
        logger.error(f"Erro no processamento do webhook: {e}", exc_info=True)
        return jsonify({
            'error': 'Erro interno no processamento',
            'timestamp': datetime.utcnow().isoformat(),
            'detalhes': str(e)
        }), 500

@webhooks_bp.route('/sankhya/venda-realizada', methods=['POST'])
@require_json
@validate_webhook_token
def webhook_venda_realizada():
    """
    Recebe notificação INSTANTÂNEA do Sankhya sobre venda confirmada (HTTPS)
    """
    try:
        data = request.get_json()
        
        logger.info(f"VENDA REALIZADA: NUNOTA {data.get('nunota')} - Produto {data.get('produto', {}).get('codprod')}")
        
        # Validação básica
        if not data.get('produto') or not data.get('produto', {}).get('codprod'):
            return jsonify({'error': 'Dados do produto obrigatórios'}), 400
        
        produto = data['produto']
        codprod = produto['codprod']
        
        # Sincronizar IMEDIATAMENTE com WooCommerce
        sync_engine = SyncEngine()
        resultado = sync_engine.sincronizar_produto_individual(codprod)
        
        if resultado['sucesso']:
            mensagem = f"Produto {codprod}: {resultado.get('mensagem', 'sincronizado')}"
            logger.info(f"TEMPO REAL: {mensagem}")
            
            return jsonify({
                'status': 'sucesso',
                'nunota': data.get('nunota'),
                'codprod': codprod,
                'acao': resultado.get('acao'),
                'estoque_anterior': resultado.get('estoque_anterior'),
                'estoque_novo': resultado.get('estoque_novo'),
                'mensagem': mensagem,
                'via': 'https',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            erro = resultado.get('erro', 'Erro desconhecido')
            logger.error(f"ERRO TEMPO REAL - Produto {codprod}: {erro}")
            
            return jsonify({
                'status': 'erro',
                'nunota': data.get('nunota'),
                'codprod': codprod,
                'erro': erro,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
    except Exception as e:
        logger.error(f"ERRO CRÍTICO no webhook venda realizada: {e}", exc_info=True)
        return jsonify({
            'status': 'erro_critico',
            'erro': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# === WEBHOOK HTTP PARA ORACLE =====
@webhooks_bp.route('/sankhya/venda-realizada-http', methods=['POST'])
@require_json
def webhook_venda_realizada_http():
    """
    Versão HTTP do webhook para contornar SSL do Oracle
    MESMO processamento do HTTPS, mas aceita HTTP sem decorator SSL
    """
    try:
        logger.info(f"HTTP WEBHOOK: Recebida de {request.remote_addr}")
        logger.info(f"Content-Type: {request.content_type}")
        
        # Verificar token manualmente (sem decorator que pode ter problema com HTTP)
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            logger.warning("Token ausente na requisição HTTP")
            return jsonify({'error': 'Token de autenticação requerido'}), 401
        
        token = auth_header.replace('Bearer ', '')
        config = load_config()
        expected_token = config.get('WEBHOOK_SECRET')
        
        if not expected_token or not hmac.compare_digest(str(token), str(expected_token)):
            logger.warning("Token inválido na requisição HTTP")
            return jsonify({'error': 'Token inválido'}), 401
        
        # Processar JSON
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON inválido'}), 400
        
        logger.info(f"HTTP VENDA REALIZADA: NUNOTA {data.get('nunota')} - Produto {data.get('produto', {}).get('codprod')}")
        
        # Validação básica
        if not data.get('produto') or not data.get('produto', {}).get('codprod'):
            return jsonify({'error': 'Dados do produto obrigatórios'}), 400
        
        produto = data['produto']
        codprod = produto['codprod']
        
        # Sincronizar com WooCommerce (MESMO código do HTTPS)
        sync_engine = SyncEngine()
        resultado = sync_engine.sincronizar_produto_individual(codprod)
        
        if resultado['sucesso']:
            mensagem = f"Produto {codprod}: {resultado.get('mensagem', 'sincronizado')}"
            logger.info(f"HTTP SYNC SUCESSO: {mensagem}")
            
            return jsonify({
                'status': 'sucesso',
                'nunota': data.get('nunota'),
                'codprod': codprod,
                'acao': resultado.get('acao'),
                'estoque_anterior': resultado.get('estoque_anterior'),
                'estoque_novo': resultado.get('estoque_novo'),
                'mensagem': mensagem,
                'via': 'http_oracle_proxy',
                'timestamp': datetime.utcnow().isoformat()
            }), 200
        else:
            erro = resultado.get('erro', 'Erro desconhecido')
            logger.error(f"HTTP SYNC ERRO - Produto {codprod}: {erro}")
            
            return jsonify({
                'status': 'erro',
                'nunota': data.get('nunota'),
                'codprod': codprod,
                'erro': erro,
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
    except Exception as e:
        logger.error(f"ERRO CRÍTICO HTTP webhook: {e}", exc_info=True)
        return jsonify({
            'status': 'erro_critico',
            'erro': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@webhooks_bp.route('/sankhya/test', methods=['POST'])
@require_json
def webhook_test():
    """Endpoint para testes de conectividade"""
    try:
        data = request.get_json() or {}
        
        logger.info(f"Webhook de teste recebido")
        logger.debug(f"Payload: {data}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Webhook de teste recebido com sucesso',
            'timestamp': datetime.utcnow().isoformat(),
            'payload_recebido': data
        }), 200
        
    except Exception as e:
        logger.error(f"Erro no webhook de teste: {e}")
        return jsonify({
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@webhooks_bp.route('/sankhya/test-connection', methods=['POST', 'GET'])
def test_sankhya_connection():
    """Endpoint para Sankhya testar conectividade"""
    return jsonify({
        'status': 'online',
        'service': 'Railway Intermediador',
        'message': 'Conexão com Railway funcionando',
        'method': request.method,
        'timestamp': datetime.utcnow().isoformat()
    }), 200

# ===== ENDPOINT DE DEBUG HTTP =====
@webhooks_bp.route('/test-http', methods=['GET', 'POST'])
def test_http():
    """Endpoint para testar conectividade HTTP do Oracle"""
    return jsonify({
        'status': 'HTTP funcionando no webhooks',
        'method': request.method,
        'timestamp': datetime.utcnow().isoformat(),
        'remote_addr': request.remote_addr,
        'content_type': request.content_type
    })

@webhooks_bp.route('/sankhya/debug', methods=['POST', 'GET'])
def webhook_debug():
    """Endpoint simples para debug Oracle"""
    try:
        logger.info(f"DEBUG: {request.method} de {request.remote_addr}")
        logger.info(f"User-Agent: {request.headers.get('User-Agent', 'N/A')}")
        
        if request.method == 'POST':
            try:
                json_data = request.get_json(force=True)
                logger.info(f"JSON OK: Produto {json_data.get('produto', {}).get('codprod', 'N/A')}")
            except Exception as e:
                logger.info(f"JSON ERRO: {str(e)}")
        
        return jsonify({
            'status': 'debug_ok',
            'method': request.method,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"DEBUG ERROR: {e}")
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/sankhya/nota-fiscal-aprovada', methods=['POST'])
@require_json
@validate_webhook_token
def webhook_nota_fiscal_aprovada():
    """
    🔔 WEBHOOK - Nota Fiscal Aprovada (Manual)
    Simula a notificação que o proxy enviaria quando uma NF é aprovada.

    Adicione esta rota ao seu arquivo app/routes/webhooks.py
    """
    # FIX: Remove request.get_json() do bloco try/except principal para permitir que BadRequests
    # (erros de JSON malformado) sejam capturados pelo handler global (handle_http_error em main.py)
    # e retornem 400, em vez de serem mascarados como 500.
    data = request.get_json() 

    try:
        
        # Validação
        nunota = data.get('nunota')
        if not nunota:
            logger.error("NUNOTA não fornecido")
            return jsonify({
                'status': 'erro',
                'mensagem': 'NUNOTA obrigatório',
                'timestamp': datetime.utcnow().isoformat()
            }), 400
        
        logger.info(f"WEBHOOK NF APROVADA: NUNOTA {nunota}")
        
        # ETAPA 1: Buscar dados da NF no Sankhya
        # FIX: As importações já estão corrigidas no topo do arquivo.
        # from app.services.sankhya.auth import SankhyaAuth
        # from app.services.sankhya.client import SankhyaClient
        # from app.services.woocommerce.client import WooCommerceClient
        # import os
        
        with SankhyaAuth() as token:
            # FIX: SankhyaClient agora é importado corretamente do topo do módulo
            sankhya_client = SankhyaClient(token)
            
            logger.info(f"Buscando dados da NF {nunota} no Sankhya...")
            
            # Buscar todos os dados necessários
            criteria = {
                "expression": {
                    "$": "this.NUNOTA = ?"
                },
                "parameter": [
                    {
                        "type": "I",
                        "$": str(nunota)
                    }
                ]
            }
            
            resultado = sankhya_client.load_records(
                entity="CabecalhoNota",
                fields="NUNOTA,NUMNOTA,CHAVENFE,STATUSNFE,DTFATUR,VLRNOTA,SERIENOTA,AD_IDWOOCOMMERCE",
                criteria=criteria,
                limit=1
            )
            
            entities = resultado.get("responseBody", {}).get("entities", {})
            total = int(entities.get("total", "0"))
            
            if total == 0:
                logger.error(f"NUNOTA {nunota} não encontrada no Sankhya")
                return jsonify({
                    'status': 'erro',
                    'mensagem': f'NUNOTA {nunota} não encontrada',
                    'timestamp': datetime.utcnow().isoformat()
                }), 404
            
            # Extrair dados
            entity = entities.get("entity")
            if isinstance(entity, list):
                entity = entity[0]
            
            numnota = entity.get('f1', {}).get('$', '')
            chavenfe = entity.get('f2', {}).get('$', '')
            statusnfe = entity.get('f3', {}).get('$', '')
            dtfatur = entity.get('f4', {}).get('$', '')
            vlrnota = entity.get('f5', {}).get('$', '0')
            serienota = entity.get('f6', {}).get('$', '')
            id_woocommerce = entity.get('f7', {}).get('$', '')
            
            # Validar status da NF
            status_map = {
                'A': 'Aprovada',
                'D': 'Denegada',
                'E': 'Aguardando Autorização',
                'P': 'Pendente',
                'R': 'Aguardando Correção'
            }
            status_legivel = status_map.get(statusnfe, 'Desconhecido')
            
            logger.info(f"NF encontrada: Nº {numnota}, Status: {status_legivel}")
            
            # FALLBACK: AD_IDWOOCOMMERCE vazio
            # O campo foi recriado na base, mas notas anteriores não tinham o vínculo.
            # Nesse caso, buscamos o pedido no WooCommerce que já tem _sankhya_nunota
            # salvo (gravado pelo integracaosite ao criar o pedido).
            if not id_woocommerce:
                logger.warning(
                    f"⚠️ AD_IDWOOCOMMERCE vazio para NUNOTA {nunota}. "
                    f"Buscando pedido WooCommerce via _sankhya_nunota..."
                )
                woo_client_lookup = WooCommerceClient()
                pedido_woo = woo_client_lookup.find_order_by_nunota(nunota)
                
                if not pedido_woo:
                    logger.error(
                        f"❌ Nenhum pedido WooCommerce encontrado com "
                        f"_sankhya_nunota={nunota}"
                    )
                    return jsonify({
                        'status': 'erro',
                        'mensagem': (
                            f'NUNOTA {nunota} não possui AD_IDWOOCOMMERCE no Sankhya '
                            f'e nenhum pedido WooCommerce tem _sankhya_nunota={nunota}.'
                        ),
                        'nunota': nunota,
                        'timestamp': datetime.utcnow().isoformat()
                    }), 404
                
                id_woocommerce = str(pedido_woo['id'])
                logger.info(
                    f"Pedido WooCommerce #{id_woocommerce} encontrado via _sankhya_nunota. "
                    f"Reparando AD_IDWOOCOMMERCE no Sankhya..."
                )
                
                # Reparar o campo no Sankhya para evitar o problema em futuros disparos
                try:
                    sankhya_client.save_record(
                        entity="CabecalhoNota",
                        data={
                            "NUNOTA": {"$": str(nunota)},
                            "AD_IDWOOCOMMERCE": {"$": id_woocommerce}
                        }
                    )
                    logger.info(f"AD_IDWOOCOMMERCE={id_woocommerce} gravado no Sankhya para NUNOTA {nunota}")
                except Exception as e_repair:
                    logger.warning(f"Não foi possível reparar AD_IDWOOCOMMERCE no Sankhya: {e_repair}")
            
            id_woocommerce = int(id_woocommerce)
            
            # ETAPA 2: Atualizar WooCommerce
            logger.info(f"Atualizando pedido WooCommerce {id_woocommerce}...")
            
            # FIX: WooCommerceClient agora é importado corretamente do topo do módulo
            woo_client = WooCommerceClient()
            
            # Preparar dados
            api_base_url = os.getenv('API_BASE_URL', 'http://localhost:5000')
            link_danfe = f"{api_base_url}/nfe/view/{id_woocommerce}"
            
            update_data = {
                "meta_data": [
                    {"key": "_sankhya_nunota", "value": str(nunota)},
                    {"key": "_nf_numero", "value": str(numnota)},
                    {"key": "_nf_serie", "value": str(serienota)},
                    {"key": "_nf_chave", "value": str(chavenfe)},
                    {"key": "_nf_status", "value": status_legivel},
                    {"key": "_nf_data_emissao", "value": str(dtfatur)},
                    {"key": "_nf_valor", "value": str(vlrnota)},
                    {"key": "_nf_link_danfe", "value": link_danfe} # LINK CORRIGIDO
                ]
            }
            
            # Atualizar pedido
            resultado_woo = woo_client.update_order(id_woocommerce, update_data)
            
            if not resultado_woo or resultado_woo.get('error'):
                logger.error(f"Erro ao atualizar WooCommerce: {resultado_woo}")
                return jsonify({
                    'status': 'erro',
                    'mensagem': 'Erro ao atualizar pedido no WooCommerce',
                    'detalhes': str(resultado_woo),
                    'timestamp': datetime.utcnow().isoformat()
                }), 500
            
            logger.info(f"Pedido WooCommerce {id_woocommerce} atualizado")
            
            
            # ETAPA 4: Retornar sucesso
            return jsonify({
                'status': 'sucesso',
                'mensagem': f'Nota Fiscal {numnota} processada com sucesso',
                'timestamp': datetime.utcnow().isoformat(),
                'dados': {
                    'nunota': nunota,
                    'nf_numero': numnota,
                    'nf_chave': chavenfe,
                    'nf_status': status_legivel,
                    'id_woocommerce': id_woocommerce,
                    'link_danfe': link_danfe
                }
            }), 200
            
    except FileNotFoundError as e:
        logger.warning(f"DANFE não encontrado: {e}")
        return jsonify({'status': 'erro', 'error': str(e)}), 404
    except Exception as e:
        # Este bloco agora só captura erros internos (rede, Sankhya, lógica 500) e NÃO mais o BadRequest (400)
        logger.error(f"Erro Crítico Interno (500) ao processar webhook NF: {e}", exc_info=True)
        return jsonify({
            'status': 'erro',
            'mensagem': 'Erro interno ao processar notificação',
            'detalhes': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

