"""Monta o analise_acessos.ipynb a partir das celulas abaixo (so para gerar o arquivo)."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []

C.append(nbf.v4.new_markdown_cell("""# Sala Segura: análise dos logs de acesso

Notebook da disciplina Hardware Architecture (Atitus). Lê os eventos gerados pelo sistema de controle
de acesso da sala do projeto e responde as perguntas do enunciado.

Fonte dos dados, em ordem de preferência:

1. API do servidor Flask (`/api/eventos.csv`), se estiver no ar;
2. arquivo `dados/acessos.csv` exportado pelo painel.

Cada linha é um evento: `entrada`, `saida` (com `duracao_segundos`), `acesso_negado`
(colaborador cadastrado sem permissão), `invasao` (tag desconhecida), `movimento_sem_cracha` ou `campainha`."""))

C.append(nbf.v4.new_code_cell("""import io
import requests
import pandas as pd
import matplotlib.pyplot as plt

SERVIDOR = "http://127.0.0.1:5000"   # troque pelo IP do servidor, se preciso
ARQUIVO_LOCAL = "dados/acessos.csv"

def carregar():
    try:
        r = requests.get(f"{SERVIDOR}/api/eventos.csv", timeout=3)
        r.raise_for_status()
        print("Dados carregados da API")
        return pd.read_csv(io.StringIO(r.text), dtype={"tag_rfid": str})
    except requests.RequestException:
        print("API indisponível, usando o CSV local")
        return pd.read_csv(ARQUIVO_LOCAL, dtype={"tag_rfid": str})

df = carregar()
df["data_hora"] = pd.to_datetime(df["data_hora"])
df["data"] = df["data_hora"].dt.date
df["hora"] = df["data_hora"].dt.hour
print(f"{len(df)} eventos de {df['data'].min()} a {df['data'].max()}")
df.head()"""))

C.append(nbf.v4.new_markdown_cell("## Visão geral"))
C.append(nbf.v4.new_code_cell("""df["tipo"].value_counts()"""))
C.append(nbf.v4.new_code_cell("""# Eventos por dia e tipo
por_dia = df.pivot_table(index="data", columns="tipo", values="id", aggfunc="count", fill_value=0)
por_dia"""))
C.append(nbf.v4.new_code_cell("""ax = por_dia.plot(kind="bar", stacked=True, figsize=(10, 4), title="Eventos por dia")
ax.set_xlabel("")
ax.set_ylabel("eventos")
plt.tight_layout()
plt.show()"""))

C.append(nbf.v4.new_markdown_cell("""## Perguntas do enunciado

Troque `DIA` e `COLABORADOR` para consultar outro dia ou outra pessoa."""))

C.append(nbf.v4.new_code_cell("""# Dia com mais movimento no conjunto de dados (so para ter um exemplo preenchido)
DIA = df[df["tipo"] == "entrada"]["data"].value_counts().idxmax()
COLABORADOR = "Luiz Eduardo Tremea"
dia_df = df[df["data"] == DIA]
print("Dia analisado:", DIA)"""))

C.append(nbf.v4.new_markdown_cell("### 1. Quantas pessoas entraram na sala no dia?"))
C.append(nbf.v4.new_code_cell("""entradas = dia_df[dia_df["tipo"] == "entrada"]
print(f"{entradas['nome'].nunique()} pessoa(s) distinta(s), em {len(entradas)} entrada(s)")
entradas.groupby("nome").size().rename("entradas")"""))

C.append(nbf.v4.new_markdown_cell("### 2. Quantas pessoas saíram da sala no dia?"))
C.append(nbf.v4.new_code_cell("""saidas = dia_df[dia_df["tipo"] == "saida"]
print(f"{saidas['nome'].nunique()} pessoa(s) distinta(s), em {len(saidas)} saída(s)")
saidas.groupby("nome").size().rename("saidas")"""))

C.append(nbf.v4.new_markdown_cell("### 3. Quanto tempo um colaborador ficou na sala no dia?"))
C.append(nbf.v4.new_code_cell("""def tempo_na_sala(df, nome, dia):
    s = df[(df["tipo"] == "saida") & (df["nome"] == nome) & (df["data"] == dia)]
    return pd.to_timedelta(s["duracao_segundos"].sum(), unit="s")

print(f"{COLABORADOR} ficou {tempo_na_sala(df, COLABORADOR, DIA)} na sala em {DIA}")

# Tempo de todos no dia
(dia_df[dia_df["tipo"] == "saida"]
   .groupby("nome")["duracao_segundos"].sum()
   .pipe(lambda s: pd.to_timedelta(s, unit="s"))
   .rename("tempo_na_sala"))"""))

C.append(nbf.v4.new_code_cell("""# Tempo diário por colaborador em todo o período (em horas)
tempo = (df[df["tipo"] == "saida"]
           .pivot_table(index="data", columns="nome", values="duracao_segundos", aggfunc="sum", fill_value=0) / 3600)
ax = tempo.plot(kind="bar", figsize=(10, 4), title="Horas na sala por dia")
ax.set_ylabel("horas")
ax.set_xlabel("")
plt.tight_layout()
plt.show()
tempo.round(2)"""))

C.append(nbf.v4.new_markdown_cell("### 4. Quantas tentativas de acesso negado ocorreram no dia?"))
C.append(nbf.v4.new_code_cell("""negados = dia_df[dia_df["tipo"] == "acesso_negado"]
print(f"{len(negados)} tentativa(s) de acesso negado em {DIA}")
negados[["data_hora", "nome", "tag_rfid"]]"""))

C.append(nbf.v4.new_markdown_cell("### 5. Quantas tentativas de invasão ocorreram no dia?"))
C.append(nbf.v4.new_code_cell("""invasoes = dia_df[dia_df["tipo"] == "invasao"]
print(f"{len(invasoes)} tentativa(s) de invasão em {DIA}")
invasoes[["data_hora", "tag_rfid"]]"""))

C.append(nbf.v4.new_markdown_cell("### 6. Quais colaboradores não autorizados mais tentaram acessar a sala no dia?"))
C.append(nbf.v4.new_code_cell("""ranking = (dia_df[dia_df["tipo"] == "acesso_negado"]
             .groupby("nome").size()
             .sort_values(ascending=False)
             .rename("tentativas"))
ranking"""))

C.append(nbf.v4.new_markdown_cell("## Extras: padrões no período inteiro"))
C.append(nbf.v4.new_code_cell("""# Ranking geral de quem mais tentou sem permissão
df[df["tipo"] == "acesso_negado"].groupby("nome").size().sort_values(ascending=False).rename("tentativas")"""))
C.append(nbf.v4.new_code_cell("""# Em que horas acontecem os alertas (invasao + acesso negado)?
alertas = df[df["tipo"].isin(["invasao", "acesso_negado"])]
ax = alertas.groupby(["hora", "tipo"]).size().unstack(fill_value=0).plot(
    kind="bar", figsize=(10, 3.5), title="Alertas por hora do dia")
ax.set_xlabel("hora")
ax.set_ylabel("alertas")
plt.tight_layout()
plt.show()"""))
C.append(nbf.v4.new_code_cell("""# Tags desconhecidas que mais apareceram (candidatas a investigacao)
df[df["tipo"] == "invasao"]["tag_rfid"].value_counts().rename("tentativas")"""))
C.append(nbf.v4.new_code_cell("""# Resumo diario em uma tabela so
resumo = pd.DataFrame({
    "pessoas_entraram": df[df["tipo"] == "entrada"].groupby("data")["nome"].nunique(),
    "entradas": df[df["tipo"] == "entrada"].groupby("data").size(),
    "saidas": df[df["tipo"] == "saida"].groupby("data").size(),
    "acessos_negados": df[df["tipo"] == "acesso_negado"].groupby("data").size(),
    "invasoes": df[df["tipo"] == "invasao"].groupby("data").size(),
    "horas_na_sala": df[df["tipo"] == "saida"].groupby("data")["duracao_segundos"].sum() / 3600,
}).fillna(0).round(2)
resumo"""))

nb["cells"] = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, "analise_acessos.ipynb")
print("analise_acessos.ipynb gerado")
