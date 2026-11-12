# wsgi.py
"""
WSGI entry point for Railway deployment
"""

import os
import sys

# Adicionar o diretório raiz ao Python path (não apenas app)
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Adicionar também o diretório app para imports relativos (fallback)
app_dir = os.path.join(project_root, 'app')
sys.path.insert(0, app_dir)

try:
    from app.main import create_app
    
    # Criar aplicação
    application = create_app()
    
    # Log de inicialização
    print("Sankhya-WooCommerce Sync iniciado no Railway!")
    print(f"Project root: {project_root}")
    print(f"App dir: {app_dir}")
    print(f"Python path: {sys.path[:3]}...")
    
    if __name__ == "__main__":
        port = int(os.environ.get('PORT', 5000))
        application.run(host='0.0.0.0', port=port, debug=False)
        
except Exception as e:
    print(f"Erro ao importar aplicação: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
