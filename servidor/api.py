"""
API usada pela Raspberry (e pelo notebook Pandas).

GET  /api/sync          -> cadastro completo para o cache local da Rasp
POST /api/eventos       -> recebe 1 evento ou uma lista (fila offline)
POST /api/heartbeat     -> "estou vivo" + estado dos sensores
GET  /api/status        -> resumo para a pagina de monitoramento
GET  /api/eventos       -> logs em JSON (filtros ?data=AAAA-MM-DD&tipo=)
GET  /api/eventos.csv   -> logs em CSV para o Pandas
"""
import csv
import io
import sqlite3
from datetime import datetime, date
from functools import wraps

from flask import Blueprint, Response, current_app, jsonify, request

from db import get_db

bp_api = Blueprint("api", __name__, url_prefix="/api")

TIPOS_VALIDOS = {"entrada", "saida", "acesso_negado", "invasao",
                 "movimento_sem_cracha", "campainha"}


# ---------- Autenticacao simples por chave ----------

def exige_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.headers.get("X-Api-Key") != current_app.config["API_KEY"]:
            return jsonify({"erro": "chave de API invalida"}), 401
        return f(*args, **kwargs)
    return wrapper


# ---------- Consultas reutilizadas ----------

def colaboradores_ativos(db):
    return db.execute(
        "SELECT id, nome, matricula, tag_rfid, cargo, acesso_sala, ativo "
        "FROM colaboradores WHERE ativo = 1 AND tag_rfid IS NOT NULL ORDER BY nome"
    ).fetchall()


def dentro_da_sala(db, dia=None):
    """Quem esta na sala agora: ultimo evento entrada/saida de cada colaborador no dia.

    Retorna lista de dicts com nome, tag e horario de entrada."""
    dia = dia or date.today().isoformat()
    linhas = db.execute(
        """
        SELECT e.colaborador_id, e.nome, e.tag_rfid, e.tipo, e.data_hora
        FROM eventos e
        JOIN (
            SELECT colaborador_id, MAX(data_hora) AS ultimo
            FROM eventos
            WHERE tipo IN ('entrada', 'saida') AND date(data_hora) = ?
              AND colaborador_id IS NOT NULL
            GROUP BY colaborador_id
        ) u ON u.colaborador_id = e.colaborador_id AND u.ultimo = e.data_hora
        WHERE e.tipo = 'entrada'
        ORDER BY e.data_hora
        """,
        (dia,),
    ).fetchall()
    return [dict(l) for l in linhas]


def entraram_hoje(db, dia=None):
    dia = dia or date.today().isoformat()
    linhas = db.execute(
        "SELECT DISTINCT tag_rfid FROM eventos "
        "WHERE tipo = 'entrada' AND date(data_hora) = ? AND tag_rfid IS NOT NULL",
        (dia,),
    ).fetchall()
    return [l["tag_rfid"] for l in linhas]


def ultimos(db, tipos, limite=8):
    marcadores = ",".join("?" * len(tipos))
    linhas = db.execute(
        f"SELECT id, data_hora, tipo, tag_rfid, nome, duracao_segundos, origem, detalhe "
        f"FROM eventos WHERE tipo IN ({marcadores}) ORDER BY data_hora DESC LIMIT ?",
        (*tipos, limite),
    ).fetchall()
    return [dict(l) for l in linhas]


# ---------- Rotas ----------

@bp_api.get("/sync")
@exige_api_key
def sync():
    db = get_db()
    return jsonify({
        "servidor_hora": datetime.now().isoformat(timespec="seconds"),
        "colaboradores": [dict(c) for c in colaboradores_ativos(db)],
        "dentro_da_sala": [d["tag_rfid"] for d in dentro_da_sala(db)],
        "entraram_hoje": entraram_hoje(db),
    })


@bp_api.post("/eventos")
@exige_api_key
def receber_eventos():
    dados = request.get_json(silent=True)
    if dados is None:
        return jsonify({"erro": "JSON invalido"}), 400
    lista = dados if isinstance(dados, list) else [dados]

    db = get_db()
    aceitos, duplicados, rejeitados = 0, 0, []
    for ev in lista:
        tipo = ev.get("tipo")
        if tipo not in TIPOS_VALIDOS or not ev.get("data_hora"):
            rejeitados.append(ev)
            continue
        tag = str(ev["tag_rfid"]) if ev.get("tag_rfid") not in (None, "") else None
        colab = None
        if tag:
            colab = db.execute(
                "SELECT id, nome FROM colaboradores WHERE tag_rfid = ?", (tag,)
            ).fetchone()
        try:
            db.execute(
                "INSERT INTO eventos (data_hora, tipo, tag_rfid, colaborador_id, nome, "
                "duracao_segundos, origem, detalhe) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ev["data_hora"], tipo, tag,
                    colab["id"] if colab else None,
                    ev.get("nome") or (colab["nome"] if colab else None),
                    ev.get("duracao_segundos"),
                    ev.get("origem", "raspberry"),
                    ev.get("detalhe"),
                ),
            )
            aceitos += 1
        except sqlite3.IntegrityError:
            duplicados += 1  # ja tinha sido recebido antes (resync da fila offline)
    db.commit()
    return jsonify({"aceitos": aceitos, "duplicados": duplicados,
                    "rejeitados": len(rejeitados)}), 201


@bp_api.post("/heartbeat")
@exige_api_key
def heartbeat():
    dados = request.get_json(silent=True) or {}
    db = get_db()
    db.execute(
        "UPDATE dispositivo SET ultimo_contato = ?, ip = ?, luz = ?, eventos_pendentes = ? WHERE id = 1",
        (datetime.now().isoformat(timespec="seconds"), request.remote_addr,
         dados.get("luz"), int(dados.get("eventos_pendentes", 0))),
    )
    db.commit()
    return jsonify({"ok": True, "servidor_hora": datetime.now().isoformat(timespec="seconds")})


@bp_api.get("/status")
def status():
    """Sem chave: e consumido pela pagina de monitoramento (que ja exige login)."""
    db = get_db()
    disp = dict(db.execute("SELECT * FROM dispositivo WHERE id = 1").fetchone())
    online = False
    if disp["ultimo_contato"]:
        delta = datetime.now() - datetime.fromisoformat(disp["ultimo_contato"])
        online = delta.total_seconds() < current_app.config["TIMEOUT_DISPOSITIVO"]
    disp["online"] = online

    hoje = date.today().isoformat()
    totais = {
        r["tipo"]: r["qtd"]
        for r in db.execute(
            "SELECT tipo, COUNT(*) AS qtd FROM eventos WHERE date(data_hora) = ? GROUP BY tipo",
            (hoje,),
        )
    }
    return jsonify({
        "agora": datetime.now().isoformat(timespec="seconds"),
        "dispositivo": disp,
        "dentro_da_sala": dentro_da_sala(db),
        "ultimas_entradas": ultimos(db, ["entrada"]),
        "ultimas_saidas": ultimos(db, ["saida"]),
        "acessos_negados": ultimos(db, ["acesso_negado"]),
        "invasoes": ultimos(db, ["invasao"]),
        "alertas": ultimos(db, ["invasao", "acesso_negado", "movimento_sem_cracha", "campainha"], 12),
        "totais_hoje": totais,
    })


def _consulta_eventos(db):
    sql = "SELECT * FROM eventos WHERE 1=1"
    params = []
    if request.args.get("data"):
        sql += " AND date(data_hora) = ?"
        params.append(request.args["data"])
    if request.args.get("tipo"):
        sql += " AND tipo = ?"
        params.append(request.args["tipo"])
    sql += " ORDER BY data_hora"
    return db.execute(sql, params).fetchall()


@bp_api.get("/eventos")
def listar_eventos():
    return jsonify([dict(l) for l in _consulta_eventos(get_db())])


@bp_api.get("/eventos.csv")
def exportar_csv():
    linhas = _consulta_eventos(get_db())
    saida = io.StringIO()
    campos = ["id", "data_hora", "tipo", "tag_rfid", "colaborador_id", "nome",
              "duracao_segundos", "origem", "detalhe", "recebido_em"]
    w = csv.DictWriter(saida, fieldnames=campos, extrasaction="ignore")
    w.writeheader()
    for l in linhas:
        w.writerow(dict(l))
    return Response(
        saida.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=acessos.csv"},
    )
