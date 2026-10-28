"""
Aplicacao embarcada da Sala Segura (Raspberry Pi + MFRC522).

Uso:
    python main.py            # com hardware
    python main.py --simular  # sem hardware: digite o ID da tag no terminal

Fluxo de cada leitura:
    tag desconhecida            -> invasao        (sirene + vermelho piscando)
    cadastrado sem acesso       -> acesso_negado  (bipe grave + vermelho)
    autorizado, fora da sala    -> entrada        (bipes agudos + verde + porta)
    autorizado, dentro da sala  -> saida          (idem, mostra tempo de permanencia)
"""
import json
import os
import time
from datetime import datetime, date

import config
import hardware
from cliente_api import ClienteAPI


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


def fmt(seg):
    seg = int(seg)
    return f"{seg // 3600:02d}:{seg % 3600 // 60:02d}:{seg % 60:02d}"


class SalaSegura:
    def __init__(self):
        self.hw = hardware.criar()
        self.api = ClienteAPI()

        # Estado local (sobrevive a reinicio da Rasp)
        est = self._ler_estado()
        self.dentro = est.get("dentro", {})          # tag -> iso da entrada
        self.entrou_hoje = set(est.get("entrou_hoje", {}).get(date.today().isoformat(), []))
        self.tempo_hoje = est.get("tempo_hoje", {}).get(date.today().isoformat(), {})  # nome -> seg

        self.ultima_leitura = {}       # tag -> timestamp (anti-repeticao)
        self.ultima_leitura_geral = 0
        self.ultimo_alerta_pir = 0
        self.t_heartbeat = 0
        self.t_sync = 0

    # ---------- Persistencia ----------

    def _ler_estado(self):
        if os.path.exists(config.ARQ_ESTADO):
            try:
                with open(config.ARQ_ESTADO, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _salvar_estado(self):
        hoje = date.today().isoformat()
        dados = {
            "dentro": self.dentro,
            "entrou_hoje": {hoje: sorted(self.entrou_hoje)},
            "tempo_hoje": {hoje: self.tempo_hoje},
        }
        tmp = config.ARQ_ESTADO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=1)
        os.replace(tmp, config.ARQ_ESTADO)

    # ---------- Inicializacao ----------

    def iniciar(self):
        self.hw.lcd("Sala Segura", "iniciando...")
        self.t_sync = self.t_heartbeat = time.time()
        if self.api.sincronizar():
            # O servidor e a fonte da verdade sobre quem ja entrou hoje
            self.entrou_hoje |= self.api.entraram_hoje_servidor
            for tag in self.api.dentro_servidor:
                self.dentro.setdefault(tag, agora_iso())
        elif self.api.colaboradores:
            print("[REDE] servidor inacessivel na inicializacao; validando pelo cache local")
        else:
            print("[AVISO] sem servidor e sem cache: toda tag sera tratada como desconhecida")
        self._salvar_estado()
        self.hw.lcd("Aproxime o", "cracha")
        print("Aproxime o crachá do leitor...")

    # ---------- Regras de acesso ----------

    def tratar_tag(self, tag):
        tag = str(tag)
        momento = agora_iso()
        colab = self.api.colaboradores.get(tag)

        # Tag desconhecida: pode ter sido cadastrada agora no painel, entao
        # busca o cadastro no servidor antes de tratar como invasao
        if colab is None and self.api.online:
            self.api.sincronizar()
            self.t_sync = time.time()
            colab = self.api.colaboradores.get(tag)

        # 1) Tag que nao esta no cadastro: possivel invasao
        if colab is None:
            print(f"Identificação não encontrada! (ID {tag})")
            self.hw.lcd("ACESSO NEGADO", "Tag desconhecida")
            self.api.enviar({"data_hora": momento, "tipo": "invasao", "tag_rfid": tag})
            self.hw.piscar_vermelho_sirene()
            return

        nome = colab["nome"]
        primeiro = nome.split()[0]

        # 2) Cadastrado, mas sem permissao para a sala do projeto
        if not colab["acesso_sala"]:
            print(f"Você não tem acesso a este projeto, {nome}")
            self.hw.lcd("Sem acesso ao", f"projeto, {primeiro}"[:16])
            self.api.enviar({"data_hora": momento, "tipo": "acesso_negado",
                             "tag_rfid": tag, "nome": nome})
            self.hw.led("vermelho", True)
            self.hw.som("negado")
            time.sleep(1.5)
            self.hw.led("vermelho", False)
            return

        # 3) Ja esta na sala: esta leitura e a saida
        if tag in self.dentro:
            entrada = datetime.fromisoformat(self.dentro.pop(tag))
            dur = int((datetime.now() - entrada).total_seconds())
            self.tempo_hoje[nome] = self.tempo_hoje.get(nome, 0) + dur
            print(f"Saída registrada: {nome} ({fmt(dur)} nesta visita, {fmt(self.tempo_hoje[nome])} hoje)")
            self.hw.lcd("Ate logo,", primeiro[:16])
            self.api.enviar({"data_hora": momento, "tipo": "saida", "tag_rfid": tag,
                             "nome": nome, "duracao_segundos": dur})
            self._liberar()
            return

        # 4) Entrada (primeira do dia ou retorno)
        if tag in self.entrou_hoje:
            print(f"Bem-vindo de volta, {nome}")
            self.hw.lcd("Bem-vindo de", f"volta, {primeiro}"[:16])
        else:
            print(f"Bem-vindo, {nome}")
            self.hw.lcd("Bem-vindo,", primeiro[:16])
            self.entrou_hoje.add(tag)
        self.dentro[tag] = momento
        self.api.enviar({"data_hora": momento, "tipo": "entrada", "tag_rfid": tag, "nome": nome})
        self._liberar()

    def _liberar(self):
        self.hw.led("verde", True)
        self.hw.som("autorizado")
        self.hw.abrir_porta()      # fica aberta FECHADURA_TEMPO segundos
        self.hw.led("verde", False)
        self._salvar_estado()

    # ---------- Sensores opcionais ----------

    def tratar_pir(self):
        """Movimento com a sala vazia e sem cracha recente = alguem entrou sem passar o cracha."""
        agora = time.time()
        if self.dentro or agora - self.ultima_leitura_geral < config.PIR_JANELA_CRACHA:
            return
        if agora - self.ultimo_alerta_pir < config.PIR_INTERVALO_ALERTA:
            return
        self.ultimo_alerta_pir = agora
        print("ALERTA: movimento detectado com a sala vazia")
        self.hw.lcd("Movimento sem", "cracha!")
        self.api.enviar({"data_hora": agora_iso(), "tipo": "movimento_sem_cracha",
                         "detalhe": "PIR acionado com a sala vazia"})
        self.hw.som("alerta")
        self.hw.led("vermelho", True); time.sleep(1); self.hw.led("vermelho", False)

    def tratar_botao(self):
        print("Campainha: chamando a segurança")
        self.hw.lcd("Chamando a", "seguranca...")
        self.api.enviar({"data_hora": agora_iso(), "tipo": "campainha",
                         "detalhe": "botao pressionado na porta"})
        self.hw.som("campainha")

    # ---------- Loop principal ----------

    def rodar(self):
        self.iniciar()
        try:
            while True:
                t = time.time()

                tag = self.hw.ler_tag()
                if tag is not None:
                    if t - self.ultima_leitura.get(str(tag), 0) > config.TEMPO_ANTIRREPETICAO:
                        self.tratar_tag(tag)
                        self.ultima_leitura_geral = time.time()
                        self.hw.lcd("Aproxime o", "cracha")
                        print("\nAproxime o crachá do leitor...")
                    self.ultima_leitura[str(tag)] = time.time()

                if self.hw.pir_detectou():
                    self.tratar_pir()
                if self.hw.botao_pressionado():
                    self.tratar_botao()

                if t - self.t_heartbeat > config.INTERVALO_HEARTBEAT:
                    self.t_heartbeat = t
                    self.api.heartbeat(luz=self.hw.luz())
                if t - self.t_sync > config.INTERVALO_SYNC:
                    self.t_sync = t
                    self.api.sincronizar()

                time.sleep(0.1)
        except KeyboardInterrupt:
            self.relatorio()
        finally:
            self._salvar_estado()
            self.hw.encerrar()

    def relatorio(self):
        print("\n" + "=" * 44)
        print(f"{'RESUMO LOCAL DE HOJE':^44}")
        print("=" * 44)
        for nome, seg in sorted(self.tempo_hoje.items()):
            print(f"  {nome:<28} {fmt(seg)}")
        if self.dentro:
            print("\nAinda na sala:")
            for tag, ent in self.dentro.items():
                nome = self.api.colaboradores.get(tag, {}).get("nome", tag)
                print(f"  {nome} (desde {ent[11:19]})")
        print(f"\nEventos pendentes de envio: {len(self.api.fila)}")
        print("=" * 44)


if __name__ == "__main__":
    SalaSegura().rodar()
