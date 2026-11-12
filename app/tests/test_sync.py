# tests/test_sync.py
"""
Testes para sistema de sincronização
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.sync.engine import SyncEngine
from app.services.sync.queue import SyncQueue, TaskPriority, TaskStatus

class TestSyncEngine:
    """Testes para motor de sincronização"""
    
    @patch('app.services.sync.engine.SankhyaAuth')
    @patch('app.services.sync.engine.WooCommerceClient')
    def test_sincronizar_produto_individual_success(self, mock_wc_client, mock_auth):
        """Teste de sincronização individual com sucesso"""
        # Mock Sankhya
        mock_auth_instance = Mock()
        mock_auth_instance.__enter__.return_value = 'mock-token'
        mock_auth_instance.__exit__.return_value = None
        mock_auth.return_value = mock_auth_instance
        
        # Mock EstoqueService
        with patch('app.services.sync.engine.EstoqueService') as mock_estoque:
            mock_estoque_instance = Mock()
            mock_estoque_instance.obter_estoque_total_produto.return_value = 48
            mock_estoque.return_value = mock_estoque_instance
            
            # Mock WooCommerce
            mock_wc_instance = Mock()
            produto_wc = {
                'id': 123,
                'name': 'Produto Teste',
                'sku': '1001',
                'stock_quantity': 10
            }
            mock_wc_instance.find_product_by_sku.return_value = produto_wc
            mock_wc_instance.update_product_stock.return_value = produto_wc
            mock_wc_client.return_value = mock_wc_instance
            
            # Teste
            engine = SyncEngine()
            resultado = engine.sincronizar_produto_individual(1001, sku_wc='1001')
            
            assert resultado['sucesso'] == True
            assert resultado['acao'] == 'atualizado'
            assert resultado['estoque_anterior'] == 10
            assert resultado['estoque_novo'] == 48
    
    @patch('app.services.sync.engine.SankhyaAuth')
    @patch('app.services.sync.engine.WooCommerceClient')
    def test_sincronizar_produto_individual_produto_nao_encontrado(self, mock_wc_client, mock_auth):
        """Teste quando produto não é encontrado no WooCommerce"""
        # Mock Sankhya
        mock_auth_instance = Mock()
        mock_auth_instance.__enter__.return_value = 'mock-token'
        mock_auth.return_value = mock_auth_instance
        
        with patch('app.services.sync.engine.EstoqueService') as mock_estoque:
            mock_estoque_instance = Mock()
            mock_estoque_instance.obter_estoque_total_produto.return_value = 48
            mock_estoque.return_value = mock_estoque_instance
            
            # Mock WooCommerce - produto não encontrado
            mock_wc_instance = Mock()
            mock_wc_instance.find_product_by_sku.return_value = None
            mock_wc_client.return_value = mock_wc_instance
            
            # Teste
            engine = SyncEngine()
            resultado = engine.sincronizar_produto_individual(1001, sku_wc='1001')
            
            assert resultado['sucesso'] == False
            assert 'não encontrado' in resultado['erro']
    
    @patch('app.services.sync.engine.SankhyaAuth')
    @patch('app.services.sync.engine.WooCommerceClient')
    def test_sincronizar_produto_individual_estoque_igual(self, mock_wc_client, mock_auth):
        """Teste quando estoques já estão sincronizados"""
        # Mock Sankhya
        mock_auth_instance = Mock()
        mock_auth_instance.__enter__.return_value = 'mock-token'
        mock_auth.return_value = mock_auth_instance
        
        with patch('app.services.sync.engine.EstoqueService') as mock_estoque:
            mock_estoque_instance = Mock()
            mock_estoque_instance.obter_estoque_total_produto.return_value = 48
            mock_estoque.return_value = mock_estoque_instance
            
            # Mock WooCommerce - estoque igual
            mock_wc_instance = Mock()
            produto_wc = {
                'id': 123,
                'stock_quantity': 48
            }
            mock_wc_instance.find_product_by_sku.return_value = produto_wc
            mock_wc_client.return_value = mock_wc_instance
            
            # Teste
            engine = SyncEngine()
            resultado = engine.sincronizar_produto_individual(1001, sku_wc='1001')
            
            assert resultado['sucesso'] == True
            assert resultado['acao'] == 'nenhuma'
            assert resultado['estoque_sankhya'] == 48
            assert resultado['estoque_woocommerce'] == 48

class TestSyncQueue:
    """Testes para sistema de filas"""
    
    def test_init(self):
        """Teste de inicialização"""
        queue = SyncQueue(max_workers=2, queue_size=100)
        
        assert queue.max_workers == 2
        assert queue.queue_size == 100
        assert len(queue._queues) == 4  # Uma para cada prioridade
        assert not queue._running
    
    def test_register_handler(self):
        """Teste de registro de handler"""
        queue = SyncQueue()
        
        def test_handler(data):
            return {'success': True}
        
        queue.register_handler('test_task', test_handler)
        
        assert 'test_task' in queue._task_handlers
        assert queue._task_handlers['test_task'] == test_handler
    
    def test_add_task(self):
        """Teste de adição de tarefa"""
        queue = SyncQueue()
        
        # Registrar handler
        def test_handler(data):
            return {'success': True}
        
        queue.register_handler('test_task', test_handler)
        
        # Adicionar tarefa
        task_id = queue.add_task('test_task', {'param': 'value'})
        
        assert task_id is not None
        assert task_id.startswith('test_task_')
        assert queue._stats['total_tasks'] == 1
    
    def test_add_task_without_handler(self):
        """Teste de adição de tarefa sem handler registrado"""
        queue = SyncQueue()
        
        with pytest.raises(ValueError, match="Handler não registrado"):
            queue.add_task('unknown_task', {})
    
    def test_start_stop(self):
        """Teste de iniciar e parar workers"""
        queue = SyncQueue(max_workers=2)
        
        # Iniciar
        queue.start()
        assert queue._running == True
        assert len(queue._workers) == 2
        
        # Parar
        queue.stop(timeout=1)
        assert queue._running == False
        assert len(queue._workers) == 0
    
    def test_get_task_status(self):
        """Teste de obtenção de status de tarefa"""
        queue = SyncQueue()
        
        # Registrar handler
        def test_handler(data):
            return {'success': True}
        
        queue.register_handler('test_task', test_handler)
        
        # Adicionar tarefa
        task_id = queue.add_task('test_task', {'param': 'value'}, TaskPriority.HIGH)
        
        # Verificar status
        status = queue.get_task_status(task_id)
        
        assert status is not None
        assert status['id'] == task_id
        assert status['type'] == 'test_task'
        assert status['status'] == TaskStatus.PENDING.value
        assert status['priority'] == TaskPriority.HIGH.name
    
    def test_get_stats(self):
        """Teste de obtenção de estatísticas"""
        queue = SyncQueue()
        
        # Registrar handler
        def test_handler(data):
            return {'success': True}
        
        queue.register_handler('test_task', test_handler)
        
        # Adicionar algumas tarefas
        queue.add_task('test_task', {}, TaskPriority.HIGH)
        queue.add_task('test_task', {}, TaskPriority.NORMAL)
        
        # Verificar stats
        stats = queue.get_stats()
        
        assert stats['stats']['total_tasks'] == 2
        assert stats['workers']['total'] == queue.max_workers
        assert stats['workers']['running'] == queue._running
        assert 'HIGH' in stats['queue_sizes']
        assert 'NORMAL' in stats['queue_sizes']