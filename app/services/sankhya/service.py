# app/services/sankhya/service.py
"""
Serviço principal Sankhya - Agregador de todos os serviços
Adaptado do seu código existente service.py
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import io
import tempfile
import os

# Dependências para DANFE (Necessário instalar brazilfiscalreport)
try:
    from brazilfiscalreport.danfe import Danfe, DanfeConfig
except ImportError:
    # Fallback para execução sem a biblioteca instalada
    logger = logging.getLogger(__name__)
    logger.warning("BrazilFiscalReport não encontrado. DANFE será simulado.")
    class Danfe:
        def __init__(self, xml, config=None): pass
        def output(self, path): pass
    class DanfeConfig:
        def __init__(self, logo=None): pass


from .auth import SankhyaAuth
from .estoque import EstoqueService
from .base import SankhyaClient

logger = logging.getLogger(__name__)

class SankhyaService:
    """
    Serviço principal para integração com Sankhya
    Agrega todos os sub-serviços
    """
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self._estoque_service = None
        
        if token:
            self._init_services()
        
        logger.info(f"SankhyaService inicializado com token: {'Sim' if token else 'Não'}")
    
    def _init_services(self):
        """Inicializa todos os sub-serviços"""
        try:
            self._estoque_service = EstoqueService(self.token)
            logger.debug("Serviços Sankhya inicializados")
        except Exception as e:
            logger.error(f"Erro ao inicializar serviços: {e}")
            raise
    
    @classmethod
    def with_auth(cls) -> 'SankhyaServiceContext':
        """
        Context manager para usar com autenticação automática
        """
        return SankhyaServiceContext()
    
    @property
    def estoque(self) -> EstoqueService:
        """Acesso ao serviço de estoque"""
        if not self._estoque_service:
            raise RuntimeError("Serviço não inicializado. Token requerido.")
        return self._estoque_service
    
    def authenticate(self, usuario: str = None, senha: str = None) -> str:
        """
        Autentica e inicializa serviços
        """
        try:
            auth = SankhyaAuth()
            self.token = auth.login(usuario, senha)
            self._init_services()
            
            logger.info("Autenticação realizada com sucesso")
            return self.token
            
        except Exception as e:
            logger.error(f"Erro na autenticação: {e}")
            raise
    
    def is_authenticated(self) -> bool:
        """Verifica se está autenticado"""
        return self.token is not None
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Testa conectividade com todos os serviços
        """
        if not self.is_authenticated():
            return {
                'sucesso': False,
                'erro': 'Não autenticado'
            }
        
        try:
            # Teste básico com consulta de estoque
            test_result = self.estoque.consultar_estoque_produto(1, somente_venda=True)
            
            return {
                'sucesso': True,
                'timestamp': datetime.utcnow().isoformat(),
                'servicos': {
                    'estoque': True,
                    'autenticacao': True
                },
                'teste_consulta': len(test_result) >= 0  # Pode ser 0 se não há estoque
            }
            
        except Exception as e:
            logger.error(f"Erro no teste de conexão: {e}")
            return {
                'sucesso': False,
                'erro': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def obter_estoque_produto(self, codprod: int, somente_venda: bool = True) -> Dict[str, Any]:
        """
        Obtém estoque de um produto com informações detalhadas
        """
        try:
            # Consulta detalhada
            estoques_detalhados = self.estoque.consultar_estoque_produto(codprod, somente_venda)
            
            # Estoque total
            estoque_total = sum(
                max(0, item['ESTOQUE'] - item['RESERVADO']) 
                for item in estoques_detalhados
            )
            
            return {
                'sucesso': True,
                'codprod': codprod,
                'estoque_total': int(estoque_total),
                'locais_disponiveis': len(estoques_detalhados),
                'detalhes_locais': estoques_detalhados,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estoque do produto {codprod}: {e}")
            return {
                'sucesso': False,
                'codprod': codprod,
                'erro': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def obter_estoque_multiplos_produtos(self, codprods: List[int]) -> Dict[str, Any]:
        """
        Obtém estoque de múltiplos produtos
        """
        try:
            logger.info(f"Consultando estoque de {len(codprods)} produtos")
            
            resultado = self.estoque.consultar_multiplos_produtos(codprods)
            
            # Estatísticas
            produtos_com_estoque = sum(1 for v in resultado.values() if v > 0)
            produtos_sem_estoque = len(resultado) - produtos_com_estoque
            
            return {
                'sucesso': True,
                'produtos_consultados': len(codprods),
                'produtos_com_estoque': produtos_com_estoque,
                'produtos_sem_estoque': produtos_sem_estoque,
                'estoques': resultado,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao consultar múltiplos produtos: {e}")
            return {
                'sucesso': False,
                'erro': str(e),
                'produtos_consultados': len(codprods),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def diagnosticar_produto(self, codprod: int) -> Dict[str, Any]:
        """
        Faz diagnóstico completo de um produto
        """
        try:
            logger.info(f"Diagnóstico completo do produto {codprod}")
            
            # Consulta locais de venda
            estoques_venda = self.estoque.consultar_estoque_produto(codprod, somente_venda=True)
            
            # Consulta todos os locais
            estoques_todos = self.estoque.consultar_estoque_produto(codprod, somente_venda=False)
            
            # Estoque total por tipo
            estoque_venda = sum(max(0, e['ESTOQUE'] - e['RESERVADO']) for e in estoques_venda)
            estoque_total = sum(max(0, e['ESTOQUE'] - e['RESERVADO']) for e in estoques_todos)
            
            # Local recomendado
            try:
                local_recomendado = self.estoque.obter_codlocalorig_produto(codprod)
            except Exception as e:
                local_recomendado = None
                erro_local = str(e)
            else:
                erro_local = None
            
            diagnostico = {
                'sucesso': True,
                'codprod': codprod,
                'estoque_venda': int(estoque_venda),
                'estoque_total': int(estoque_total),
                'locais_venda_disponiveis': len(estoques_venda),
                'locais_total_disponiveis': len(estoques_todos),
                'tem_estoque_venda': estoque_venda > 0,
                'tem_estoque_geral': estoque_total > 0,
                'local_recomendado': local_recomendado,
                'erro_local': erro_local,
                'detalhes_venda': estoques_venda,
                'detalhes_todos': estoques_todos,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Logs do diagnóstico
            logger.info(f"Diagnóstico produto {codprod}:")
            logger.info(f"  Estoque venda: {estoque_venda}")
            logger.info(f"  Estoque total: {estoque_total}")
            logger.info(f"  Local recomendado: {local_recomendado}")
            
            if erro_local:
                logger.warning(f"  Aviso: {erro_local}")
            
            return diagnostico
            
        except Exception as e:
            logger.error(f"Erro no diagnóstico do produto {codprod}: {e}")
            return {
                'sucesso': False,
                'codprod': codprod,
                'erro': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def obter_status_servicos(self) -> Dict[str, Any]:
        """
        Retorna status de todos os serviços
        """
        return {
            'autenticado': self.is_authenticated(),
            'token_presente': bool(self.token),
            'servicos_inicializados': {
                'estoque': self._estoque_service is not None
            },
            'timestamp': datetime.utcnow().isoformat()
        }

    def obter_nunota_por_id_woocommerce(self, id_woocommerce: int) -> Optional[int]:
        """
        Consulta NUNOTA pelo ID do Pedido do WooCommerce (campo AD_IDWOOCOMMERCE).
        Nota: Assumimos que o SankhyaClient tem o método load_records.
        """
        try:
            logger.info(f"Buscando NUNOTA para ID WooCommerce: {id_woocommerce}")
            
            # Criar um cliente base para usar load_records
            client = SankhyaClient(self.token)
            
            # Critério de busca no campo customizado (AD_IDWOOCOMMERCE)
            criteria = {
                "expression": {
                    "$": "this.AD_IDWOOCOMMERCE = ?"
                },
                "parameter": [
                    {
                        "type": "I", 
                        "$": str(id_woocommerce)
                    }
                ]
            }
            
            resultado = client.load_records(
                entity="CabecalhoNota",
                fields="NUNOTA",
                criteria=criteria,
                limit=1,
                offset_page=0
            )
            
            entities = resultado.get("responseBody", {}).get("entities", {})
            total = int(entities.get("total", "0"))
            
            if total > 0:
                entity = entities.get("entity")
                if isinstance(entity, list):
                    entity = entity[0]
                
                # Extrai o valor do campo NUNOTA (f0)
                nunota_str = entity.get('f0', {}).get('$', '')
                nunota = int(nunota_str)
                logger.info(f"NUNOTA {nunota} encontrado para ID WooCommerce {id_woocommerce}")
                return nunota
            
            logger.warning(f"Nenhuma NUNOTA encontrada para ID WooCommerce {id_woocommerce}")
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar NUNOTA por ID WooCommerce: {e}")
            return None

    def _obter_xml_nfe_por_nunota(self, nunota: int) -> str:
        """
        Consulta o XMLNFE na tabela CabecalhoNota (TGFCAB) usando NUNOTA.
        """
        client = SankhyaClient(self.token)
        
        criteria = {
            "expression": {"$": "this.NUNOTA = ?"},
            "parameter": [{"$": str(nunota), "type": "I"}]
        }
        
        resultado = client.load_records(
            entity="CabecalhoNota",
            fields="NUNOTA, XMLNFE, CHAVENFE",
            criteria=criteria,
            limit=1,
            offset_page=0
        )
        
        entities = resultado.get("responseBody", {}).get("entities", {})
        total = int(entities.get("total", "0"))
        
        if total > 0:
            entity = entities.get("entity")
            if isinstance(entity, list):
                entity = entity[0]
            
            # XMLNFE é o campo f1 (índice 1)
            xml_content = entity.get('f1', {}).get('$', '')
            
            if not xml_content:
                logger.warning(f"XMLNFE vazio encontrado para NUNOTA {nunota}")
                raise FileNotFoundError(f"XMLNFE não encontrado para NUNOTA {nunota} (pode não estar faturada)")
            
            return xml_content
        
        raise FileNotFoundError(f"NUNOTA {nunota} não encontrada no Sankhya.")

    def obter_danfe_pdf(self, nunota: int) -> bytes:
        """
        Gera o DANFE PDF a partir do XMLNFE do Sankhya
        VERSÃO MELHORADA com logs e validações
        """
        logger.info(f"[DANFE] Gerando PDF para NUNOTA={nunota}")

        try:
            # ETAPA 1: Obter XML do Sankhya
            logger.debug(f"[DANFE] Buscando XML no Sankhya...")
            xml_content = self._obter_xml_nfe_por_nunota(nunota)
            
            # Validações
            if not xml_content:
                raise FileNotFoundError(f"XML não disponível para NUNOTA {nunota}")
            
            if len(xml_content) < 100:
                raise ValueError(f"XML muito pequeno ({len(xml_content)} chars)")
            
            xml_limpo = xml_content.strip()
            if not xml_limpo.startswith('<?xml'):
                raise ValueError(f"Conteúdo não é XML válido. Início: {xml_limpo[:100]}")
            
            logger.info(f"[DANFE] XML obtido - {len(xml_content)} chars")
            logger.debug(f"[DANFE] Preview: {xml_content[:500]}")

            # ETAPA 2: Gerar PDF
            logger.debug(f"[DANFE] Iniciando geração com BrazilFiscalReport...")
            
            # Importar biblioteca (captura erro se não instalada)
            try:
                from brazilfiscalreport.danfe import Danfe
            except ImportError as e:
                logger.error(f"[DANFE] Biblioteca não instalada: {e}")
                raise ImportError(
                    "BrazilFiscalReport não encontrada. "
                    "Execute: pip install BrazilFiscalReport==0.4.1"
                )
            
            # Criar arquivo temporário
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                temp_pdf_path = tmp.name
                logger.debug(f"[DANFE] Arquivo temp: {temp_pdf_path}")
            
            try:
                # Gerar DANFE
                logger.debug("[DANFE] Renderizando PDF...")
                danfe = Danfe(xml=xml_content, config=None)
                danfe.output(temp_pdf_path)
                
                # Verificar se arquivo foi criado
                if not os.path.exists(temp_pdf_path):
                    raise RuntimeError(f"Arquivo PDF não foi criado")
                
                file_size = os.path.getsize(temp_pdf_path)
                if file_size == 0:
                    raise ValueError("PDF gerado está vazio")
                
                logger.info(f"[DANFE] PDF criado - {file_size} bytes")
                
            except Exception as e:
                # Limpar arquivo em caso de erro
                if os.path.exists(temp_pdf_path):
                    os.unlink(temp_pdf_path)
                raise RuntimeError(f"Erro ao gerar PDF: {str(e)}")

            # ETAPA 3: Ler arquivo em memória
            logger.debug(f"[DANFE] Lendo PDF...")
            try:
                with open(temp_pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
            except Exception as e:
                raise IOError(f"Erro ao ler PDF: {str(e)}")
            finally:
                # Sempre limpar arquivo temporário
                if os.path.exists(temp_pdf_path):
                    os.unlink(temp_pdf_path)
                    logger.debug(f"[DANFE] Arquivo temp removido")
            
            # Validação final
            if not pdf_bytes or len(pdf_bytes) == 0:
                raise ValueError("PDF resultou em conteúdo vazio")
            
            if not pdf_bytes.startswith(b'%PDF'):
                raise ValueError("Arquivo gerado não é um PDF válido")
            
            logger.info(f"[DANFE] SUCESSO - {len(pdf_bytes)} bytes")
            return pdf_bytes

        except FileNotFoundError as e:
            logger.error(f"[DANFE] NFe não encontrada: {e}")
            raise
        except (ValueError, ImportError, IOError, RuntimeError) as e:
            logger.error(f"[DANFE] Erro: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"[DANFE] Erro inesperado: {e}", exc_info=True)
            raise ValueError(f"Falha: {str(e)}")

    def obter_danfe_pdf_com_fallback(self, nunota: int) -> bytes:
        """
        Tenta múltiplas estratégias para gerar PDF
        """
        estrategias = [
            ("BrazilFiscalReport", self._gerar_com_brazilfiscal),
            ("erpbrasil.edoc.pdf", self._gerar_com_erpbrasil),
            ("nfelib", self._gerar_com_nfelib),
        ]
        
        erros = []
        
        for nome, funcao in estrategias:
            try:
                logger.info(f"Tentando gerar PDF com {nome}...")
                pdf_bytes = funcao(nunota)
                logger.info(f"PDF gerado com {nome} - {len(pdf_bytes)} bytes")
                return pdf_bytes
            except Exception as e:
                erro_msg = f"{nome}: {str(e)}"
                erros.append(erro_msg)
                logger.warning(f"Falhou: {erro_msg}")
                continue
        
        # Se todas falharam
        raise RuntimeError(f"Nenhuma estratégia funcionou. Erros: {'; '.join(erros)}")

    def _gerar_com_brazilfiscal(self, nunota: int) -> bytes:
        from brazilfiscalreport.danfe import Danfe
        xml = self._obter_xml_nfe_por_nunota(nunota)
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            danfe = Danfe(xml=xml, config=None)
            danfe.output(tmp.name)
            
            with open(tmp.name, 'rb') as f:
                pdf_bytes = f.read()
            os.unlink(tmp.name)
            
        return pdf_bytes

    def _gerar_com_erpbrasil(self, nunota: int) -> bytes:
        from erpbrasil.edoc.pdf import danfe
        xml = self._obter_xml_nfe_por_nunota(nunota)
        pdf_bytes = danfe.Danfe(xml).gerar_pdf()
        return pdf_bytes

    def _gerar_com_nfelib(self, nunota: int) -> bytes:
        from nfelib.nfe.bindings.v4_0.nfe_v4_00 import Nfe
        xml = self._obter_xml_nfe_por_nunota(nunota)
        nfe = Nfe.from_xml(xml)
        pdf_bytes = nfe.to_pdf()
        return pdf_bytes

class SankhyaServiceContext:
    """
    Context manager para SankhyaService com autenticação automática
    """
    
    def __init__(self):
        self.auth = None
        self.service = None
        self.token = None
    
    def __enter__(self) -> SankhyaService:
        try:
            logger.info("Iniciando autenticação Sankhya...")
            
            self.auth = SankhyaAuth()
            self.token = self.auth.login()
            
            if not self.token:
                raise Exception("Falha na autenticação com Sankhya")
            
            logger.info("Autenticação realizada com sucesso")
            
            # Cria instância do serviço com token
            self.service = SankhyaService(self.token)
            
            logger.info("Serviços Sankhya inicializados")
            return self.service
            
        except Exception as e:
            logger.error(f"Erro na inicialização: {e}")
            if self.auth and self.token:
                try:
                    self.auth.logout()
                except:
                    pass
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.auth and self.token:
                logger.info("Realizando logout...")
                self.auth.logout()
                logger.info("Logout realizado com sucesso")
        except Exception as e:
            logger.warning(f"Erro no logout: {e}")
        finally:
            # Limpa referências
            self.service = None
            self.token = None
            self.auth = None
        
        # Se houve exceção, re-levanta
        if exc_type:
            logger.error(f"Erro durante execução: {exc_val}")
            return False
        
        return True


