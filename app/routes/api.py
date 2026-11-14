# app/routes/api.py
"""
APIs principais do intermediador
"""

import logging
import hashlib
import hmac
from flask import Blueprint, request, jsonify, Response
from datetime import datetime

from app.services.sync.engine import SyncEngine
from app.services.sankhya.auth import SankhyaAuth
from app.services.sankhya.estoque import EstoqueService
from app.services.sankhya.service import SankhyaService
from app.utils.decorators import require_auth, require_json
from app.config.settings import load_config

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Helper functions (adicionar no topo do arquivo)
def gerar_hash_danfe(order_id: int, secret: str) -> str:
    """Gera hash HMAC-SHA256 para validação de acesso ao DANFE"""
    mensagem = f"danfe_{order_id}"
    return hmac.new(
        secret.encode('utf-8'),
        mensagem.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def validar_hash_danfe(order_id: int, hash_recebido: str, secret: str) -> bool:
    """Valida o hash recebido contra o esperado"""
    hash_esperado = gerar_hash_danfe(order_id, secret)
    return hmac.compare_digest(hash_esperado, hash_recebido)

# Endpoint público com validação por hash
@api_bp.route('/public/nfe/danfe/woo/<int:id_woocommerce>', methods=['GET'])
def obter_danfe_publico_seguro(id_woocommerce):
    """
    Endpoint PÚBLICO para download de DANFE com validação por hash.
    URL: /api/v1/public/nfe/danfe/woo/<order_id>?hash=<hash_gerado>
    """
    try:
        # 1. Obter e validar hash
        hash_recebido = request.args.get('hash', '')
        
        if not hash_recebido:
            logger.warning(f"Tentativa de acesso sem hash para pedido {id_woocommerce}")
            return jsonify({'status': 'erro', 'error': 'Hash de validação obrigatório'}), 401
        
        # 2. Validar hash
        config = load_config()
        secret = config.get('WEBHOOK_SECRET')
        if not secret:
            logger.error('WEBHOOK_SECRET não configurado: endpoint público de DANFE desativado')
            return jsonify({'status': 'erro', 'error': 'Serviço indisponível'}), 503
        
        if not validar_hash_danfe(id_woocommerce, hash_recebido, secret):
            logger.warning(f"Hash inválido para pedido {id_woocommerce}")
            return jsonify({'status': 'erro', 'error': 'Hash de validação inválido'}), 401
        
        logger.info(f"Requisição VÁLIDA de DANFE para ID WooCommerce={id_woocommerce}")
        
        # 3. Buscar e gerar DANFE
        with SankhyaService.with_auth() as service:
            nunota = service.obter_nunota_por_id_woocommerce(id_woocommerce)
            
            if not nunota:
                return jsonify({'status': 'erro', 'error': 'Nota fiscal não encontrada'}), 404
            
            pdf_bytes = service.obter_danfe_pdf(nunota)
        
        # 4. Retornar PDF
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename=DANFE_Pedido_{id_woocommerce}_NF_{nunota}.pdf',
                'Cache-Control': 'public, max-age=3600'
            }
        )
        
    except Exception as e:
        logger.error(f"Erro ao gerar DANFE: {e}", exc_info=True)
        return jsonify({'status': 'erro', 'error': 'Erro ao gerar nota fiscal'}), 500

@api_bp.route('/nfe/xml/woo/<int:id_woocommerce>', methods=['GET'])
@require_auth
def obter_xml_por_id_woocommerce(id_woocommerce):
    """
    Download direto do XML da NFe (alternativa ao PDF)
    """
    try:
        logger.info(f"[XML] Requisição para pedido WooCommerce #{id_woocommerce}")
        
        with SankhyaService.with_auth() as service:
            # Buscar NUNOTA
            nunota = service.obter_nunota_por_id_woocommerce(id_woocommerce)
            
            if not nunota:
                return jsonify({'error': 'NFe não encontrada'}), 404
            
            # Buscar XML
            xml_content = service._obter_xml_nfe_por_nunota(nunota)
            
            logger.info(f"[XML] XML obtido - {len(xml_content)} chars")
            
            return Response(
                xml_content,
                mimetype='application/xml',
                headers={
                    'Content-Disposition': f'attachment; filename=NFe_Pedido_{id_woocommerce}_NUNOTA_{nunota}.xml'
                }
            )
    except Exception as e:
        logger.error(f"[XML] Erro: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
        
@api_bp.route('/sync/produto/<int:codprod>', methods=['POST'])
@require_auth
def sync_produto_individual(codprod):
    """
    Sincroniza estoque de um produto específico
    """
    try:
        data = request.get_json() or {}
        product_id_wc = data.get('product_id_wc')
        sku_wc = data.get('sku_wc')
        
        logger.info(f"Solicitação de sincronização produto {codprod}")
        
        sync_engine = SyncEngine()
        resultado = sync_engine.sincronizar_produto_individual(
            codprod, 
            product_id_wc=product_id_wc,
            sku_wc=sku_wc
        )
        
        status_code = 200 if resultado['sucesso'] else 400
        
        return jsonify({
            'status': 'sucesso' if resultado['sucesso'] else 'erro',
            'timestamp': datetime.utcnow().isoformat(),
            'resultado': resultado
        }), status_code
        
    except Exception as e:
        logger.error(f"Erro na API sync produto {codprod}: {e}")
        return jsonify({
            'status': 'erro',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/sync/lote', methods=['POST'])
@require_auth
@require_json
def sync_lote():
    """
    Sincroniza múltiplos produtos
    
    Body:
    {
        "produtos": [
            {"codprod_sankhya": 1001, "sku_wc": "1001"},
            {"codprod_sankhya": 1002, "product_id_wc": 123}
        ]
    }
    """
    try:
        data = request.get_json()
        produtos = data.get('produtos', [])
        
        if not produtos:
            return jsonify({'error': 'Lista de produtos obrigatória'}), 400
        
        logger.info(f"Solicitação de sincronização em lote: {len(produtos)} produtos")
        
        sync_engine = SyncEngine()
        resultado = sync_engine.sincronizar_multiplos_produtos(produtos)
        
        status_code = 200 if resultado['sucesso'] else 400
        
        return jsonify({
            'status': 'sucesso' if resultado['sucesso'] else 'erro',
            'timestamp': datetime.utcnow().isoformat(),
            'resultado': resultado
        }), status_code
        
    except Exception as e:
        logger.error(f"Erro na API sync lote: {e}")
        return jsonify({
            'status': 'erro',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/estoque/<int:codprod>', methods=['GET'])
@require_auth
def consultar_estoque(codprod):
    """
    Consulta estoque atual de um produto no Sankhya
    """
    try:
        somente_venda = request.args.get('somente_venda', 'true').lower() == 'true'
        
        logger.info(f"Consulta de estoque produto {codprod}")
        
        with SankhyaAuth() as token:
            estoque_service = EstoqueService(token)
            
            if request.args.get('detalhado', 'false').lower() == 'true':
                # Retorna detalhes por local
                estoques = estoque_service.consultar_estoque_produto(codprod, somente_venda)
                estoque_total = sum(max(0, e['ESTOQUE'] - e['RESERVADO']) for e in estoques)
                
                resultado = {
                    'codprod': codprod,
                    'estoque_total': estoque_total,
                    'locais': estoques
                }
            else:
                # Retorna apenas total
                estoque_total = estoque_service.obter_estoque_total_produto(codprod)
                
                resultado = {
                    'codprod': codprod,
                    'estoque_total': estoque_total
                }
        
        return jsonify({
            'status': 'sucesso',
            'timestamp': datetime.utcnow().isoformat(),
            'resultado': resultado
        }), 200
        
    except Exception as e:
        logger.error(f"Erro na consulta de estoque {codprod}: {e}")
        return jsonify({
            'status': 'erro',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/estoque/multiplos', methods=['POST'])
@require_auth
@require_json
def consultar_estoque_multiplos():
    """
    Consulta estoque de múltiplos produtos
    
    Body:
    {
        "codprods": [1001, 1002, 1003]
    }
    """
    try:
        data = request.get_json()
        codprods = data.get('codprods', [])
        
        if not codprods:
            return jsonify({'error': 'Lista de códigos obrigatória'}), 400
        
        logger.info(f"Consulta de estoque múltiplos produtos: {len(codprods)}")
        
        with SankhyaAuth() as token:
            estoque_service = EstoqueService(token)
            estoques = estoque_service.consultar_multiplos_produtos(codprods)
        
        return jsonify({
            'status': 'sucesso',
            'timestamp': datetime.utcnow().isoformat(),
            'produtos_consultados': len(codprods),
            'resultado': estoques
        }), 200
        
    except Exception as e:
        logger.error(f"Erro na consulta múltipla de estoque: {e}")
        return jsonify({
            'status': 'erro',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@api_bp.route('/nfe/danfe/woo/<int:id_woocommerce>', methods=['GET'])
@require_auth
def obter_danfe_por_id_woocommerce(id_woocommerce):
    """
    Gera e retorna o DANFE de uma NF-e, buscando pelo ID do Pedido do WooCommerce.
    Endpoint otimizado para o fluxo de integração site (Repo 1).
    """
    try:
        logger.info(f"Requisição de DANFE para ID WooCommerce={id_woocommerce}")
        
        with SankhyaService.with_auth() as service:
            # 1. Busca NUNOTA pelo ID do WooCommerce
            nunota = service.obter_nunota_por_id_woocommerce(id_woocommerce)
            
            if not nunota:
                logger.warning(f"Nenhuma NUNOTA encontrada para ID WooCommerce {id_woocommerce}")
                return jsonify({'status': 'erro', 'error': 'NUNOTA não encontrada para este ID WooCommerce (não faturado ou ID incorreto)'}), 404
            
            logger.info(f"NUNOTA {nunota} encontrado. Gerando PDF...")
            
            # 2. Obtém o PDF usando o NUNOTA
            pdf_bytes = service.obter_danfe_pdf(nunota)
        
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=DANFE_WOO_{id_woocommerce}_N{nunota}.pdf'
            }
        )
    except FileNotFoundError as e:
        logger.warning(f"DANFE não encontrado: {e}")
        return jsonify({'status': 'erro', 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Erro crítico ao gerar DANFE para ID WooCommerce {id_woocommerce}: {e}", exc_info=True)
        return jsonify({'status': 'erro', 'error': 'Erro interno ao gerar DANFE'}), 500

@api_bp.route('/nfe/<int:nunota>/danfe', methods=['GET'])
@require_auth
def obter_danfe(nunota):
    """
    Gera e retorna o DANFE de uma NF-e em formato PDF.
    """
    try:
        logger.info(f"Requisição de DANFE para NUNOTA={nunota}")
        with SankhyaService.with_auth() as service:
            # Opcional: passar caminho do logo a partir de config ou request
            pdf_bytes = service.obter_danfe_pdf(nunota)
        
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=DANFE_{nunota}.pdf'
            }
        )
    except (ValueError, FileNotFoundError, PermissionError) as e:
        logger.warning(f"Erro ao gerar DANFE para {nunota}: {e}")
        return jsonify({'status': 'erro', 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Erro crítico ao gerar DANFE para {nunota}: {e}", exc_info=True)
        return jsonify({'status': 'erro', 'error': 'Erro interno ao gerar DANFE'}), 500

@api_bp.route('/nf/reprocessar', methods=['POST'])
@require_auth
@require_json
def reprocessar_notas_retroativo():
    """
    Reprocessa NFs do período em que AD_IDWOOCOMMERCE estava ausente.

    Recebe apenas os NUNOTAs. O id_woocommerce é descoberto automaticamente
    buscando no WooCommerce o pedido que tem _sankhya_nunota=<nunota>
    (gravado pelo integracaosite ao criar o pedido).

    Também repara AD_IDWOOCOMMERCE no Sankhya para notas futuras.

    Body:
    {
        "nunotas": [14173, 14158]
    }
    """
    import os as _os
    from app.services.sankhya.auth import SankhyaAuth
    from app.services.sankhya import SankhyaClient
    from app.services.woocommerce.client import WooCommerceClient

    data = request.get_json()
    nunotas = data.get('nunotas', [])

    if not nunotas:
        return jsonify({'error': 'Lista "nunotas" obrigatória. Ex: {"nunotas": [14173, 14158]}'}), 400

    resultados = []
    woo_client = WooCommerceClient()

    for nunota in nunotas:
        try:
            nunota = int(nunota)
            logger.info(f"Reprocessando NUNOTA {nunota}...")

            # ── PASSO 1: Buscar dados da NF no Sankhya (inclui AD_IDWOOCOMMERCE) ──
            with SankhyaAuth() as token:
                sankhya_client = SankhyaClient(token)

                criteria = {
                    "expression": {"$": "this.NUNOTA = ?"},
                    "parameter": [{"type": "I", "$": str(nunota)}]
                }

                resultado_sk = sankhya_client.load_records(
                    entity="CabecalhoNota",
                    fields="NUNOTA,NUMNOTA,CHAVENFE,STATUSNFE,DTFATUR,VLRNOTA,SERIENOTA,AD_IDWOOCOMMERCE",
                    criteria=criteria,
                    limit=1
                )

                entities = resultado_sk.get("responseBody", {}).get("entities", {})
                if int(entities.get("total", "0")) == 0:
                    resultados.append({
                        'nunota': nunota,
                        'sucesso': False,
                        'erro': f'NUNOTA {nunota} não encontrada no Sankhya'
                    })
                    continue

                entity = entities.get("entity")
                if isinstance(entity, list):
                    entity = entity[0]

                numnota     = entity.get('f1', {}).get('$', '')
                chavenfe    = entity.get('f2', {}).get('$', '')
                statusnfe   = entity.get('f3', {}).get('$', '')
                dtfatur     = entity.get('f4', {}).get('$', '')
                vlrnota     = entity.get('f5', {}).get('$', '0')
                serienota   = entity.get('f6', {}).get('$', '')
                ad_id_atual = entity.get('f7', {}).get('$', '')

                status_map = {
                    'A': 'Aprovada', 'D': 'Denegada',
                    'E': 'Aguardando Autorização',
                    'P': 'Pendente', 'R': 'Aguardando Correção'
                }
                status_legivel = status_map.get(statusnfe, 'Desconhecido')

                # ── PASSO 2: Determinar id_woocommerce ──
                # Prioridade 1: AD_IDWOOCOMMERCE do Sankhya (fonte da verdade)
                # Prioridade 2: Fallback via _sankhya_nunota no WooCommerce
                id_woocommerce = None
                fonte_id = None

                if ad_id_atual:
                    id_woocommerce = int(ad_id_atual)
                    fonte_id = 'AD_IDWOOCOMMERCE (Sankhya)'
                    logger.info(
                        f"id_woocommerce={id_woocommerce} obtido do "
                        f"AD_IDWOOCOMMERCE do Sankhya para NUNOTA {nunota}"
                    )
                else:
                    logger.warning(
                        f"⚠️ AD_IDWOOCOMMERCE vazio para NUNOTA {nunota}. "
                        f"Buscando pedido WooCommerce via _sankhya_nunota..."
                    )
                    pedido_woo = woo_client.find_order_by_nunota(nunota)
                    if pedido_woo:
                        id_woocommerce = pedido_woo['id']
                        fonte_id = '_sankhya_nunota (WooCommerce — fallback)'
                        logger.info(
                            f"Pedido WooCommerce #{id_woocommerce} encontrado "
                            f"via _sankhya_nunota para NUNOTA {nunota}"
                        )
                        # Reparar AD_IDWOOCOMMERCE no Sankhya
                        try:
                            sankhya_client.save_record(
                                entity="CabecalhoNota",
                                data={
                                    "NUNOTA": {"$": str(nunota)},
                                    "AD_IDWOOCOMMERCE": {"$": str(id_woocommerce)}
                                }
                            )
                            logger.info(
                                f"AD_IDWOOCOMMERCE={id_woocommerce} "
                                f"gravado no Sankhya para NUNOTA {nunota}"
                            )
                        except Exception as e_repair:
                            logger.warning(
                                f"⚠️ Não foi possível reparar AD_IDWOOCOMMERCE "
                                f"no Sankhya para NUNOTA {nunota}: {e_repair}"
                            )

                if not id_woocommerce:
                    resultados.append({
                        'nunota': nunota,
                        'sucesso': False,
                        'erro': (
                            f'Não foi possível determinar o pedido WooCommerce para '
                            f'NUNOTA {nunota}. AD_IDWOOCOMMERCE vazio no Sankhya e '
                            f'nenhum pedido WooCommerce tem _sankhya_nunota={nunota}.'
                        )
                    })
                    continue

                # ── PASSO 3: Atualizar metadados da NF no WooCommerce ──
                api_base_url = _os.getenv('API_BASE_URL', 'http://localhost:5000')
                link_danfe = f"{api_base_url}/nfe/view/{id_woocommerce}"

                update_data = {
                    "meta_data": [
                        {"key": "_sankhya_nunota",  "value": str(nunota)},
                        {"key": "_nf_numero",        "value": str(numnota)},
                        {"key": "_nf_serie",         "value": str(serienota)},
                        {"key": "_nf_chave",         "value": str(chavenfe)},
                        {"key": "_nf_status",        "value": status_legivel},
                        {"key": "_nf_data_emissao",  "value": str(dtfatur)},
                        {"key": "_nf_valor",         "value": str(vlrnota)},
                        {"key": "_nf_link_danfe",    "value": link_danfe},
                    ]
                }

                resultado_woo = woo_client.update_order(id_woocommerce, update_data)
                if not resultado_woo or resultado_woo.get('error'):
                    resultados.append({
                        'nunota': nunota, 'id_woocommerce': id_woocommerce,
                        'sucesso': False,
                        'erro': f'Erro ao atualizar WooCommerce: {resultado_woo}'
                    })
                    continue


                logger.info(f"NUNOTA {nunota} → Pedido #{id_woocommerce} integrado ({fonte_id})")
                resultados.append({
                    'nunota': nunota,
                    'id_woocommerce': id_woocommerce,
                    'sucesso': True,
                    'nf_numero': numnota,
                    'nf_status': status_legivel,
                    'link_danfe': link_danfe,
                    'fonte_id_woocommerce': fonte_id,
                    'ad_idwoocommerce_reparado': not ad_id_atual
                })

        except Exception as e:
            logger.error(f"Erro ao reprocessar NUNOTA {nunota}: {e}", exc_info=True)
            resultados.append({
                'nunota': nunota,
                'sucesso': False,
                'erro': str(e)
            })

    sucessos = sum(1 for r in resultados if r['sucesso'])
    return jsonify({
        'status': 'concluido',
        'timestamp': datetime.utcnow().isoformat(),
        'total': len(resultados),
        'sucessos': sucessos,
        'erros': len(resultados) - sucessos,
        'resultados': resultados
    }), 200


@api_bp.route('/status', methods=['GET'])
def status():
    """Status do serviço"""
    try:
        # Testa conectividade com Sankhya
        sankhya_ok = False
        try:
            with SankhyaAuth() as token:
                sankhya_ok = True
        except:
            pass
        
        # Testa conectividade com WooCommerce
        wc_ok = False
        try:
            from app.services.woocommerce.client import WooCommerceClient
            wc_client = WooCommerceClient()
            # Tenta fazer uma consulta simples
            wc_client.get_products(per_page=1)
            wc_ok = True
        except:
            pass
        
        return jsonify({
            'status': 'running',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'sankhya': 'ok' if sankhya_ok else 'error',
                'woocommerce': 'ok' if wc_ok else 'error'
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500




