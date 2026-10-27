import sqlite3
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario    TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS colaboradores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT NOT NULL,
    matricula   TEXT UNIQUE NOT NULL,
    tag_rfid    TEXT UNIQUE,              -- pode ficar vazio ate o cracha ser cadastrado
    cargo       TEXT,
    acesso_sala INTEGER NOT NULL DEFAULT 0, -- 1 = pode entrar na sala do projeto
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT DEFAULT (datetime('now', 'localtime'))
);

-- Cada leitura/alerta vira uma linha aqui. E a "versao unica da verdade".
CREATE TABLE IF NOT EXISTS eventos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora        TEXT NOT NULL,          -- momento em que aconteceu na Raspberry
    tipo             TEXT NOT NULL,          -- entrada | saida | acesso_negado | invasao | movimento_sem_cracha | campainha
    tag_rfid         TEXT,
    colaborador_id   INTEGER,
    nome             TEXT,
    duracao_segundos INTEGER,               -- preenchido nas saidas
    origem           TEXT DEFAULT 'raspberry', -- raspberry | offline (sincronizado depois) | simulador
    detalhe          TEXT,
    recebido_em      TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE (data_hora, tipo, tag_rfid),     -- evita duplicar ao resincronizar a fila offline
    FOREIGN KEY (colaborador_id) REFERENCES colaboradores (id) ON DELETE SET NULL
);

-- Estado do dispositivo fisico (uma linha so)
CREATE TABLE IF NOT EXISTS dispositivo (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    ultimo_contato TEXT,
    ip             TEXT,
    luz            TEXT,                    -- 'clara' | 'escura' | NULL (sem sensor)
    eventos_pendentes INTEGER DEFAULT 0
);
INSERT OR IGNORE INTO dispositivo (id) VALUES (1);

CREATE INDEX IF NOT EXISTS idx_eventos_data ON eventos (data_hora);
CREATE INDEX IF NOT EXISTS idx_eventos_tipo ON eventos (tipo);
"""


def get_db():
    """Uma conexao por requisicao, guardada no contexto do Flask."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
