# Sankhya ↔ WooCommerce Sync

Intermediador Python para sincronização de estoque em tempo real entre Sankhya ERP e WooCommerce.

## Funcionalidades

- **Sincronização em tempo real** via webhooks do Sankhya
- **API REST** completa para integração com WordPress
- **Sincronização em lote** de múltiplos produtos  
- **Health checks** para monitoramento
- **Logs estruturados** para auditoria
- **Autenticação segura** com tokens
- **Docker** para deploy fácil

## Instalação

### Desenvolvimento Local

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/sankhya-woocommerce-sync.git
cd sankhya-woocommerce-sync

# Instale dependências
pip install -r requirements.txt

# Configure variáveis
cp .env.example .env
# Edite .env com suas credenciais

# Execute
python app/main.py