# app/services/sankhya/auth.py
"""
SankhyaAuth - Adaptado para o intermediador
Baseado no seu arquivo auth.py existente
"""

import requests
import logging
from app.config.settings import load_config

logger = logging.getLogger(__name__)

class SankhyaAuth:
    """Context manager para autenticação Sankhya"""
    
    def __init__(self):
        self.config = load_config()
        self.token = None
        self.session = requests.Session()
        
        # Configurar timeout padrão
        self.session.timeout = self.config.get('REQUEST_TIMEOUT', 30)
    
    def login(self, usuario=None, senha=None):
        """Realiza login no Sankhya"""
        username = usuario or self.config['SANKHYA_USERNAME']
        password = senha or self.config['SANKHYA_PASSWORD']
        
        headers = {
            'token': self.config['SANKHYA_TOKEN'],
            'appkey': self.config['SANKHYA_APPKEY'],
            'username': username,
            'password': password,
            'Content-Type': 'application/json'
        }
        
        login_url = f'{self.config["SANKHYA_BASE_URL"]}/login'
        
        logger.info(f"Autenticando usuário: {username}")
        
        try:
            response = self.session.post(login_url, headers=headers)
            logger.info(f"Status autenticação: {response.status_code}")
            
            response.raise_for_status()
            
            response_data = response.json()
            bearer_token = response_data.get('bearerToken')
            
            if not bearer_token:
                raise ValueError("Bearer token não encontrado na resposta")
                
            logger.info("Login realizado com sucesso")
            self.token = bearer_token
            
            # Atualizar headers da sessão
            self.session.headers.update({
                'Authorization': f'Bearer {bearer_token}',
                'Content-Type': 'application/json'
            })
            
            return bearer_token
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP na autenticação: {e}")
            logger.error(f"Response: {response.text}")
            raise
        except Exception as e:
            logger.error(f"Erro na autenticação: {e}")
            raise

    def logout(self):
        """Realiza logout do Sankhya"""
        if not self.token:
            logger.warning("Tentativa de logout sem token")
            return
            
        url = f'{self.config["SANKHYA_BASE_URL"]}/gateway/v1/mge/service.sbr'
        params = {
            'serviceName': 'MobileLoginSP.logout',
            'outputType': 'json'
        }
        
        try:
            response = self.session.post(url, params=params)
            logger.info(f"Logout - Status: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("Logout realizado com sucesso")
        except Exception as e:
            logger.warning(f"Erro no logout: {e}")
        finally:
            self.token = None
            # Limpar headers de autenticação
            self.session.headers.pop('Authorization', None)

    def __enter__(self):
        """Context manager enter"""
        self.token = self.login()
        return self.token

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.logout()
        return False

    def is_authenticated(self):
        """Verifica se está autenticado"""
        return self.token is not None
    
    def get_session(self):
        """Retorna sessão autenticada"""
        if not self.is_authenticated():
            raise RuntimeError("Não autenticado. Execute login() primeiro.")
        return self.session
