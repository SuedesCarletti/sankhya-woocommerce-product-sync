# app/services/sync/engine.py
"""
Motor principal de sincronização entre Sankhya e WooCommerce
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime

from app.services.sankhya.auth import SankhyaAuth
from app.services.sankhya.estoque import EstoqueService
from app.services.woocommerce.client import WooCommerceClient

logger = logging.getLogger(__name__)

class SyncEngine:
    """Motor de sincronização entre Sankhya e WooCommerce"""
    
    def __init__(self):
        self.wc_client = WooCommerceClient()
        self.sync_stats = {
            'iniciado_em': None,
            'concluido_em': None,
            'produtos_processados': 0,
            'sucessos': 0,
            'erros': 0,
            'detalhes': []
        }
    
    def sincronizar_produto_individual(self, codprod_sankhya: int, 
                                     product_id_wc: int = None, 
                                     sku_wc: str = None) -> Dict[str, Any]:
        """
        Sincroniza estoque de um produto específico
        """
        logger.info(f"Iniciando sincronização produto {codprod_sankhya}")
        
        try:
            # 1. Buscar estoque no Sankhya
            with SankhyaAuth() as token:
                estoque_service = EstoqueService(token)
                estoque_sankhya = estoque_service.obter_estoque_total_produto(codprod_sankhya)
            
            logger.info(f"Estoque Sankhya: {estoque_sankhya}")
            
            # 2. Encontrar produto no WooCommerce
            produto_wc = None
            
            if product_id_wc:
                produto_wc = self.wc_client.get_product(product_id_wc)
            elif sku_wc:
                produto_wc = self.wc_client.find_product_by_sku(sku_wc)
            else:
                # Tenta encontrar por SKU = CODPROD
                produto_wc = self.wc_client.find_product_by_sku(str(codprod_sankhya))
            
            if not produto_wc:
                raise ValueError(f"Produto não encontrado no WooCommerce")
            
            estoque_atual_wc = produto_wc.get('stock_quantity', 0) or 0
            
            logger.info(f"Estoque WooCommerce atual: {estoque_atual_wc}")
            
            # 3. Verificar se precisa atualizar
            if estoque_sankhya == estoque_atual_wc:
                logger.info(f"Estoques já sincronizados: {estoque_sankhya}")
                return {
                    'sucesso': True,
                    'acao': 'nenhuma',
                    'estoque_sankhya': estoque_sankhya,
                    'estoque_woocommerce': estoque_atual_wc,
                    'mensagem': 'Estoques já sincronizados'
                }
            
            # 4. Atualizar no WooCommerce
            resultado = self.wc_client.update_product_stock(
                produto_wc['id'], 
                estoque_sankhya
            )
            
            logger.info(f"Produto {codprod_sankhya} sincronizado: {estoque_atual_wc} → {estoque_sankhya}")
            
            return {
                'sucesso': True,
                'acao': 'atualizado',
                'product_id_wc': produto_wc['id'],
                'estoque_anterior': estoque_atual_wc,
                'estoque_novo': estoque_sankhya,
                'estoque_sankhya': estoque_sankhya,
                'mensagem': f'Estoque atualizado de {estoque_atual_wc} para {estoque_sankhya}'
            }
            
        except Exception as e:
            logger.error(f"Erro na sincronização do produto {codprod_sankhya}: {e}")
            return {
                'sucesso': False,
                'erro': str(e),
                'codprod_sankhya': codprod_sankhya
            }
    
    def sincronizar_multiplos_produtos(self, mapeamento: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Sincroniza múltiplos produtos
        
        Args:
            mapeamento: Lista de dicts com 'codprod_sankhya', 'product_id_wc' ou 'sku_wc'
        """
        self.sync_stats = {
            'iniciado_em': datetime.utcnow(),
            'concluido_em': None,
            'produtos_processados': 0,
            'sucessos': 0,
            'erros': 0,
            'detalhes': []
        }
        
        logger.info(f"Iniciando sincronização de {len(mapeamento)} produtos")
        
        try:
            # 1. Buscar todos os estoques no Sankhya de uma vez
            codprods = [item['codprod_sankhya'] for item in mapeamento]
            
            with SankhyaAuth() as token:
                estoque_service = EstoqueService(token)
                estoques_sankhya = estoque_service.consultar_multiplos_produtos(codprods)
            
            # 2. Processar cada produto
            updates_wc = []
            
            for item in mapeamento:
                try:
                    codprod = item['codprod_sankhya']
                    estoque_sankhya = estoques_sankhya.get(codprod, 0)
                    
                    # Encontrar produto WooCommerce
                    produto_wc = None
                    if 'product_id_wc' in item:
                        produto_wc = self.wc_client.get_product(item['product_id_wc'])
                    elif 'sku_wc' in item:
                        produto_wc = self.wc_client.find_product_by_sku(item['sku_wc'])
                    else:
                        produto_wc = self.wc_client.find_product_by_sku(str(codprod))
                    
                    if not produto_wc:
                        raise ValueError(f"Produto {codprod} não encontrado no WooCommerce")
                    
                    estoque_atual = produto_wc.get('stock_quantity', 0) or 0
                    
                    # Só atualiza se diferente
                    if estoque_sankhya != estoque_atual:
                        updates_wc.append({
                            'id': produto_wc['id'],
                            'stock_quantity': estoque_sankhya,
                            'manage_stock': True,
                            'stock_status': 'instock' if estoque_sankhya > 0 else 'outofstock'
                        })
                    
                    # Estatísticas
                    self.sync_stats['detalhes'].append({
                        'codprod_sankhya': codprod,
                        'product_id_wc': produto_wc['id'],
                        'estoque_anterior': estoque_atual,
                        'estoque_novo': estoque_sankhya,
                        'acao': 'atualizado' if estoque_sankhya != estoque_atual else 'mantido',
                        'sucesso': True
                    })
                    
                    self.sync_stats['sucessos'] += 1
                    
                except Exception as e:
                    logger.error(f"Erro no produto {codprod}: {e}")
                    
                    self.sync_stats['detalhes'].append({
                        'codprod_sankhya': codprod,
                        'erro': str(e),
                        'sucesso': False
                    })
                    
                    self.sync_stats['erros'] += 1
                
                self.sync_stats['produtos_processados'] += 1
            
            # 3. Atualizar WooCommerce em lote
            if updates_wc:
                logger.info(f"Enviando {len(updates_wc)} atualizações para WooCommerce")
                resultado_batch = self.wc_client.batch_update_products(updates_wc)
                logger.info(f"Batch update concluído")
            
            self.sync_stats['concluido_em'] = datetime.utcnow()
            
            logger.info(f"Sincronização concluída: {self.sync_stats['sucessos']}/{self.sync_stats['produtos_processados']} sucessos")
            
            return {
                'sucesso': True,
                'estatisticas': self.sync_stats,
                'atualizacoes_enviadas': len(updates_wc)
            }
            
        except Exception as e:
            self.sync_stats['concluido_em'] = datetime.utcnow()
            logger.error(f"Erro na sincronização em lote: {e}")
            
            return {
                'sucesso': False,
                'erro': str(e),
                'estatisticas': self.sync_stats
            }
    
    def obter_estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas da última sincronização"""
        return self.sync_stats.copy()