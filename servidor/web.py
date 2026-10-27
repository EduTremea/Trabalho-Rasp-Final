"""
Painel web: login, gerenciamento de colaboradores, logs e monitoramento.
"""
import sqlite3
from functools import wraps

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash

from db import get_db

bp_web = Blueprint("web", __name__)

TIPOS = ["entrada", "saida", "acesso_negado", "invasao", "movimento_sem_cracha", "campainha"]


def exige_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("usuario"):
            return redirect(url_for("web.login", proximo=request.path))
        return f(*args, **kwargs)
    return wrapper


# ---------- Autenticacao ----------

@bp_web.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = get_db().execute(
            "SELECT * FROM usuarios WHERE usuario = ?", (request.form["usuario"],)
        ).fetchone()
        if u and check_password_hash(u["senha_hash"], request.form["senha"]):
            session["usuario"] = u["usuario"]
            return redirect(request.args.get("proximo") or url_for("web.monitoramento"))
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")


@bp_web.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("web.login"))


# ---------- Colaboradores ----------

@bp_web.get("/colaboradores")
@exige_login
def colaboradores():
    lista = get_db().execute("SELECT * FROM colaboradores ORDER BY nome").fetchall()
    return render_template("colaboradores.html", colaboradores=lista)


def _form_colaborador():
    f = request.form
    return {
        "nome": f["nome"].strip(),
        "matricula": f["matricula"].strip(),
        "tag_rfid": f["tag_rfid"].strip() or None,
        "cargo": f["cargo"].strip(),
        "acesso_sala": 1 if f.get("acesso_sala") else 0,
        "ativo": 1 if f.get("ativo") else 0,
    }


@bp_web.route("/colaboradores/novo", methods=["GET", "POST"])
@exige_login
def colaborador_novo():
    if request.method == "POST":
        d = _form_colaborador()
        try:
            get_db().execute(
                "INSERT INTO colaboradores (nome, matricula, tag_rfid, cargo, acesso_sala, ativo) "
                "VALUES (:nome, :matricula, :tag_rfid, :cargo, :acesso_sala, :ativo)", d)
            get_db().commit()
            flash(f"Colaborador {d['nome']} cadastrado.", "ok")
            return redirect(url_for("web.colaboradores"))
        except sqlite3.IntegrityError:
            flash("Matrícula ou tag RFID já cadastrada.", "erro")
    return render_template("colaborador_form.html", c=None)


@bp_web.route("/colaboradores/<int:cid>/editar", methods=["GET", "POST"])
@exige_login
def colaborador_editar(cid):
    db = get_db()
    c = db.execute("SELECT * FROM colaboradores WHERE id = ?", (cid,)).fetchone()
    if c is None:
        flash("Colaborador não encontrado.", "erro")
        return redirect(url_for("web.colaboradores"))
    if request.method == "POST":
        d = _form_colaborador()
        d["id"] = cid
        try:
            db.execute(
                "UPDATE colaboradores SET nome=:nome, matricula=:matricula, tag_rfid=:tag_rfid, "
                "cargo=:cargo, acesso_sala=:acesso_sala, ativo=:ativo WHERE id=:id", d)
            db.commit()
            flash("Dados atualizados.", "ok")
            return redirect(url_for("web.colaboradores"))
        except sqlite3.IntegrityError:
            flash("Matrícula ou tag RFID já cadastrada em outro colaborador.", "erro")
    return render_template("colaborador_form.html", c=c)


@bp_web.post("/colaboradores/<int:cid>/excluir")
@exige_login
def colaborador_excluir(cid):
    db = get_db()
    db.execute("DELETE FROM colaboradores WHERE id = ?", (cid,))
    db.commit()
    flash("Colaborador excluído. Os logs dele foram mantidos.", "ok")
    return redirect(url_for("web.colaboradores"))


# ---------- Logs ----------

@bp_web.get("/logs")
@exige_login
def logs():
    data = request.args.get("data", "")
    tipo = request.args.get("tipo", "")
    sql, params = "SELECT * FROM eventos WHERE 1=1", []
    if data:
        sql += " AND date(data_hora) = ?"
        params.append(data)
    if tipo:
        sql += " AND tipo = ?"
        params.append(tipo)
    sql += " ORDER BY data_hora DESC LIMIT 500"
    eventos = get_db().execute(sql, params).fetchall()
    return render_template("logs.html", eventos=eventos, data=data, tipo=tipo, tipos=TIPOS)


# ---------- Monitoramento ----------

@bp_web.get("/monitoramento")
@exige_login
def monitoramento():
    return render_template("monitoramento.html")
