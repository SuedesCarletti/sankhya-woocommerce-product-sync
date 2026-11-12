# app/services/sankhya/estoque.py
"""
EstoqueService - Adaptado do seu código existente
"""

import logging
from typing import List, Dict, Any, Optional
from .base import SankhyaClient

logger = logging.getLogger(__name__)

class EstoqueService(SankhyaClient):
    """Serviço para consulta e gestão de estoque"""
    
    def __init__(self, token=None):
        super().__init__(token)
        self.cache_locais_produto = {}

    def consultar_estoque_produto(self, codprod: int, somente_venda: bool = True) -> List[Dict[str, Any]]:
        """
        Consulta estoque do produto e retorna locais disponíveis
        Adaptado do seu código original
        """
        try:
            cache_key = f"{codprod}_{somente_venda}"
            if cache_key in self.cache_locais_produto:
                logger.info(f"Cache hit para produto {codprod}")
                return self.cache_locais_produto[cache_key]

            logger.info(f"Consultando estoque do produto: {codprod}")
            
            # 1. VALIDAÇÃO AD_PROD_SITE (Query separada para evitar erro de JOIN no Sankhya)
            try:
                prod_criteria = {
                    "expression": {"$": "this.CODPROD = ?"},
                    "parameter": [{"$": str(codprod), "type": "I"}]
                }
                prod_result = self.load_records(
                    entity="Produto",
                    fields="AD_PROD_SITE",
                    criteria=prod_criteria
                )
                
                prod_entities = prod_result.get("responseBody", {}).get("entities", {})
                if int(prod_entities.get("total", "0")) > 0:
                    prod_entity = prod_entities.get("entity", {})
                    if isinstance(prod_entity, list):
                        prod_entity = prod_entity[0]
                    # f0 é o campo retornado (AD_PROD_SITE)
                    ad_prod_site = prod_entity.get("f0", {}).get("$", "")
                    
                    if str(ad_prod_site) != "1":
                        logger.warning(f"Produto {codprod} ignorado (AD_PROD_SITE = {ad_prod_site}). Retornando estoque 0.")
                        self.cache_locais_produto[cache_key] = []
                        return []
                else:
                    self.cache_locais_produto[cache_key] = []
                    return []
            except Exception as e:
                logger.error(f"Erro ao validar AD_PROD_SITE do produto {codprod}: {e}")
                self.cache_locais_produto[cache_key] = []
                return []

            # 2. Monta critério de busca (Original sem o join com Produto)
            if somente_venda:
                expression = "this.CODPROD = ? AND this.ATIVO = 'S' AND this.ESTOQUE > 0 AND (this.CODLOCAL = '201' OR this.CODLOCAL = '401')"
                parameters = [{"$": str(codprod), "type": "I"}]
            else:
                expression = "this.CODPROD = ? AND this.ATIVO = 'S' AND this.ESTOQUE > 0"
                parameters = [{"$": str(codprod), "type": "I"}]
            
            criteria = {
                "expression": {"$": expression},
                "parameter": parameters
            }
            
            # Consulta estoque
            result = self.load_records(
                entity="Estoque",
                fields="CODPROD,CODLOCAL,ESTOQUE,RESERVADO,ATIVO,CODEMP",
                criteria=criteria,
                limit=50
            )
            
            entities = result.get("responseBody", {}).get("entities", {})
            total = int(entities.get("total", "0"))
            
            if total == 0:
                logger.warning(f"Produto {codprod} não encontrado no estoque")
                self.cache_locais_produto[cache_key] = []
                return []
            
            # Processa resultados
            entity_list = entities.get("entity", [])
            if not isinstance(entity_list, list):
                entity_list = [entity_list]
            
            estoques = []
            for entity in entity_list:
                estoque_info = {
                    'CODPROD': entity.get('f0', {}).get('$', ''),
                    'CODLOCAL': entity.get('f1', {}).get('$', ''),
                    'ESTOQUE': float(entity.get('f2', {}).get('$', '0')),
                    'RESERVADO': float(entity.get('f3', {}).get('$', '0')),
                    'ATIVO': entity.get('f4', {}).get('$', 'S'),
                    'CODEMP': entity.get('f5', {}).get('$', '')
                }
                
                # Validação adicional
                if somente_venda and not self._is_local_venda(estoque_info['CODLOCAL']):
                    continue
                
                estoques.append(estoque_info)
            
            # Ordena por estoque disponível
            estoques.sort(key=lambda x: x['ESTOQUE'] - x['RESERVADO'], reverse=True)
            
            logger.info(f"Encontrados {len(estoques)} locais para produto {codprod}")
            
            # Cache do resultado
            self.cache_locais_produto[cache_key] = estoques
            
            return estoques
            
        except Exception as e:
            logger.error(f"Erro ao consultar estoque do produto {codprod}: {e}")
            return []
    
    def _is_local_venda(self, codlocal: str) -> bool:
        """Verifica se o local é para venda (termina com "01")"""
        try:
            codlocal_str = str(codlocal)
            return (codlocal_str.endswith("01") and 
                   len(codlocal_str) >= 3 and 
                   codlocal_str.isdigit())
        except Exception:
            return False
    
    def obter_estoque_total_produto(self, codprod: int) -> int:
        """
        Obtém estoque total disponível do produto (soma todos os locais)
        """
        try:
            estoques = self.consultar_estoque_produto(codprod, somente_venda=True)
            
            if not estoques:
                logger.warning(f"Produto {codprod} sem estoque disponível")
                return 0
            
            estoque_total = sum(
                max(0, item['ESTOQUE'] - item['RESERVADO']) 
                for item in estoques
            )
            
            logger.info(f"Produto {codprod}: {estoque_total} unidades disponíveis")
            return int(estoque_total)
            
        except Exception as e:
            logger.error(f"Erro ao calcular estoque total do produto {codprod}: {e}")
            return 0
    
    def consultar_multiplos_produtos(self, codprods: List[int]) -> Dict[int, int]:
        """
        Consulta estoque de múltiplos produtos de uma vez
        Otimizado para sincronização em lote
        """
        resultado = {}
        
        logger.info(f"Consultando estoque de {len(codprods)} produtos")
        
        for codprod in codprods:
            try:
                estoque = self.obter_estoque_total_produto(codprod)
                resultado[codprod] = estoque
                
            except Exception as e:
                logger.error(f"Erro no produto {codprod}: {e}")
                resultado[codprod] = 0
        
        sucessos = sum(1 for v in resultado.values() if v >= 0)
        logger.info(f"Consultados {sucessos}/{len(codprods)} produtos com sucesso")
        
        return resultado
