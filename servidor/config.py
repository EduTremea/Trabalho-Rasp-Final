import os

# Caminho do banco SQLite (fica na pasta servidor/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "sala_segura.db")

# Chave da sessao do Flask (troque em producao)
SECRET_KEY = os.environ.get("SALA_SECRET_KEY", "troque-esta-chave")

# Chave que a Raspberry envia no cabecalho X-Api-Key
API_KEY = os.environ.get("SALA_API_KEY", "rasp-sala-2026")

# Usuario do painel, criado automaticamente ao subir o servidor
ADMIN_USUARIO = "admin"
ADMIN_SENHA = "admin"

# Tempo (segundos) sem heartbeat para considerar a Raspberry offline
TIMEOUT_DISPOSITIVO = 30
