# app/config/settings.py
import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """
    Carrega configurações de ambiente com fallbacks seguros
    """
    return {
        # Flask
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-key-change-in-production'),
        'DEBUG': os.getenv('FLASK_ENV') == 'development',
        
        # Sankhya ERP
        'SANKHYA_BASE_URL': os.getenv('SANKHYA_BASE_URL', 'https://api.sankhya.com.br'),
        'SANKHYA_TOKEN': os.getenv('SANKHYA_TOKEN', ''),
        'SANKHYA_APPKEY': os.getenv('SANKHYA_APPKEY', ''),
        'SANKHYA_USERNAME': os.getenv('SANKHYA_USERNAME', ''),
        'SANKHYA_PASSWORD': os.getenv('SANKHYA_PASSWORD', ''),
        
        # WooCommerce
        'WOOCOMMERCE_URL': os.getenv('WOOCOMMERCE_URL', ''),
        'WOOCOMMERCE_CONSUMER_KEY': os.getenv('WOOCOMMERCE_CONSUMER_KEY', ''),
        'WOOCOMMERCE_CONSUMER_SECRET': os.getenv('WOOCOMMERCE_CONSUMER_SECRET', ''),
        
        # Autenticação
        'API_TOKEN': os.getenv('API_TOKEN', 'default-api-token'),
        'WEBHOOK_SECRET': os.getenv('WEBHOOK_SECRET', 'webhook-secret'),
        
        # Rate Limiting
        'RATE_LIMIT_PER_MINUTE': int(os.getenv('RATE_LIMIT_PER_MINUTE', '60')),
        
        # Timeouts
        'REQUEST_TIMEOUT': int(os.getenv('REQUEST_TIMEOUT', '30')),
        
        # Logging
        'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
    }

def get_sankhya_defaults():
    """Retorna configurações padrão do Sankhya"""
    return {
        'CODLOCALORIG': os.getenv('SANKHYA_DEFAULT_CODLOCALORIG', '101'),
        'CODEMP': os.getenv('SANKHYA_DEFAULT_CODEMP', '1'),
        'CODVOL': os.getenv('SANKHYA_DEFAULT_CODVOL', 'UN'),
        'CODTIPOPER': os.getenv('SANKHYA_DEFAULT_CODTIPOPER', '1000'),
    }