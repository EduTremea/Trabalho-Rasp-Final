"""
Configuracao da aplicacao embarcada. Pinos no modo BOARD (numero fisico do conector).
Troque SERVIDOR_URL pelo IP do notebook que roda o Flask.
"""

# ---------- Servidor ----------
SERVIDOR_URL = "http://192.168.0.100:5000"   # IP do computador com o Flask
API_KEY = "rasp-sala-2026"                   # mesmo valor de servidor/config.py
TIMEOUT_HTTP = 3                             # segundos; acima disso considera offline
INTERVALO_HEARTBEAT = 10                     # segundos
INTERVALO_SYNC = 60                          # segundos (recarrega o cadastro)

# ---------- Arquivos locais (cache para funcionar sem rede) ----------
ARQ_CACHE = "cache_colaboradores.json"
ARQ_FILA = "fila_offline.json"
ARQ_ESTADO = "estado_sala.json"

# ---------- Componentes obrigatorios ----------
# O MFRC522 usa os pinos padrao da biblioteca: SDA 24, SCK 23, MOSI 19, MISO 21, RST 22
LED_VERDE = 11      # GPIO17
LED_VERMELHO = 13   # GPIO27
BUZZER = 12         # GPIO18 (piezo)

# ---------- Componentes opcionais (None = nao instalado) ----------
FECHADURA_TIPO = "rele"      # "rele", "servo" ou None
FECHADURA_PINO = 15          # GPIO22
FECHADURA_TEMPO = 3          # segundos que a porta fica liberada
RELE_ATIVO_BAIXO = True      # a maioria dos modulos de rele liga com nivel LOW

PIR_PINO = 16                # GPIO23 (None para desativar)
BOTAO_PINO = 18              # GPIO24, botao para o GND com pull-up interno (None para desativar)
LDR_PINO = 29                # GPIO5, saida digital (DO) do modulo LDR (None para desativar)
LDR_ESCURO_NIVEL = 1         # nivel que o modulo entrega quando esta escuro (ajuste no trimpot)

LCD_ATIVO = True             # display 16x2 (HD44780 / 1602A)
LCD_MODO = "gpio"            # "gpio" = 16 pinos direto (modo 4 bits) | "i2c" = com modulo I2C atras
# Modo gpio: pinos fisicos (BOARD) ligados no LCD
LCD_RS = 31                  # GPIO6
LCD_E = 33                   # GPIO13
LCD_D4 = 35                  # GPIO19
LCD_D5 = 37                  # GPIO26
LCD_D6 = 38                  # GPIO20
LCD_D7 = 40                  # GPIO21
# Modo i2c: endereco do modulo (use `i2cdetect -y 1`: 0x27 ou 0x3F)
LCD_ENDERECO = 0x27

# ---------- Comportamento ----------
TEMPO_ANTIRREPETICAO = 3     # segundos para ignorar o mesmo cracha
PIR_INTERVALO_ALERTA = 60    # segundos entre alertas de movimento sem cracha
PIR_JANELA_CRACHA = 15       # segundos apos uma leitura em que o movimento e esperado
