# Sala Segura: controle de acesso com RFID

Projeto final de Hardware Architecture (Atitus, 2026.1). Controle de acesso a uma sala de projeto sob NDA, com Raspberry Pi + RFID na porta, servidor Flask como hub central, painel web para gestão e monitoramento, e análise dos logs em Pandas.

## Integrantes

| Integrante | Responsabilidade | Pasta |
|---|---|---|
| Luiz Eduardo Tremea | Aplicação embarcada (Raspberry, sensores, cache offline) | `raspberry/` |
| Bruno Benetti | Servidor Flask, API e painel web | `servidor/` |
| Patrick M. | Análise de dados (Pandas) e documentação | `analise/`, `docs/` |

> Ajuste a tabela acima conforme a divisão real do grupo.

## Como funciona

```
 crachá RFID ──► Raspberry Pi ──HTTP──► Servidor Flask + SQLite ──► Painel web (gestão + monitoramento)
                 LEDs, buzzer,                 ▲                        │
                 LCD, fechadura,               │ cache local +          └──► CSV / API ──► Notebook Pandas
                 PIR, botão, LDR               │ fila offline
```

1. Ao ligar, a Raspberry baixa o cadastro (`GET /api/sync`) e guarda em `cache_colaboradores.json`.
2. Cada leitura de crachá é validada **localmente** e vira um evento enviado por `POST /api/eventos`.
3. Se o servidor estiver fora, o evento vai para `fila_offline.json` e é reenviado quando a conexão volta (o servidor ignora duplicatas).
4. O painel lê o banco e a página de monitoramento atualiza a cada 3 s por polling em `/api/status`.
5. O notebook lê `/api/eventos.csv` (ou o CSV exportado) e responde as perguntas do enunciado.

### Regras na porta

| Situação | Tela / LCD | Atuadores | Evento |
|---|---|---|---|
| Autorizado, 1ª vez no dia | Bem-vindo, {nome} | LED verde, 2 bipes agudos, fechadura 3 s | `entrada` |
| Autorizado, já entrou hoje | Bem-vindo de volta, {nome} | idem | `entrada` |
| Autorizado, já está dentro | Até logo, {nome} + tempo do dia | idem | `saida` (com duração) |
| Cadastrado sem acesso | Sem acesso ao projeto | LED vermelho, bipe grave | `acesso_negado` |
| Tag desconhecida | ACESSO NEGADO + ID | vermelho piscando + sirene | `invasao` |
| PIR com sala vazia | Movimento sem crachá | vermelho + 2 bipes | `movimento_sem_cracha` |
| Botão da porta | Chamando a segurança | 3 bipes | `campainha` |

Entrada e saída alternam a cada leitura do mesmo crachá. O LDR só informa se a sala está iluminada (aparece no monitoramento).

## Estrutura

```
sala-segura/
├── raspberry/      main.py, hardware.py, cliente_api.py, config.py
├── servidor/       app.py, api.py, web.py, db.py, seed.py, templates/, static/
├── analise/        analise_acessos.ipynb, gerar_dados_exemplo.py, dados/acessos.csv
└── docs/           documentacao.pdf, apresentacao.pdf, imagens/
```

## Como rodar

### 1. Servidor (notebook do grupo, na mesma rede Wi-Fi da Rasp)

```bash
cd servidor
python -m venv env && source env/bin/activate     # Windows: env\Scripts\activate
pip install -r requirements.txt
python seed.py            # cria admin/admin123 e colaboradores de exemplo
python app.py             # http://<ip-do-notebook>:5000
```

Descubra o IP com `ipconfig` (Windows) ou `hostname -I` (Linux). Libere a porta 5000 no firewall se precisar.

### 2. Raspberry Pi

```bash
sudo raspi-config         # Interface Options: ativar SPI e I2C
cd raspberry
python -m venv env --system-site-packages && source env/bin/activate
pip install -r requirements.txt
nano config.py            # SERVIDOR_URL = "http://<ip-do-notebook>:5000" e flags dos componentes
python main.py
```

Sem a placa (ou para testar no PC): `python main.py --simular`. Digite o ID da tag e Enter; `p` simula o PIR, `b` o botão, `l` alterna a luz.

Para cadastrar um crachá novo: passe no leitor, copie o ID que aparece junto com "Identificação não encontrada!" e cole no painel em Colaboradores.

### 3. Dados de exemplo e notebook

```bash
cd analise
pip install -r requirements.txt
python gerar_dados_exemplo.py http://127.0.0.1:5000 7   # 7 dias de eventos fictícios
jupyter notebook analise_acessos.ipynb
```

## Ligações (modo BOARD)

| Componente | Pino físico | GPIO |
|---|---|---|
| RFID SDA / SCK / MOSI / MISO / RST | 24 / 23 / 19 / 21 / 22 | 8 / 11 / 10 / 9 / 25 |
| RFID 3,3 V / GND | 1 / 6 | |
| LED verde / LED vermelho | 11 / 13 | 17 / 27 |
| Buzzer | 12 | 18 |
| Relé ou servo (fechadura) | 15 | 22 |
| Sensor PIR (OUT) | 16 | 23 |
| Botão (para GND, pull-up interno) | 18 | 24 |
| LDR módulo (DO) | 29 | 5 |
| LCD I2C SDA / SCL | 3 / 5 | 2 / 3 |
| GND comum | 9 | |

LEDs com resistor de 220 a 330 Ω. O RFID vai no 3,3 V; o LCD, relé, PIR e LDR no 5 V (pino 2 ou 4). Servo em 5 V com GND comum.

## API

| Método | Rota | Uso |
|---|---|---|
| GET | `/api/sync` | cadastro + quem está dentro + quem já entrou hoje |
| POST | `/api/eventos` | um evento ou lista (fila offline) |
| POST | `/api/heartbeat` | estado da Rasp (luz, fila pendente) |
| GET | `/api/status` | resumo para o monitoramento |
| GET | `/api/eventos` / `/api/eventos.csv` | logs em JSON ou CSV (`?data=AAAA-MM-DD&tipo=`) |

As rotas que a Rasp usa exigem o cabeçalho `X-Api-Key` (valor em `servidor/config.py` e `raspberry/config.py`).

## Limitações do MVP

- A autenticação do painel é por usuário e senha em sessão; não há perfis nem HTTPS.
- Entrada e saída dependem de o colaborador passar o crachá nas duas direções. Se esquecer na saída, a próxima leitura é tratada como saída.
- Se a Rasp reiniciar sem rede e sem cache, toda tag é tratada como desconhecida até a primeira sincronização.
- Durante a falta de rede, o painel não vê os eventos. Eles chegam juntos na reconexão, com a hora original.
- O relógio da Rasp precisa estar certo (NTP) para os horários baterem com o servidor.
