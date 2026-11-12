import requests
import logging
from typing import Dict, List, Any, Optional
from requests.auth import HTTPBasicAuth
from app.config.settings import load_config

logger = logging.getLogger(__name__)

class WooCommerceClient:
    """Cliente para comunicação com WooCommerce REST API"""
    
    def __init__(self):
        self.config = load_config()
        self.base_url = self.config['WOOCOMMERCE_URL'].rstrip('/')
        self.consumer_key = self.config['WOOCOMMERCE_CONSUMER_KEY']
        self.consumer_secret = self.config['WOOCOMMERCE_CONSUMER_SECRET']
        
        if not all([self.base_url, self.consumer_key, self.consumer_secret]):
            raise ValueError("Configurações WooCommerce incompletas")
        
        self.api_url = f"{self.base_url}/wp-json/wc/v3"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        self.session.timeout = self.config.get('REQUEST_TIMEOUT', 30)
        
        logger.info(f"Cliente WooCommerce inicializado: {self.base_url}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Faz requisição para API WooCommerce com tratamento de erros"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"{method.upper()} {endpoint}")
            
            response = self.session.request(method, url, **kwargs)
            
            logger.debug(f"Status: {response.status_code}")
            
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP WooCommerce: {e}")
            logger.error(f"Response: {response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão WooCommerce: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado WooCommerce: {e}")
            raise
    
    def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Busca produto por ID"""
        try:
            return self._make_request('GET', f'products/{product_id}')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def find_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Busca produto por SKU"""
        try:
            params = {'sku': sku, 'per_page': 1}
            products = self._make_request('GET', 'products', params=params)
            
            return products[0] if products else None
            
        except Exception as e:
            logger.error(f"Erro ao buscar produto por SKU {sku}: {e}")
            return None
    
    def update_product_stock(self, product_id: int, stock_quantity: int, 
                           manage_stock: bool = True) -> Dict[str, Any]:
        """Atualiza estoque de um produto"""
        data = {
            'stock_quantity': stock_quantity,
            'manage_stock': manage_stock,
            'stock_status': 'instock' if stock_quantity > 0 else 'outofstock'
        }
        
        logger.info(f"Atualizando produto {product_id}: estoque → {stock_quantity}")
        
        return self._make_request('PUT', f'products/{product_id}', json=data)
    
    def batch_update_products(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Atualiza múltiplos produtos em lote"""
        data = {'update': updates}
        
        logger.info(f"Atualizando {len(updates)} produtos em lote")
        
        return self._make_request('POST', 'products/batch', json=data)
    
    def get_products(self, per_page: int = 10, page: int = 1, **params) -> List[Dict[str, Any]]:
        """Lista produtos com paginação"""
        params.update({'per_page': per_page, 'page': page})
        
        return self._make_request('GET', 'products', params=params)

    # CORREÇÃO: ADICIONAR MÉTODO update_order para a funcionalidade de NF-e
    def update_order(self, order_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza um pedido existente (necessário para metadados da NF-e)"""
        logger.info(f"Atualizando pedido {order_id} com dados da NF-e")
        return self._make_request('PUT', f'orders/{order_id}', json=data)

    def add_order_note(self, order_id: int, note: str, customer_note: bool = True) -> Dict[str, Any]:
        """Adiciona uma nota a um pedido existente"""
        data = {
            'note': note,
            'customer_note': customer_note
        }
        logger.info(f"Adicionando nota ao pedido {order_id}")
        return self._make_request('POST', f'orders/{order_id}/notes', json=data)

    def find_order_by_meta(self, meta_key: str, meta_value: str) -> Optional[Dict[str, Any]]:
        """
        Busca um pedido pelo valor de um campo de metadado.
        Usa o filtro meta_key/meta_value da API WooCommerce.
        Retorna o primeiro pedido encontrado ou None.
        """
        try:
            orders = self._make_request('GET', 'orders', params={
                'meta_key': meta_key,
                'meta_value': str(meta_value),
                'per_page': 1
            })
            return orders[0] if orders else None
        except Exception as e:
            logger.error(f"Erro ao buscar pedido por meta {meta_key}={meta_value}: {e}")
            return None

    def find_order_by_nunota(self, nunota: int) -> Optional[Dict[str, Any]]:
        """
        Busca o pedido WooCommerce que tem _sankhya_nunota = nunota.
        É a fonte da verdade quando AD_IDWOOCOMMERCE está ausente no Sankhya.
        """
        logger.info(f"Buscando pedido WooCommerce com _sankhya_nunota={nunota}")
        return self.find_order_by_meta('_sankhya_nunota', str(nunota))
