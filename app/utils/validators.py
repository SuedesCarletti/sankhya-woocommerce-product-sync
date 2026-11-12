# app/utils/validators.py
"""
Funções de validação
"""

import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

def validate_cpf(cpf: str) -> bool:
    """
    Valida CPF brasileiro
    """
    if not cpf:
        return False
    
    # Remove formatação
    cpf = re.sub(r'\D', '', cpf)
    
    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        return False
    
    # Verifica se não são todos dígitos iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Calcula primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    primeiro_digito = 11 - (soma % 11)
    if primeiro_digito >= 10:
        primeiro_digito = 0
    
    if int(cpf[9]) != primeiro_digito:
        return False
    
    # Calcula segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    segundo_digito = 11 - (soma % 11)
    if segundo_digito >= 10:
        segundo_digito = 0
    
    if int(cpf[10]) != segundo_digito:
        return False
    
    return True

def validate_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ brasileiro
    """
    if not cnpj:
        return False
    
    # Remove formatação
    cnpj = re.sub(r'\D', '', cnpj)
    
    # Verifica se tem 14 dígitos
    if len(cnpj) != 14:
        return False
    
    # Verifica se não são todos dígitos iguais
    if cnpj == cnpj[0] * 14:
        return False
    
    # Cálculo do primeiro dígito verificador
    peso = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * peso[i] for i in range(12))
    primeiro_digito = 11 - (soma % 11)
    if primeiro_digito >= 10:
        primeiro_digito = 0
    
    if int(cnpj[12]) != primeiro_digito:
        return False
    
    # Cálculo do segundo dígito verificador
    peso = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * peso[i] for i in range(13))
    segundo_digito = 11 - (soma % 11)
    if segundo_digito >= 10:
        segundo_digito = 0
    
    if int(cnpj[13]) != segundo_digito:
        return False
    
    return True

def validate_document(document: str) -> Dict[str, Any]:
    """
    Valida documento (CPF ou CNPJ) e retorna informações
    """
    if not document:
        return {
            'valid': False,
            'type': None,
            'error': 'Documento não informado'
        }
    
    # Remove formatação
    clean_doc = re.sub(r'\D', '', document)
    
    if len(clean_doc) == 11:
        # CPF
        is_valid = validate_cpf(clean_doc)
        return {
            'valid': is_valid,
            'type': 'cpf',
            'document': clean_doc,
            'formatted': f"{clean_doc[:3]}.{clean_doc[3:6]}.{clean_doc[6:9]}-{clean_doc[9:]}",
            'error': None if is_valid else 'CPF inválido'
        }
    
    elif len(clean_doc) == 14:
        # CNPJ
        is_valid = validate_cnpj(clean_doc)
        return {
            'valid': is_valid,
            'type': 'cnpj',
            'document': clean_doc,
            'formatted': f"{clean_doc[:2]}.{clean_doc[2:5]}.{clean_doc[5:8]}/{clean_doc[8:12]}-{clean_doc[12:]}",
            'error': None if is_valid else 'CNPJ inválido'
        }
    
    else:
        return {
            'valid': False,
            'type': None,
            'document': clean_doc,
            'error': f'Documento deve ter 11 (CPF) ou 14 (CNPJ) dígitos. Recebido: {len(clean_doc)}'
        }

def validate_codprod(codprod: Any) -> Dict[str, Any]:
    """
    Valida código de produto
    """
    if codprod is None:
        return {
            'valid': False,
            'error': 'Código de produto não informado'
        }
    
    try:
        codprod_int = int(codprod)
        
        if codprod_int <= 0:
            return {
                'valid': False,
                'error': 'Código de produto deve ser maior que zero'
            }
        
        return {
            'valid': True,
            'codprod': codprod_int
        }
        
    except (ValueError, TypeError):
        return {
            'valid': False,
            'error': f'Código de produto inválido: {codprod}'
        }

def validate_stock_quantity(quantity: Any) -> Dict[str, Any]:
    """
    Valida quantidade de estoque
    """
    if quantity is None:
        return {
            'valid': False,
            'error': 'Quantidade não informada'
        }
    
    try:
        quantity_int = int(quantity)
        
        if quantity_int < 0:
            return {
                'valid': False,
                'error': 'Quantidade não pode ser negativa'
            }
        
        return {
            'valid': True,
            'quantity': quantity_int
        }
        
    except (ValueError, TypeError):
        return {
            'valid': False,
            'error': f'Quantidade inválida: {quantity}'
        }

def validate_email(email: str) -> bool:
    """
    Valida formato de email
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> Dict[str, Any]:
    """
    Valida telefone brasileiro
    """
    if not phone:
        return {
            'valid': False,
            'error': 'Telefone não informado'
        }
    
    # Remove formatação
    clean_phone = re.sub(r'\D', '', phone)
    
    # Verifica tamanho (10 ou 11 dígitos)
    if len(clean_phone) not in [10, 11]:
        return {
            'valid': False,
            'error': f'Telefone deve ter 10 ou 11 dígitos. Recebido: {len(clean_phone)}'
        }
    
    # Verifica se começa com código de área válido
    if len(clean_phone) >= 2:
        area_code = int(clean_phone[:2])
        if area_code < 11 or area_code > 99:
            return {
                'valid': False,
                'error': f'Código de área inválido: {area_code}'
            }
    
    return {
        'valid': True,
        'phone': clean_phone,
        'formatted': format_phone(clean_phone)
    }

def format_phone(phone: str) -> str:
    """
    Formata telefone brasileiro
    """
    clean_phone = re.sub(r'\D', '', phone)
    
    if len(clean_phone) == 10:
        # Formato: (11) 1234-5678
        return f"({clean_phone[:2]}) {clean_phone[2:6]}-{clean_phone[6:]}"
    elif len(clean_phone) == 11:
        # Formato: (11) 91234-5678
        return f"({clean_phone[:2]}) {clean_phone[2:7]}-{clean_phone[7:]}"
    else:
        return clean_phone

def validate_webhook_payload(payload: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
    """
    Valida payload de webhook
    """
    if not isinstance(payload, dict):
        return {
            'valid': False,
            'error': 'Payload deve ser um objeto JSON'
        }
    
    missing_fields = []
    for field in required_fields:
        if field not in payload:
            missing_fields.append(field)
    
    if missing_fields:
        return {
            'valid': False,
            'error': f'Campos obrigatórios faltando: {", ".join(missing_fields)}'
        }
    
    return {
        'valid': True
    }

def validate_sync_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida requisição de sincronização
    """
    errors = []
    
    # Validar produtos se presente
    if 'produtos' in data:
        produtos = data['produtos']
        
        if not isinstance(produtos, list):
            errors.append('Campo "produtos" deve ser uma lista')
        else:
            for i, produto in enumerate(produtos):
                if not isinstance(produto, dict):
                    errors.append(f'Produto {i} deve ser um objeto')
                    continue
                
                # Validar codprod_sankhya
                if 'codprod_sankhya' not in produto:
                    errors.append(f'Produto {i}: campo "codprod_sankhya" obrigatório')
                else:
                    codprod_validation = validate_codprod(produto['codprod_sankhya'])
                    if not codprod_validation['valid']:
                        errors.append(f'Produto {i}: {codprod_validation["error"]}')
                
                # Validar product_id_wc ou sku_wc
                if 'product_id_wc' not in produto and 'sku_wc' not in produto:
                    errors.append(f'Produto {i}: deve ter "product_id_wc" ou "sku_wc"')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }

def sanitize_string(text: str, max_length: int = None) -> str:
    """
    Sanitiza string removendo caracteres perigosos
    """
    if not text:
        return ""
    
    # Remove caracteres de controle
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', str(text))
    
    # Remove espaços extras
    sanitized = ' '.join(sanitized.split())
    
    # Limita tamanho se especificado
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length].strip()
    
    return sanitized

def validate_url(url: str) -> bool:
    """
    Valida formato de URL
    """
    if not url:
        return False
    
    pattern = r'^https?:\/\/[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(\/.*)?$'
    return bool(re.match(pattern, url))