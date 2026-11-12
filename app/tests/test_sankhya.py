# tests/test_sankhya.py
"""
Testes para serviços Sankhya
"""

import pytest
from unittest.mock import Mock, patch
from app.services.sankhya.auth import SankhyaAuth
from app.services.sankhya.estoque import EstoqueService
from app.services.sankhya.service import SankhyaService

class TestSankhyaAuth:
    """Testes para autenticação Sankhya"""
    
    @patch('app.services.sankhya.auth.requests.Session')
    def test_login_success(self, mock_session):
        """Teste de login com sucesso"""
        # Mock da resposta
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'bearerToken': 'test-token'}
        mock_response.raise_for_status.return_value = None
        
        mock_session_instance = Mock()
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Teste
        auth = SankhyaAuth()
        token = auth.login('test_user', 'test_pass')
        
        assert token == 'test-token'
        assert auth.token == 'test-token'
        mock_session_instance.post.assert_called_once()
    
    @patch('app.services.sankhya.auth.requests.Session')
    def test_login_failure(self, mock_session):
        """Teste de falha no login"""
        # Mock da resposta de erro
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("Unauthorized")
        
        mock_session_instance = Mock()
        mock_session_instance.post.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Teste
        auth = SankhyaAuth()
        
        with pytest.raises(Exception):
            auth.login('wrong_user', 'wrong_pass')
    
    def test_context_manager(self, mock_sankhya_auth):
        """Teste do context manager"""
        with SankhyaAuth() as token:
            assert token == 'mock-bearer-token'

class TestEstoqueService:
    """Testes para serviço de estoque"""
    
    def test_is_local_venda(self):
        """Teste de validação de local de venda"""
        service = EstoqueService()
        
        # Locais válidos
        assert service._is_local_venda('101') == True
        assert service._is_local_venda('201') == True
        assert service._is_local_venda('1001') == True
        
        # Locais inválidos
        assert service._is_local_venda('100') == False
        assert service._is_local_venda('102') == False
        assert service._is_local_venda('01') == False
        assert service._is_local_venda('abc01') == False
    
    @patch('app.services.sankhya.estoque.EstoqueService.load_records')
    def test_consultar_estoque_produto(self, mock_load_records):
        """Teste de consulta de estoque"""
        # Mock da resposta
        mock_response = {
            'responseBody': {
                'entities': {
                    'total': '1',
                    'entity': {
                        'f0': {'$': '1001'},  # CODPROD
                        'f1': {'$': '101'},   # CODLOCAL
                        'f2': {'$': '50'},    # ESTOQUE
                        'f3': {'$': '2'},     # RESERVADO
                        'f4': {'$': 'S'},     # ATIVO
                        'f5': {'$': '1'}      # CODEMP
                    }
                }
            }
        }
        
        mock_load_records.return_value = mock_response
        
        # Teste
        service = EstoqueService('mock-token')
        resultado = service.consultar_estoque_produto(1001)
        
        assert len(resultado) == 1
        assert resultado[0]['CODPROD'] == '1001'
        assert resultado[0]['ESTOQUE'] == 50.0
        assert resultado[0]['RESERVADO'] == 2.0
    
    @patch('app.services.sankhya.estoque.EstoqueService.consultar_estoque_produto')
    def test_obter_estoque_total_produto(self, mock_consultar):
        """Teste de cálculo de estoque total"""
        # Mock de múltiplos locais
        mock_consultar.return_value = [
            {'ESTOQUE': 30, 'RESERVADO': 2},
            {'ESTOQUE': 20, 'RESERVADO': 1},
            {'ESTOQUE': 10, 'RESERVADO': 0}
        ]
        
        service = EstoqueService('mock-token')
        estoque_total = service.obter_estoque_total_produto(1001)
        
        # (30-2) + (20-1) + (10-0) = 57
        assert estoque_total == 57

class TestSankhyaService:
    """Testes para serviço principal Sankhya"""
    
    def test_init_without_token(self):
        """Teste de inicialização sem token"""
        service = SankhyaService()
        
        assert service.token is None
        assert not service.is_authenticated()
    
    def test_init_with_token(self, mock_sankhya_auth):
        """Teste de inicialização com token"""
        service = SankhyaService('test-token')
        
        assert service.token == 'test-token'
        assert service.is_authenticated()
        assert service._estoque_service is not None
    
    @patch('app.services.sankhya.service.EstoqueService')
    def test_obter_estoque_produto_success(self, mock_estoque_service):
        """Teste de obtenção de estoque com sucesso"""
        # Mock do serviço de estoque
        mock_service_instance = Mock()
        mock_service_instance.consultar_estoque_produto.return_value = [
            {'ESTOQUE': 50, 'RESERVADO': 2}
        ]
        mock_estoque_service.return_value = mock_service_instance
        
        service = SankhyaService('test-token')
        service._estoque_service = mock_service_instance
        
        resultado = service.obter_estoque_produto(1001)
        
        assert resultado['sucesso'] == True
        assert resultado['codprod'] == 1001
        assert resultado['estoque_total'] == 48  # 50 - 2
    
    def test_context_manager(self, mock_sankhya_auth):
        """Teste do context manager"""
        with SankhyaService.with_auth() as service:
            assert isinstance(service, SankhyaService)
            assert service.is_authenticated()