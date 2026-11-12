# tests/test_woocommerce.py
"""
Testes para serviços WooCommerce
"""

import pytest
from unittest.mock import Mock, patch
from app.services.woocommerce.client import WooCommerceClient
from app.services.woocommerce.products import ProductsService

class TestWooCommerceClient:
    """Testes para cliente WooCommerce"""
    
    @patch('app.services.woocommerce.client.requests.Session')
    def test_find_product_by_sku_success(self, mock_session):
        """Teste de busca de produto por SKU com sucesso"""
        # Mock da resposta
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            'id': 123,
            'name': 'Produto Teste',
            'sku': '1001',
            'stock_quantity': 10
        }]
        mock_response.raise_for_status.return_value = None
        
        mock_session_instance = Mock()
        mock_session_instance.request.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Teste
        client = WooCommerceClient()
        client.session = mock_session_instance
        
        produto = client.find_product_by_sku('1001')
        
        assert produto is not None
        assert produto['sku'] == '1001'
        assert produto['id'] == 123
    
    @patch('app.services.woocommerce.client.requests.Session')
    def test_find_product_by_sku_not_found(self, mock_session):
        """Teste de busca de produto não encontrado"""
        # Mock da resposta vazia
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        
        mock_session_instance = Mock()
        mock_session_instance.request.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Teste
        client = WooCommerceClient()
        client.session = mock_session_instance
        
        produto = client.find_product_by_sku('9999')
        
        assert produto is None
    
    @patch('app.services.woocommerce.client.requests.Session')
    def test_update_product_stock(self, mock_session):
        """Teste de atualização de estoque"""
        # Mock da resposta
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'id': 123,
            'stock_quantity': 25,
            'stock_status': 'instock'
        }
        mock_response.raise_for_status.return_value = None
        
        mock_session_instance = Mock()
        mock_session_instance.request.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Teste
        client = WooCommerceClient()
        client.session = mock_session_instance
        
        resultado = client.update_product_stock(123, 25)
        
        assert resultado['stock_quantity'] == 25
        assert resultado['stock_status'] == 'instock'

class TestProductsService:
    """Testes para serviço de produtos"""
    
    def test_init(self, mock_woocommerce_client):
        """Teste de inicialização"""
        service = ProductsService()
        
        assert service.client is not None
        assert service.cache_produtos == {}
    
    def test_find_product_by_sku_with_cache(self, mock_woocommerce_client):
        """Teste de busca com cache"""
        service = ProductsService()
        
        # Primeira busca - vai para o client
        produto1 = service.find_product_by_sku('1001')
        assert produto1 is not None
        assert '1001' in service.cache_produtos
        
        # Segunda busca - vem do cache
        produto2 = service.find_product_by_sku('1001')
        assert produto2 is not None
        assert produto1 == produto2
        
        # Verificar que client foi chamado apenas uma vez
        service.client.find_product_by_sku.assert_called_once()
    
    def test_update_stock_success(self, mock_woocommerce_client):
        """Teste de atualização de estoque com sucesso"""
        service = ProductsService()
        
        # Mock do produto atual
        produto_atual = {
            'id': 123,
            'name': 'Produto Teste',
            'sku': '1001',
            'stock_quantity': 10
        }
        service.client.get_product.return_value = produto_atual
        
        # Mock da atualização
        produto_atualizado = produto_atual.copy()
        produto_atualizado['stock_quantity'] = 25
        service.client.update_product_stock.return_value = produto_atualizado
        
        # Teste
        resultado = service.update_stock(123, 25)
        
        assert resultado['sucesso'] == True
        assert resultado['acao'] == 'atualizado'
        assert resultado['estoque_anterior'] == 10
        assert resultado['estoque_novo'] == 25
    
    def test_update_stock_no_change(self, mock_woocommerce_client):
        """Teste quando estoque já está correto"""
        service = ProductsService()
        
        # Mock do produto com estoque já correto
        produto_atual = {
            'id': 123,
            'stock_quantity': 25
        }
        service.client.get_product.return_value = produto_atual
        
        # Teste
        resultado = service.update_stock(123, 25)
        
        assert resultado['sucesso'] == True
        assert resultado['acao'] == 'nenhuma'
        assert resultado['estoque_anterior'] == 25
        assert resultado['estoque_novo'] == 25
        
        # Verificar que update não foi chamado
        service.client.update_product_stock.assert_not_called()
    
    def test_bulk_update_stock(self, mock_woocommerce_client):
        """Teste de atualização em lote"""
        service = ProductsService()
        
        updates = [
            {'id': 123, 'stock_quantity': 25},
            {'id': 124, 'stock_quantity': 30}
        ]
        
        # Mock da resposta batch
        mock_batch_response = {
            'update': [
                {'id': 123, 'stock_quantity': 25},
                {'id': 124, 'stock_quantity': 30}
            ]
        }
        service.client.batch_update_products.return_value = mock_batch_response
        
        # Teste
        resultado = service.bulk_update_stock(updates)
        
        assert resultado['sucesso'] == True
        assert resultado['produtos_processados'] == 2
        assert resultado['sucessos'] == 2
        assert resultado['erros'] == 0
    
    def test_sync_product_stock(self, mock_woocommerce_client):
        """Teste de sincronização de produto"""
        service = ProductsService()
        
        # Mock find_product_by_sku já configurado no fixture
        # Mock update_stock
        with patch.object(service, 'update_stock') as mock_update:
            mock_update.return_value = {
                'sucesso': True,
                'acao': 'atualizado',
                'estoque_anterior': 10,
                'estoque_novo': 48
            }
            
            resultado = service.sync_product_stock('1001', 48)
            
            assert resultado['sucesso'] == True
            assert resultado['sku'] == '1001'
            assert resultado['sankhya_stock'] == 48