# app/services/sync/queue.py
"""
Sistema de filas para processamento assíncrono de sincronizações
"""

import logging
import threading
import queue
import time
from typing import Dict, Any, Callable, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """Status de uma tarefa na fila"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class TaskPriority(Enum):
    """Prioridade das tarefas"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

@dataclass
class SyncTask:
    """
    Tarefa de sincronização
    """
    id: str
    task_type: str
    data: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    max_retries: int = 3
    retry_count: int = 0
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

class SyncQueue:
    """
    Sistema de filas para sincronização assíncrona
    """
    
    def __init__(self, max_workers: int = 3, queue_size: int = 1000):
        self.max_workers = max_workers
        self.queue_size = queue_size
        
        # Filas por prioridade
        self._queues = {
            TaskPriority.URGENT: queue.PriorityQueue(maxsize=queue_size),
            TaskPriority.HIGH: queue.PriorityQueue(maxsize=queue_size),
            TaskPriority.NORMAL: queue.PriorityQueue(maxsize=queue_size),
            TaskPriority.LOW: queue.PriorityQueue(maxsize=queue_size)
        }
        
        # Controle de workers
        self._workers = []
        self._running = False
        self._shutdown_event = threading.Event()
        
        # Histórico de tarefas
        self._tasks_history = {}
        self._history_lock = threading.Lock()
        
        # Handlers para diferentes tipos de tarefa
        self._task_handlers = {}
        
        # Estatísticas
        self._stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'retried_tasks': 0
        }
        self._stats_lock = threading.Lock()
        
        logger.info(f"SyncQueue inicializada: {max_workers} workers, tamanho {queue_size}")
    
    def register_handler(self, task_type: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """
        Registra handler para um tipo de tarefa
        """
        self._task_handlers[task_type] = handler
        logger.info(f"Handler registrado para tipo: {task_type}")
    
    def add_task(self, task_type: str, data: Dict[str, Any], 
                priority: TaskPriority = TaskPriority.NORMAL,
                max_retries: int = 3) -> str:
        """
        Adiciona tarefa à fila
        """
        if task_type not in self._task_handlers:
            raise ValueError(f"Handler não registrado para tipo: {task_type}")
        
        # Gerar ID único
        task_id = f"{task_type}_{int(time.time() * 1000)}"
        
        task = SyncTask(
            id=task_id,
            task_type=task_type,
            data=data,
            priority=priority,
            max_retries=max_retries
        )
        
        try:
            # Adicionar à fila apropriada
            # Usar negative timestamp para ordem FIFO dentro da mesma prioridade
            priority_value = (-task.priority.value, -time.time())
            self._queues[priority].put((priority_value, task), timeout=1)
            
            # Adicionar ao histórico
            with self._history_lock:
                self._tasks_history[task_id] = task
            
            # Atualizar estatísticas
            with self._stats_lock:
                self._stats['total_tasks'] += 1
            
            logger.info(f"Tarefa adicionada: {task_id} ({task_type}) - Prioridade: {priority.name}")
            return task_id
            
        except queue.Full:
            logger.error(f"Fila cheia para prioridade {priority.name}")
            raise RuntimeError(f"Fila cheia para prioridade {priority.name}")
    
    def start(self):
        """
        Inicia os workers
        """
        if self._running:
            logger.warning("Queue já está rodando")
            return
        
        self._running = True
        self._shutdown_event.clear()
        
        # Criar workers
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"SyncWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)
        
        logger.info(f"SyncQueue iniciada com {len(self._workers)} workers")
    
    def stop(self, timeout: int = 30):
        """
        Para os workers
        """
        if not self._running:
            return
        
        logger.info("Parando SyncQueue...")
        
        self._running = False 
        self._shutdown_event.set()
        
        # Aguardar workers terminarem
        for worker in self._workers:
            worker.join(timeout=timeout)
            if worker.is_alive():
                logger.warning(f"Worker {worker.name} não terminou no tempo esperado")
        
        self._workers.clear()
        logger.info("SyncQueue parada")
    
    def _worker_loop(self):
        """
        Loop principal dos workers
        """
        worker_name = threading.current_thread().name
        logger.info(f"Worker {worker_name} iniciado")
        
        while self._running and not self._shutdown_event.is_set():
            try:
                task = self._get_next_task(timeout=1)
                
                if task:
                    self._process_task(task)
                
            except Exception as e:
                logger.error(f"Erro no worker {worker_name}: {e}")
                time.sleep(1)  # Evitar loop de erro
        
        logger.info(f"Worker {worker_name} finalizado")
    
    def _get_next_task(self, timeout: int = 1) -> Optional[SyncTask]:
        """
        Obtém próxima tarefa da fila (por prioridade)
        """
        # Tentar filas por ordem de prioridade
        for priority in [TaskPriority.URGENT, TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW]:
            try:
                priority_value, task = self._queues[priority].get(timeout=timeout)
                return task
            except queue.Empty:
                continue
        
        return None
    
    def _process_task(self, task: SyncTask):
        """
        Processa uma tarefa
        """
        logger.info(f"Processando tarefa: {task.id}")
        
        # Atualizar status
        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.utcnow()
        
        try:
            # Obter handler
            handler = self._task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"Handler não encontrado para tipo: {task.task_type}")
            
            # Executar handler
            result = handler(task.data)
            
            # Sucesso
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result = result
            
            with self._stats_lock:
                self._stats['completed_tasks'] += 1
            
            logger.info(f"Tarefa concluída: {task.id}")
            
        except Exception as e:
            # Erro
            task.error = str(e)
            task.retry_count += 1
            
            logger.error(f"Erro na tarefa {task.id}: {e}")
            
            # Verificar se deve retentar
            if task.retry_count < task.max_retries:
                logger.info(f"Tentativa {task.retry_count}/{task.max_retries} para tarefa {task.id}")
                
                task.status = TaskStatus.RETRYING
                
                # Adicionar de volta à fila com prioridade menor
                retry_priority = TaskPriority.LOW
                priority_value = (-retry_priority.value, -time.time())
                
                try:
                    self._queues[retry_priority].put((priority_value, task), timeout=1)
                    
                    with self._stats_lock:
                        self._stats['retried_tasks'] += 1
                        
                except queue.Full:
                    logger.error(f"Não foi possível recolocar tarefa na fila: {task.id}")
                    task.status = TaskStatus.FAILED
                    
                    with self._stats_lock:
                        self._stats['failed_tasks'] += 1
            else:
                # Máximo de tentativas atingido
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                
                with self._stats_lock:
                    self._stats['failed_tasks'] += 1
                
                logger.error(f"Tarefa falhou definitivamente: {task.id} (max retries: {task.max_retries})")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém status de uma tarefa
        """
        with self._history_lock:
            task = self._tasks_history.get(task_id)
            
            if not task:
                return None
            
            return {
                'id': task.id,
                'type': task.task_type,
                'status': task.status.value,
                'priority': task.priority.name,
                'created_at': task.created_at.isoformat(),
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'retry_count': task.retry_count,
                'max_retries': task.max_retries,
                'error': task.error,
                'result': task.result
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas da fila
        """
        with self._stats_lock:
            stats = self._stats.copy()
        
        # Adicionar informações das filas
        queue_sizes = {}
        for priority, q in self._queues.items():
            queue_sizes[priority.name] = q.qsize()
        
        return {
            'stats': stats,
            'queue_sizes': queue_sizes,
            'workers': {
                'total': len(self._workers),
                'running': self._running
            },
            'tasks_in_history': len(self._tasks_history),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def clear_history(self, older_than_hours: int = 24):
        """
        Limpa histórico de tarefas antigas
        """
        cutoff_time = datetime.utcnow().timestamp() - (older_than_hours * 3600)
        
        with self._history_lock:
            tasks_to_remove = [
                task_id for task_id, task in self._tasks_history.items()
                if task.created_at.timestamp() < cutoff_time and 
                   task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]
            ]
            
            for task_id in tasks_to_remove:
                del self._tasks_history[task_id]
        
        logger.info(f"Histórico limpo: {len(tasks_to_remove)} tarefas removidas")


# Instância global da fila (singleton)
_sync_queue_instance = None

def get_sync_queue() -> SyncQueue:
    """
    Obtém instância global da fila de sincronização
    """
    global _sync_queue_instance
    
    if _sync_queue_instance is None:
        _sync_queue_instance = SyncQueue()
    
    return _sync_queue_instance