# API.md
# Documentação da API - Sankhya WooCommerce Sync

## Visão Geral

Esta API permite sincronização de estoque entre Sankhya ERP e WooCommerce através de endpoints REST e webhooks.

**Base URL:** `https://seu-intermediador.railway.app`

## Autenticação

### APIs REST
Todas as APIs requerem autenticação via Bearer token:

```bash
Authorization: Bearer seu-api-token