"""
Camada de hardware. Se as bibliotecas da Raspberry nao estiverem instaladas
(ou se rodar com --simular), tudo vira impressao no terminal e o cracha e
digitado pelo teclado. Assim da para testar a integracao sem a placa.
"""
import sys
import threading
import time
import queue

import config

SIMULADO = "--simular" in sys.argv
try:
    if SIMULADO:
        raise ImportError
    import RPi.GPIO as GPIO
    from mfrc522 import SimpleMFRC522
except ImportError:
    SIMULADO = True


# =====================================================================
#  Modo simulado (sem hardware)
# =====================================================================

class _Teclado:
    """Le linhas do terminal em uma thread e entrega para o loop principal.

    Comandos:  <id da tag>   -> aproxima o cracha
               p             -> movimento no PIR
               b             -> aperta o botao
               l             -> alterna luz clara/escura
    """
    def __init__(self):
        self.fila = queue.Queue()
        self.luz_clara = True
        threading.Thread(target=self._ler, daemon=True).start()

    def _ler(self):
        for linha in sys.stdin:
            self.fila.put(linha.strip())

    def proximo(self):
        try:
            return self.fila.get_nowait()
        except queue.Empty:
            return None


class HardwareSimulado:
    def __init__(self):
        print("[SIMULACAO] Sem GPIO. Digite o ID da tag e Enter. 'p' = PIR, 'b' = botao, 'l' = luz.")
        self.teclado = _Teclado()
        self._pir = False
        self._botao = False

    # -- entradas --
    def ler_tag(self):
        cmd = self.teclado.proximo()
        if cmd is None or cmd == "":
            return None
        if cmd == "p":
            self._pir = True
            return None
        if cmd == "b":
            self._botao = True
            return None
        if cmd == "l":
            self.teclado.luz_clara = not self.teclado.luz_clara
            print(f"[SIMULACAO] luz agora: {'clara' if self.teclado.luz_clara else 'escura'}")
            return None
        try:
            return int(cmd)
        except ValueError:
            print("[SIMULACAO] comando desconhecido")
            return None

    def pir_detectou(self):
        v, self._pir = self._pir, False
        return v

    def botao_pressionado(self):
        v, self._botao = self._botao, False
        return v

    def luz(self):
        return "clara" if self.teclado.luz_clara else "escura"

    # -- saidas --
    def lcd(self, linha1, linha2=""):
        print(f"[LCD] |{linha1[:16]:<16}|\n[LCD] |{linha2[:16]:<16}|")

    def led(self, cor, ligado):
        print(f"[LED {cor}] {'ON' if ligado else 'off'}")

    def som(self, nome):
        print(f"[BUZZER] {nome}")

    def abrir_porta(self):
        print(f"[FECHADURA] liberada por {config.FECHADURA_TEMPO}s")

    def piscar_vermelho_sirene(self, vezes=6):
        print(f"[LED vermelho + BUZZER] sirene x{vezes}")
        time.sleep(0.5)

    def encerrar(self):
        pass


# =====================================================================
#  Hardware real
# =====================================================================

class HardwareReal:
    def __init__(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)
        GPIO.setup(config.LED_VERDE, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(config.LED_VERMELHO, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(config.BUZZER, GPIO.OUT, initial=GPIO.LOW)
        self.buzzer = GPIO.PWM(config.BUZZER, 1000)
        self.leitor = SimpleMFRC522()

        # Fechadura (rele ou servo)
        self.servo = None
        if config.FECHADURA_TIPO == "rele":
            nivel_fechado = GPIO.HIGH if config.RELE_ATIVO_BAIXO else GPIO.LOW
            GPIO.setup(config.FECHADURA_PINO, GPIO.OUT, initial=nivel_fechado)
        elif config.FECHADURA_TIPO == "servo":
            GPIO.setup(config.FECHADURA_PINO, GPIO.OUT)
            self.servo = GPIO.PWM(config.FECHADURA_PINO, 50)  # 50 Hz
            self.servo.start(0)

        # Sensores opcionais
        if config.PIR_PINO:
            GPIO.setup(config.PIR_PINO, GPIO.IN)
        if config.BOTAO_PINO:
            GPIO.setup(config.BOTAO_PINO, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        if config.LDR_PINO:
            GPIO.setup(config.LDR_PINO, GPIO.IN)
        self._ultimo_botao = 0

        # Display LCD I2C
        self.display = None
        if config.LCD_ATIVO:
            try:
                from RPLCD.i2c import CharLCD
                self.display = CharLCD("PCF8574", config.LCD_ENDERECO, cols=16, rows=2)
                self.display.clear()
            except Exception as e:  # sem display nao pode travar o resto
                print(f"[LCD] nao encontrado ({e}); seguindo sem display")

    # -- entradas --
    def ler_tag(self):
        return self.leitor.read_id_no_block()

    def pir_detectou(self):
        return bool(config.PIR_PINO) and GPIO.input(config.PIR_PINO) == GPIO.HIGH

    def botao_pressionado(self):
        if not config.BOTAO_PINO:
            return False
        if GPIO.input(config.BOTAO_PINO) == GPIO.LOW and time.time() - self._ultimo_botao > 1:
            self._ultimo_botao = time.time()  # debounce simples
            return True
        return False

    def luz(self):
        if not config.LDR_PINO:
            return None
        return "escura" if GPIO.input(config.LDR_PINO) == config.LDR_ESCURO_NIVEL else "clara"

    # -- saidas --
    def lcd(self, linha1, linha2=""):
        print(f"[LCD] {linha1} / {linha2}")
        if self.display:
            self.display.clear()
            self.display.write_string(linha1[:16])
            self.display.crlf()
            self.display.write_string(linha2[:16])

    def led(self, cor, ligado):
        pino = config.LED_VERDE if cor == "verde" else config.LED_VERMELHO
        GPIO.output(pino, GPIO.HIGH if ligado else GPIO.LOW)

    def _tocar(self, freq, dur):
        self.buzzer.ChangeFrequency(freq)
        self.buzzer.start(50)
        time.sleep(dur)
        self.buzzer.stop()

    def som(self, nome):
        if nome == "autorizado":       # dois bipes agudos
            self._tocar(2000, 0.1); time.sleep(0.05); self._tocar(2500, 0.1)
        elif nome == "negado":         # um bipe grave e longo
            self._tocar(400, 0.8)
        elif nome == "campainha":      # tres bipes medios
            for _ in range(3):
                self._tocar(1200, 0.15); time.sleep(0.1)
        elif nome == "alerta":         # dois bipes graves
            self._tocar(600, 0.3); time.sleep(0.1); self._tocar(600, 0.3)

    def abrir_porta(self):
        if config.FECHADURA_TIPO == "rele":
            ligar = GPIO.LOW if config.RELE_ATIVO_BAIXO else GPIO.HIGH
            GPIO.output(config.FECHADURA_PINO, ligar)
            time.sleep(config.FECHADURA_TEMPO)
            GPIO.output(config.FECHADURA_PINO, not ligar)
        elif self.servo:
            self.servo.ChangeDutyCycle(7.5)   # ~90 graus = aberto
            time.sleep(config.FECHADURA_TEMPO)
            self.servo.ChangeDutyCycle(2.5)   # ~0 grau = fechado
            time.sleep(0.5)
            self.servo.ChangeDutyCycle(0)     # para de tremer

    def piscar_vermelho_sirene(self, vezes=6):
        for i in range(vezes):
            self.led("vermelho", True)
            self._tocar(1800 if i % 2 == 0 else 900, 0.2)
            self.led("vermelho", False)
            time.sleep(0.15)

    def encerrar(self):
        self.buzzer.stop()
        if self.servo:
            self.servo.stop()
        if self.display:
            self.display.clear()
            self.display.close(clear=True)
        GPIO.cleanup()


def criar():
    return HardwareSimulado() if SIMULADO else HardwareReal()
