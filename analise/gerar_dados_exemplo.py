"""
Gera eventos ficticios de varios dias e envia para a API, para testar o painel
e o notebook sem precisar passar cracha por uma semana.

Uso:  python gerar_dados_exemplo.py [http://servidor:5000] [dias]
"""
import random
import sys
from datetime import datetime, timedelta

import requests

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
DIAS = int(sys.argv[2]) if len(sys.argv) > 2 else 7
H = {"X-Api-Key": "rasp-sala-2026"}

random.seed(42)  # resultado reproduzivel

# Mesmos colaboradores do seed.py
AUTORIZADOS = [("111111111111", "Luiz Eduardo Tremea"), ("222222222222", "Bruno Benetti")]
SEM_ACESSO = [("333333333333", "Patrick M."), ("444444444444", "Ana Souza")]
DESCONHECIDAS = ["734528190", "88120033421", "501277364", "9900112233"]

eventos = []
hoje = datetime.now().date()
for d in range(DIAS, 0, -1):
    dia = hoje - timedelta(days=d)
    if dia.weekday() >= 5:      # fim de semana: so tentativas de invasao, raras
        if random.random() < 0.3:
            t = datetime.combine(dia, datetime.min.time()) + timedelta(hours=random.randint(1, 5))
            eventos.append({"data_hora": t.isoformat(timespec="seconds"), "tipo": "invasao",
                            "tag_rfid": random.choice(DESCONHECIDAS)})
        continue

    for tag, nome in AUTORIZADOS:
        if random.random() < 0.1:   # faltou
            continue
        # 1 a 3 visitas no dia
        t = datetime.combine(dia, datetime.min.time()) + timedelta(hours=8, minutes=random.randint(0, 90))
        for _ in range(random.randint(1, 3)):
            dur = random.randint(25, 180) * 60
            eventos.append({"data_hora": t.isoformat(timespec="seconds"), "tipo": "entrada",
                            "tag_rfid": tag, "nome": nome})
            t += timedelta(seconds=dur)
            eventos.append({"data_hora": t.isoformat(timespec="seconds"), "tipo": "saida",
                            "tag_rfid": tag, "nome": nome, "duracao_segundos": dur})
            t += timedelta(minutes=random.randint(10, 90))

    for tag, nome in SEM_ACESSO:
        for _ in range(random.choice([0, 0, 1, 1, 2, 3])):
            t = datetime.combine(dia, datetime.min.time()) + timedelta(hours=random.randint(8, 18), minutes=random.randint(0, 59))
            eventos.append({"data_hora": t.isoformat(timespec="seconds"), "tipo": "acesso_negado",
                            "tag_rfid": tag, "nome": nome})

    for _ in range(random.choice([0, 0, 1, 2])):
        t = datetime.combine(dia, datetime.min.time()) + timedelta(hours=random.randint(7, 22), minutes=random.randint(0, 59))
        eventos.append({"data_hora": t.isoformat(timespec="seconds"), "tipo": "invasao",
                        "tag_rfid": random.choice(DESCONHECIDAS)})

    if random.random() < 0.3:
        t = datetime.combine(dia, datetime.min.time()) + timedelta(hours=random.randint(8, 18))
        eventos.append({"data_hora": t.isoformat(timespec="seconds"), "tipo": "campainha",
                        "detalhe": "botao pressionado na porta"})

for e in eventos:
    e["origem"] = "simulador"

r = requests.post(f"{URL}/api/eventos", json=eventos, headers=H, timeout=10)
print(f"{len(eventos)} eventos gerados ->", r.json())
