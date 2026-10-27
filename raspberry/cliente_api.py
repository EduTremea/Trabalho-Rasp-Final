"""
Conversa com o servidor Flask e cuida da operacao sem rede:
- cache do cadastro em arquivo (cache_colaboradores.json)
- fila de eventos que nao conseguiram ser enviados (fila_offline.json)
- reenvio da fila quando a conexao volta
"""
import json
import os
import socket
import time

import requests

import config

CABECALHOS = {"X-Api-Key": config.API_KEY, "Content-Type": "application/json"}


def _ler_json(caminho, padrao):
    if os.path.exists(caminho):
        try:
            with open(caminho, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return padrao


def _gravar_json(caminho, dados):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)  # troca atomica: nao corrompe se faltar energia no meio


class ClienteAPI:
    def __init__(self):
        self.online = False
        self.colaboradores = {}     # tag -> dict
        self.fila = _ler_json(config.ARQ_FILA, [])
        cache = _ler_json(config.ARQ_CACHE, None)
        if cache:
            self._carregar_cadastro(cache)
            print(f"[CACHE] {len(self.colaboradores)} colaboradores carregados do arquivo local")
        self.dentro_servidor = set(cache.get("dentro_da_sala", [])) if cache else set()
        self.entraram_hoje_servidor = set(cache.get("entraram_hoje", [])) if cache else set()

    def _carregar_cadastro(self, dados):
        self.colaboradores = {
            str(c["tag_rfid"]): c for c in dados.get("colaboradores", []) if c.get("tag_rfid")
        }

    # ---------- Sincronizacao do cadastro ----------

    def sincronizar(self):
        """Busca o cadastro no servidor. Devolve True se conseguiu."""
        try:
            r = requests.get(f"{config.SERVIDOR_URL}/api/sync",
                             headers=CABECALHOS, timeout=config.TIMEOUT_HTTP)
            r.raise_for_status()
        except (requests.RequestException, socket.error) as e:
            self._marcar_offline(e)
            return False
        dados = r.json()
        self._carregar_cadastro(dados)
        self.dentro_servidor = set(dados.get("dentro_da_sala", []))
        self.entraram_hoje_servidor = set(dados.get("entraram_hoje", []))
        _gravar_json(config.ARQ_CACHE, dados)
        self._marcar_online()
        print(f"[SYNC] cadastro atualizado: {len(self.colaboradores)} colaboradores com tag")
        self.enviar_fila()
        return True

    # ---------- Envio de eventos ----------

    def enviar(self, evento):
        """Tenta mandar na hora; se falhar, guarda na fila e segue a vida."""
        if self.online and self._post([evento]):
            return True
        evento["origem"] = "offline"
        self.fila.append(evento)
        _gravar_json(config.ARQ_FILA, self.fila)
        print(f"[FILA] sem conexao, evento guardado ({len(self.fila)} pendente(s))")
        return False

    def enviar_fila(self):
        if not self.fila:
            return
        if self._post(self.fila):
            print(f"[FILA] {len(self.fila)} evento(s) sincronizado(s) com o servidor")
            self.fila = []
            _gravar_json(config.ARQ_FILA, self.fila)

    def _post(self, eventos):
        try:
            r = requests.post(f"{config.SERVIDOR_URL}/api/eventos", json=eventos,
                              headers=CABECALHOS, timeout=config.TIMEOUT_HTTP)
            r.raise_for_status()
            self._marcar_online()
            return True
        except (requests.RequestException, socket.error) as e:
            self._marcar_offline(e)
            return False

    # ---------- Heartbeat ----------

    def heartbeat(self, luz=None):
        try:
            r = requests.post(f"{config.SERVIDOR_URL}/api/heartbeat",
                              json={"luz": luz, "eventos_pendentes": len(self.fila)},
                              headers=CABECALHOS, timeout=config.TIMEOUT_HTTP)
            r.raise_for_status()
            voltou = not self.online
            self._marcar_online()
            if voltou:
                self.enviar_fila()
            return True
        except (requests.RequestException, socket.error) as e:
            self._marcar_offline(e)
            return False

    # ---------- Estado da conexao ----------

    def _marcar_online(self):
        if not self.online:
            print("[REDE] conexao com o servidor OK")
        self.online = True

    def _marcar_offline(self, erro):
        if self.online:
            print(f"[REDE] servidor inacessivel ({type(erro).__name__}); operando com cache local")
        self.online = False
