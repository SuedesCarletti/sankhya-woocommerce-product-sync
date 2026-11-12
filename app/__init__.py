# app/__init__.py
"""
Sankhya-WooCommerce Sync
Intermediador para sincronização de estoque em tempo real
"""

__version__ = "1.0.0"
__author__ = "Sua Empresa"
__description__ = "Intermediador Sankhya ↔ WooCommerce"

from .main import create_app

__all__ = ['create_app']