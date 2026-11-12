# tests/conftest.py
"""
Configurações globais para testes
"""

import pytest
import os
import sys
from unittest.mock import Mock

# Adicionar app ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.main import create_app
from app.config.settings import load_config

@pytest.fixture
def app():
    """Fixture da aplicação Flask para testes"""
    
    # Configurações de teste
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TESTING'] = 'true'
    os.environ['LOG_LEVEL'] = 'DEBUG'
    
    # Criar app
    app = create_app()
    app.config['TESTING'] = True
    
    # Context
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    """Cliente de teste Flask"""
    return app.test_client()

@pytest.fixture
def auth_headers():
    """Headers de autenticação para testes"""
    return {
        'Authorization': 'Bearer test-token',
        'Content-Type': 'application/json'
    }

@pytest.fixture
def webhook_headers():
    """Headers de webhook para testes"""
    return {
        'Authorization': 'Bearer webhook-secret',
        'Content-Type': 'application/json'
    }

@pytest.fixture
def mock_sankhya_auth():
    """Mock da autenticação Sankhya"""
    with pytest.mock.patch('app.services.sankhya.auth.SankhyaAuth') as mock_auth:
        mock_instance = Mock()
        mock_instance.login.return_value = 'mock-bearer-token'
        mock_instance.logout.return_value = None
        mock_instance.__enter__.return_value = 'mock-bearer-token'
        mock_instance.__exit__.return_value = None
        
        mock_auth.return_value = mock_instance
        yield mock_auth

@pytest.fixture
def mock_woocommerce_client():
    """Mock do client WooCommerce"""
    with pytest.mock.patch('app.services.woocommerce.client.WooCommerceClient') as mock_client:
        mock_instance = Mock()
        
        # Mock de produto
        mock_product = {
            'id': 123,
            'name': 'Produto Teste',
            'sku': '1001',
            'stock_quantity': 10,
            'manage_stock': True,
            'stock_status': 'instock'
        }
        
        mock_instance.find_product_by_sku.return_value = mock_product
        mock_instance.get_product.return_value = mock_product
        mock_instance.update_product_stock.return_value = mock_product
        mock_instance.batch_update_products.return_value = {'update': [mock_product]}
        
        mock_client.return_value = mock_instance
        yield mock_client

@pytest.fixture
def sample_webhook_payload():
    """Payload de exemplo para webhooks"""
    return {
        'nunota': 12345,
        'codparc': 1001,
        'status': 'L',
        'event_type': 'estoque_update',
        'timestamp': '2025-01-30T10:00:00Z',
        'produtos': [
            {
                'codprod': 1001,
                'qtd_vendida': 2,
                'estoque_atual': 48
            },
            {
                'codprod': 1002,
                'qtd_vendida': 1,
                'estoque_atual': 25
            }
        ]
    }

@pytest.fixture
def sample_sync_request():
    """Requisição de sincronização de exemplo"""
    return {
        'produtos': [
            {
                'codprod_sankhya': 1001,
                'sku_wc': '1001'
            },
            {
                'codprod_sankhya': 1002,
                'product_id_wc': 124
            }
        ]
    }