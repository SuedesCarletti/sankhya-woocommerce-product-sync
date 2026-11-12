# app/utils/logger.py
"""
Sistema de logging estruturado
"""

import logging
import logging.handlers
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any
from flask import Flask, request, has_request_context

class StructuredFormatter(logging.Formatter):
    """
    Formatter para logs estruturados em JSON
    """
    
    def format(self, record):
        # Dados base do log
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Adicionar informações da requisição Flask se disponível
        if has_request_context():
            try:
                log_data['request'] = {
                    'method': request.method,
                    'url': request.url,
                    'path': request.path,
                    'remote_addr': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                }
                
                # Adicionar correlation ID se presente
                if hasattr(request, 'correlation_id'):
                    log_data['correlation_id'] = request.correlation_id
                    
            except Exception:
                # Se houver erro ao acessar request, continua sem essas informações
                pass
        
        # Adicionar informações extras do record
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        # Adicionar informações de exceção se houver
        if record.exc_info:
            # exc_info já é formatado pelo logging
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)

class ColoredConsoleFormatter(logging.Formatter):
    """
    Formatter colorido para console (desenvolvimento)
    """
    
    # Cores ANSI
    COLORS = {
        'DEBUG': '\033[36m',     # Ciano
        'INFO': '\033[32m',      # Verde
        'WARNING': '\033[33m',   # Amarelo
        'ERROR': '\033[31m',     # Vermelho
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        # Cor baseada no nível
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Timestamp
        timestamp = datetime.utcnow().strftime('%H:%M:%S')
        
        # Informações da requisição se disponível
        request_info = ""
        if has_request_context():
            try:
                request_info = f" [{request.method} {request.path}]"
            except Exception:
                pass
        
        # Formatar mensagem
        formatted = f"{color}[{timestamp}] {record.levelname:8} {record.name}:{record.lineno}{request_info} - {record.getMessage()}{reset}"
        
        # Adicionar exceção se houver
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted

def setup_logger(app: Flask = None) -> logging.Logger:
    """
    Configura sistema de logging da aplicação
    """
    # Configurações do ambiente
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    is_development = os.getenv('FLASK_ENV') == 'development'
    
    # Logger principal
    logger = logging.getLogger('sankhya-woocommerce-sync')
    logger.setLevel(getattr(logging, log_level))
    
    # Remover handlers existentes para evitar duplicação
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    
    if is_development:
        # Formato colorido para desenvolvimento
        console_formatter = ColoredConsoleFormatter()
    else:
        # Formato JSON estruturado para produção
        console_formatter = StructuredFormatter()
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Handler para arquivo (opcional)
    log_file = os.getenv('LOG_FILE')
    if log_file:
        try:
            # Rotating file handler para evitar arquivos muito grandes
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            
            # Sempre usar formato JSON para arquivo
            file_formatter = StructuredFormatter()
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            logger.info(f"Log em arquivo habilitado: {log_file}")
            
        except Exception as e:
            logger.warning(f"Erro ao configurar log em arquivo: {e}")
    
    # Configurar loggers de bibliotecas externas
    # Reduzir verbosidade de bibliotecas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    
    # Log de inicialização
    logger.info(f"Logger configurado - Nível: {log_level}, Desenvolvimento: {is_development}")
    
    # Configurar Flask app logger se fornecido
    if app:
        app.logger.handlers = logger.handlers
        app.logger.setLevel(logger.level)
        
        # Middleware para adicionar correlation ID
        @app.before_request
        def add_correlation_id():
            if not has_request_context():
                return
            
            # Usar correlation ID do header ou gerar um novo
            correlation_id = request.headers.get('X-Correlation-ID')
            if not correlation_id:
                correlation_id = f"req_{int(datetime.utcnow().timestamp() * 1000)}"
            
            request.correlation_id = correlation_id
        
        # Log de requisições (opcional)
        if os.getenv('LOG_REQUESTS', 'false').lower() == 'true':
            @app.after_request
            def log_request(response):
                if has_request_context():
                    duration = getattr(request, 'start_time', None)
                    duration_ms = int((datetime.utcnow().timestamp() - duration) * 1000) if duration else 0
                    
                    logger.info(
                        f"📥 {request.method} {request.path} - {response.status_code} - {duration_ms}ms",
                        extra={
                            'extra_data': {
                                'http_method': request.method,
                                'http_path': request.path,
                                'http_status': response.status_code,
                                'duration_ms': duration_ms,
                                'correlation_id': getattr(request, 'correlation_id', None)
                            }
                        }
                    )
                
                return response
            
            @app.before_request
            def start_timer():
                request.start_time = datetime.utcnow().timestamp()
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Obtém logger com nome específico
    """
    return logging.getLogger(f'sankhya-woocommerce-sync.{name}')

def log_sync_event(event_type: str, data: Dict[str, Any], level: str = 'info'):
    """
    Log estruturado para eventos de sincronização
    """
    logger = get_logger('sync')
    
    log_data = {
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        **data
    }
    
    message = f"🔄 Sync Event: {event_type}"
    
    # Escolher nível de log
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, extra={'extra_data': log_data})

def log_api_call(service: str, method: str, success: bool, duration_ms: int = None, **kwargs):
    """
    Log estruturado para chamadas de API
    """
    logger = get_logger('api')
    
    log_data = {
        'service': service,
        'method': method,
        'success': success,
        'duration_ms': duration_ms,
        **kwargs
    }
    
    status = "✅" if success else "❌"
    message = f"{status} API Call: {service}.{method}"
    
    level = 'info' if success else 'error'
    log_method = getattr(logger, level)
    log_method(message, extra={'extra_data': log_data})

def log_error_with_context(logger: logging.Logger, message: str, error: Exception, **context):
    """
    Log de erro com contexto adicional
    """
    error_data = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context
    }
    
    logger.error(f"{message}", extra={'extra_data': error_data}, exc_info=True)