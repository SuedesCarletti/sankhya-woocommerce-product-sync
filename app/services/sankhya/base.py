# app/services/sankhya/base.py
"""
Cliente base para comunicação com Sankhya ERP
Baseado no padrão do seu código existente
"""

import requests
import logging
from typing import Dict, Any, Optional, List
from app.config.settings import load_config

logger = logging.getLogger(__name__)

class SankhyaClient:
    """
    Cliente base para serviços Sankhya
    Fornece métodos comuns para todas as integrações
    """
    
    def __init__(self, token: Optional[str] = None):
        self.config = load_config()
        self.token = token
        self.base_url = self.config['SANKHYA_BASE_URL']
        self.session = requests.Session()
        
        if token:
            self.session.headers.update({
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            })
        
        # Configurar timeout
        self.session.timeout = self.config.get('REQUEST_TIMEOUT', 30)
        
        logger.debug(f"SankhyaClient inicializado com token: {'Sim' if token else 'Não'}")
    
    def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """
        Faz requisição HTTP com tratamento de erros
        """
        try:
            logger.debug(f"{method.upper()} {url}")
            
            response = self.session.request(method, url, **kwargs)
            
            logger.debug(f"Status: {response.status_code}")
            
            # Log do response em debug (cuidado com dados sensíveis)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Response: {response.text[:500]}...")
            
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Erro HTTP Sankhya: {e}")
            logger.error(f"Response: {response.text}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de conexão Sankhya: {e}")
            raise
        except Exception as e:
            logger.error(f"Erro inesperado Sankhya: {e}")
            raise
    
    def load_records(self, entity: str, fields: str, criteria: Dict[str, Any] = None, 
                    limit: int = 100, offset: int = 0, offset_page: int = None) -> Dict[str, Any]:
        """
        Carrega registros usando CRUDServiceProvider.loadRecords
        """
        url = f"{self.base_url}/gateway/v1/mge/service.sbr"
        params = {
            'serviceName': 'CRUDServiceProvider.loadRecords',
            'outputType': 'json'
        }
        
        body = {
            "serviceName": "CRUDServiceProvider.loadRecords",
            "requestBody": {
                "dataSet": {
                    "rootEntity": entity,
                    "offsetPage": str(offset_page if offset_page is not None else offset),
                    "includePresentation": "S",
                    "criteria": criteria or {},
                    "entity": {
                        "fieldset": {
                            "list": fields
                        }
                    }
                }
            }
        }
        
        if limit:
            body["requestBody"]["dataSet"]["limitRows"] = str(limit)
        
        logger.info(f"Consultando {entity}: {fields}")
        logger.debug(f"Critérios: {criteria}")
        
        return self._make_request('POST', url, params=params, json=body)
    
    def save_record(self, entity: str, data: Dict[str, Any], 
                   action: str = "save") -> Dict[str, Any]:
        """
        Salva registro usando CRUDServiceProvider.saveRecord
        """
        url = f"{self.base_url}/gateway/v1/mge/service.sbr"
        params = {
            'serviceName': 'CRUDServiceProvider.saveRecord',
            'outputType': 'json'
        }
        
        body = {
            "serviceName": "CRUDServiceProvider.saveRecord",
            "requestBody": {
                "dataSet": {
                    "rootEntity": entity,
                    "includePresentationFields": "S",
                    "entity": {
                        "fieldset": {
                            "list": ",".join(data.keys())
                        },
                        **data
                    }
                }
            }
        }
        
        logger.info(f"Salvando {entity}")
        logger.debug(f"Dados: {data}")
        
        return self._make_request('POST', url, params=params, json=body)
    
    def execute_service(self, service_name: str, request_body: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executa serviço customizado do Sankhya
        """
        url = f"{self.base_url}/gateway/v1/mge/service.sbr"
        params = {
            'serviceName': service_name,
            'outputType': 'json'
        }
        
        body = {
            "serviceName": service_name,
            "requestBody": request_body or {}
        }
        
        logger.info(f"Executando serviço: {service_name}")
        
        return self._make_request('POST', url, params=params, json=body)
    
    def get_user_info(self) -> Dict[str, Any]:
        """
        Obtém informações do usuário autenticado
        """
        try:
            result = self.execute_service("MobileLoginSP.getUserInfo")
            return result.get('responseBody', {})
        except Exception as e:
            logger.error(f"Erro ao obter info do usuário: {e}")
            return {}
    
    def test_connection(self) -> bool:
        """
        Testa conectividade com Sankhya
        """
        try:
            user_info = self.get_user_info()
            is_connected = bool(user_info)
            
            if is_connected:
                logger.info("Conexão Sankhya OK")
            else:
                logger.warning("Conexão Sankhya com problemas")
            
            return is_connected
            
        except Exception as e:
            logger.error(f"Erro no teste de conexão: {e}")
            return False
    
    def _extract_field_value(self, field_data: Any) -> Any:
        """
        Extrai valor de campo do formato Sankhya
        """
        if isinstance(field_data, dict) and '$' in field_data:
            return field_data['$']
        return field_data
    
    def _format_criteria_expression(self, field: str, operator: str, value: Any, 
                                  field_type: str = "S") -> Dict[str, Any]:
        """
        Formata expressão de critério para consultas
        """
        return {
            "expression": {"$": f"this.{field} {operator} ?"},
            "parameter": [{"$": str(value), "type": field_type}]
        }
    
    def get_entity_metadata(self, entity: str) -> Dict[str, Any]:
        """
        Obtém metadados de uma entidade
        """
        try:
            result = self.execute_service("DbExplorerSP.getMetadata", {
                "entity": entity
            })
            return result.get('responseBody', {})
        except Exception as e:
            logger.error(f"Erro ao obter metadados da entidade {entity}: {e}")
            return {}
