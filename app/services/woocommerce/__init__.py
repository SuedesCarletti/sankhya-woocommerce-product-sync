# app/services/woocommerce/__init__.py
"""
Serviços de integração com WooCommerce
"""

from .client import WooCommerceClient
from .products import ProductsService

__all__ = ['WooCommerceClient', 'ProductsService']