# app/services/woocommerce/products.py
"""
Serviço especializado para gestão de produtos WooCommerce
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from .client import WooCommerceClient

logger = logging.getLogger(__name__)

class ProductsService:
    """
    Serviço especializado para operações com produtos WooCommerce
    """
    
    def __init__(self, client: WooCommerceClient = None):
        self.client = client or WooCommerceClient()
        self.cache_produtos = {}  # Cache simples para produtos
        
        logger.info("ProductsService inicializado")
    
    def find_product_by_sku(self, sku: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Busca produto por SKU com cache opcional
        """
        if use_cache and sku in self.cache_produtos:
            logger.debug(f"Cache hit para SKU: {sku}")
            return self.cache_produtos[sku]
        
        try:
            logger.info(f"Buscando produto por SKU: {sku}")
            
            produto = self.client.find_product_by_sku(sku)
            
            if produto and use_cache:
                self.cache_produtos[sku] = produto
                logger.debug(f"Produto {sku} adicionado ao cache")
            
            if produto:
                logger.info(f"Produto encontrado: {produto['name']} (ID: {produto['id']})")
            else:
                logger.warning(f"Produto não encontrado para SKU: {sku}")
            
            return produto
            
        except Exception as e:
            logger.error(f"Erro ao buscar produto por SKU {sku}: {e}")
            return None
    
    def find_products_by_skus(self, skus: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Busca múltiplos produtos por SKU
        """
        logger.info(f"Buscando {len(skus)} produtos por SKU")
        
        resultado = {}
        
        for sku in skus:
            try:
                produto = self.find_product_by_sku(sku)
                resultado[sku] = produto
                
            except Exception as e:
                logger.error(f"Erro no SKU {sku}: {e}")
                resultado[sku] = None
        
        encontrados = sum(1 for p in resultado.values() if p is not None)
        logger.info(f"Encontrados {encontrados}/{len(skus)} produtos")
        
        return resultado
    
    def update_stock(self, product_id: int, stock_quantity: int, 
                    manage_stock: bool = True) -> Dict[str, Any]:
        """
        Atualiza estoque de um produto com validações
        """
        try:
            logger.info(f"Atualizando estoque produto {product_id}: {stock_quantity}")
            
            # Validações
            if stock_quantity < 0:
                logger.warning(f"Estoque negativo convertido para 0: {stock_quantity}")
                stock_quantity = 0
            
            # Buscar produto atual para comparação
            produto_atual = self.client.get_product(product_id)
            if not produto_atual:
                raise ValueError(f"Produto {product_id} não encontrado")
            
            estoque_atual = produto_atual.get('stock_quantity', 0) or 0
            
            # Se o estoque é o mesmo, não precisa atualizar
            if estoque_atual == stock_quantity:
                logger.info(f"Estoque já está correto: {stock_quantity}")
                return {
                    'sucesso': True,
                    'acao': 'nenhuma',
                    'product_id': product_id,
                    'estoque_anterior': estoque_atual,
                    'estoque_novo': stock_quantity,
                    'mensagem': 'Estoque já estava correto'
                }
            
            # Atualizar
            resultado = self.client.update_product_stock(
                product_id, 
                stock_quantity, 
                manage_stock
            )
            
            # Limpar cache se existir
            produto_name = produto_atual.get('name', f'ID{product_id}')
            sku = produto_atual.get('sku', '')
            
            if sku and sku in self.cache_produtos:
                del self.cache_produtos[sku]
                logger.debug(f"Cache limpo para SKU: {sku}")
            
            logger.info(f"Estoque atualizado: {produto_name} ({estoque_atual} → {stock_quantity})")
            
            return {
                'sucesso': True,
                'acao': 'atualizado',
                'product_id': product_id,
                'product_name': produto_name,
                'sku': sku,
                'estoque_anterior': estoque_atual,
                'estoque_novo': stock_quantity,
                'mensagem': f'Estoque atualizado de {estoque_atual} para {stock_quantity}',
                'woocommerce_response': resultado
            }
            
        except Exception as e:
            logger.error(f"Erro ao atualizar estoque do produto {product_id}: {e}")
            return {
                'sucesso': False,
                'product_id': product_id,
                'erro': str(e)
            }
    
    def bulk_update_stock(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Atualiza estoque de múltiplos produtos em lote
        
        Args:
            updates: Lista de dicts com 'id', 'stock_quantity', opcionalmente 'manage_stock'
        """
        logger.info(f"Atualizando estoque em lote: {len(updates)} produtos")
        
        try:
            # Preparar dados para WooCommerce
            wc_updates = []
            for update in updates:
                product_id = update.get('id')
                stock_quantity = update.get('stock_quantity', 0)
                manage_stock = update.get('manage_stock', True)
                
                if not product_id:
                    logger.warning(f"Update sem ID ignorado: {update}")
                    continue
                
                # Garantir que estoque não seja negativo
                if stock_quantity < 0:
                    stock_quantity = 0
                
                wc_updates.append({
                    'id': product_id,
                    'stock_quantity': stock_quantity,
                    'manage_stock': manage_stock,
                    'stock_status': 'instock' if stock_quantity > 0 else 'outofstock'
                })
            
            if not wc_updates:
                return {
                    'sucesso': False,
                    'erro': 'Nenhuma atualização válida fornecida'
                }
            
            # Executar batch update
            resultado = self.client.batch_update_products(wc_updates)
            
            # Processar resultado
            updated = resultado.get('update', [])
            sucessos = len([u for u in updated if 'error' not in u])
            erros = len(updated) - sucessos
            
            # Limpar cache dos produtos atualizados
            for update in wc_updates:
                # Tentar encontrar no cache e remover
                for sku, produto_cache in list(self.cache_produtos.items()):
                    if produto_cache.get('id') == update['id']:
                        del self.cache_produtos[sku]
                        logger.debug(f"Cache limpo para produto ID: {update['id']}")
                        break
            
            logger.info(f"Batch update concluído: {sucessos} sucessos, {erros} erros")
            
            return {
                'sucesso': True,
                'produtos_processados': len(wc_updates),
                'sucessos': sucessos,
                'erros': erros,
                'detalhes': updated,
                'woocommerce_response': resultado
            }
            
        except Exception as e:
            logger.error(f"Erro no batch update: {e}")
            return {
                'sucesso': False,
                'erro': str(e),
                'produtos_solicitados': len(updates)
            }
    
    def get_stock_info(self, product_id: int) -> Dict[str, Any]:
        """
        Obtém informações detalhadas de estoque de um produto
        """
        try:
            produto = self.client.get_product(product_id)
            
            if not produto:
                return {
                    'sucesso': False,
                    'erro': f'Produto {product_id} não encontrado'
                }
            
            return {
                'sucesso': True,
                'product_id': product_id,
                'name': produto.get('name', ''),
                'sku': produto.get('sku', ''),
                'stock_quantity': produto.get('stock_quantity', 0),
                'manage_stock': produto.get('manage_stock', False),
                'stock_status': produto.get('stock_status', ''),
                'backorders': produto.get('backorders', 'no'),
                'low_stock_amount': produto.get('low_stock_amount', ''),
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter info de estoque do produto {product_id}: {e}")
            return {
                'sucesso': False,
                'product_id': product_id,
                'erro': str(e)
            }
    
    def sync_product_stock(self, sku: str, sankhya_stock: int) -> Dict[str, Any]:
        """
        Sincroniza estoque de um produto específico
        """
        try:
            logger.info(f"Sincronizando estoque: SKU {sku} → {sankhya_stock}")
            
            # 1. Encontrar produto no WooCommerce
            produto = self.find_product_by_sku(sku)
            
            if not produto:
                return {
                    'sucesso': False,
                    'sku': sku,
                    'erro': f'Produto com SKU {sku} não encontrado no WooCommerce'
                }
            
            # 2. Atualizar estoque
            resultado = self.update_stock(produto['id'], sankhya_stock)
            
            # 3. Adicionar informações do SKU
            resultado['sku'] = sku
            resultado['sankhya_stock'] = sankhya_stock
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro na sincronização do SKU {sku}: {e}")
            return {
                'sucesso': False,
                'sku': sku,
                'sankhya_stock': sankhya_stock,
                'erro': str(e)
            }
    
    def clear_cache(self):
        """Limpa cache de produtos"""
        cache_size = len(self.cache_produtos)
        self.cache_produtos.clear()
        logger.info(f"Cache limpo: {cache_size} produtos removidos")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache"""
        return {
            'produtos_em_cache': len(self.cache_produtos),
            'skus_em_cache': list(self.cache_produtos.keys()),
            'timestamp': datetime.utcnow().isoformat()
        }