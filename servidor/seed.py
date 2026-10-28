"""
Cria o usuario admin e alguns colaboradores de exemplo.
Rode uma vez:  python seed.py
"""
from werkzeug.security import generate_password_hash

import config
from app import create_app
from db import get_db

COLABORADORES = [
    # nome, matricula, tag_rfid, cargo, acesso_sala, ativo
    ("Luiz Eduardo Tremea", "1001", "111111111111", "Desenvolvedor", 1, 1),
    ("Bruno Benetti",       "1002", "222222222222", "Artista 3D",    1, 1),
    ("Patrick M.",          "1003", "333333333333", "Estagiario",    0, 1),
    ("Ana Souza",           "1004", "444444444444", "Financeiro",    0, 1),
    ("Carlos Lima",         "1005", None,           "Suporte",       0, 0),
]

app = create_app()
with app.app_context():
    db = get_db()
    # Cria o admin ou redefine a senha dele para a do config.py
    db.execute(
        "INSERT INTO usuarios (usuario, senha_hash) VALUES (?, ?) "
        "ON CONFLICT(usuario) DO UPDATE SET senha_hash = excluded.senha_hash",
        (config.ADMIN_USUARIO, generate_password_hash(config.ADMIN_SENHA)),
    )
    for c in COLABORADORES:
        db.execute(
            "INSERT OR IGNORE INTO colaboradores "
            "(nome, matricula, tag_rfid, cargo, acesso_sala, ativo) VALUES (?, ?, ?, ?, ?, ?)",
            c,
        )
    db.commit()
    print(f"Usuario '{config.ADMIN_USUARIO}' (senha '{config.ADMIN_SENHA}') e "
          f"{len(COLABORADORES)} colaboradores de exemplo criados.")
