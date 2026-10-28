"""
Texto de ponta-cabeca no LCD 16x2 (HD44780), para quando o display esta
montado com os pinos para baixo.

O controlador nao gira o texto, entao a rotacao e feita aqui:
  1. as duas linhas trocam de lugar e cada uma e escrita de tras para frente;
  2. letras que ficam iguais de ponta-cabeca (O, H, I, N, S, X, Z, 0, 8...)
     usam a propria letra da memoria do LCD;
  3. as demais sao desenhadas giradas em 180 graus na memoria de caracteres
     personalizados, que comporta 8 desenhos por tela;
  4. se uma tela precisar de mais de 8, as letras menos usadas recebem um
     caractere parecido (por exemplo M vira W).

O texto e convertido para maiusculas e sem acento.
"""
import unicodedata
from collections import Counter

# Fonte 5x7 no padrao do HD44780 (1 = pixel aceso)
FONTE = {
    " ": ["00000"] * 7,
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "10001", "11001", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "10001", "01010", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ",": ["00000", "00000", "00000", "00000", "01100", "00100", "01000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
}

# Caractere da memoria do LCD que fica bem parecido com a letra girada.
# Essas letras so ganham desenho proprio se sobrar espaco nos 8 da tela.
PARECIDOS = {
    "M": "W", "W": "M", "6": "9", "9": "6", ".": "'", ",": "'", "!": "i",
}


def _normal(linhas):
    return tuple(int(b, 2) for b in linhas) + (0,)


def _girado(linhas):
    """Gira o desenho 5x7 em 180 graus (inverte linhas e colunas)."""
    rows = [0] * 8
    for g, bits in enumerate(linhas):
        rows[6 - g] = int(bits[::-1], 2)
    return tuple(rows)


# Letras cujo desenho girado e igual ao de outra letra da memoria do LCD
_NORMAIS = {_normal(f): c for c, f in FONTE.items()}
IGUAL_GIRADO = {}
for _c, _f in FONTE.items():
    _r = _girado(_f)
    if _r in _NORMAIS:
        IGUAL_GIRADO[_c] = _c if _normal(_f) == _r else _NORMAIS[_r]


def _limpar(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return t.upper()[:16].ljust(16)


def preparar(linha1, linha2):
    """Recebe o texto como deve ser lido e devolve o que gravar no LCD.

    Retorna (fisica1, fisica2, glifos), onde glifos e {posicao: desenho}
    para gravar com create_char antes de escrever as linhas.
    """
    # A linha de cima para quem le e a de baixo do display, ao contrario
    fis1 = _limpar(linha2)[::-1]
    fis2 = _limpar(linha1)[::-1]

    troca = {}
    precisa_desenho = Counter()
    for c in fis1 + fis2:
        if c in IGUAL_GIRADO:
            troca[c] = IGUAL_GIRADO[c]
        elif c in FONTE:
            precisa_desenho[c] += 1
        else:
            troca[c] = " "  # caractere sem desenho conhecido

    # Primeiro as letras sem substituto parecido, das mais usadas para as menos
    ordem = sorted(precisa_desenho, key=lambda c: (c in PARECIDOS, -precisa_desenho[c]))
    glifos = {}
    for pos, c in enumerate(ordem):
        if pos < 8:
            glifos[pos] = _girado(FONTE[c])
            troca[c] = chr(pos)
        else:
            troca[c] = PARECIDOS.get(c, c)

    conv = lambda s: "".join(troca[c] for c in s)
    return conv(fis1), conv(fis2), glifos
