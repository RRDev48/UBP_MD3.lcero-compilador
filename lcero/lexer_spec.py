"""Expresiones regulares de cada token de L-Cero.

El orden de ``TOKEN_SPECS`` es la prioridad ante empates de longitud: las
palabras reservadas van antes que ``id`` para que ``while`` sea WHILE y no
ID. Ante longitudes distintas manda la regla del *máximo bocado* (ver
``lexer.py``): ``whilex`` es un ID, ``<=`` es LE y no LT seguido de ASSIGN.

Notación del informe:  letra = [a-zA-Z_],  dígito = [0-9].
"""

from __future__ import annotations

from dataclasses import dataclass

from .alphabet import CLASSES, KEYWORD_LETTERS, KEYWORDS, char_class
from .regex import Regex, alt, plus, seq, star, sym
from .tokens import TokenType as T


@dataclass(frozen=True)
class TokenSpec:
    type: T
    regex: Regex
    #: La ER tal como se escribe en el informe.
    er: str


def word(s: str) -> Regex:
    """ER que reconoce exactamente la cadena ``s``."""
    return seq(*(sym(char_class(ch)) for ch in s))


LETTER = alt(*(sym(c) for c in KEYWORD_LETTERS), sym("LET"))  # letra = [a-zA-Z_]
DIGIT = sym("DIG")  # dígito = [0-9]
NOT_NEWLINE = alt(*(sym(c) for c in CLASSES if c != "NL"))  # Σ − {\n}

TOKEN_SPECS: tuple[TokenSpec, ...] = (
    # Palabras reservadas (prioridad sobre id)
    *(TokenSpec(tt, word(kw), kw) for kw, tt in KEYWORDS.items()),
    # Identificadores y números
    TokenSpec(T.ID, seq(LETTER, star(alt(LETTER, DIGIT))), "letra (letra | dígito)*"),
    TokenSpec(T.NUM, plus(DIGIT), "dígito dígito*"),
    # Operadores de dos caracteres
    TokenSpec(T.EQ, word("=="), "=="),
    TokenSpec(T.NEQ, word("!="), "!="),
    TokenSpec(T.LE, word("<="), "<="),
    TokenSpec(T.GE, word(">="), ">="),
    # Operadores y delimitadores de un carácter
    TokenSpec(T.ASSIGN, word("="), "="),
    TokenSpec(T.LT, word("<"), "<"),
    TokenSpec(T.GT, word(">"), ">"),
    TokenSpec(T.PLUS, word("+"), "+"),
    TokenSpec(T.MINUS, word("-"), "-"),
    TokenSpec(T.STAR, word("*"), "*"),
    TokenSpec(T.SLASH, word("/"), "/"),
    TokenSpec(T.PERCENT, word("%"), "%"),
    TokenSpec(T.LPAREN, word("("), "("),
    TokenSpec(T.RPAREN, word(")"), ")"),
    TokenSpec(T.LBRACE, word("{"), "{"),
    TokenSpec(T.RBRACE, word("}"), "}"),
    TokenSpec(T.SEMI, word(";"), ";"),
    # Categorías descartadas
    TokenSpec(T.COMMENT, seq(sym("/"), sym("/"), star(NOT_NEWLINE)), "// (Σ − {\\n})*"),
    TokenSpec(T.WS, plus(alt(sym("ESP"), sym("NL"))), "(' ' | \\t | \\r | \\n)(' ' | \\t | \\r | \\n)*"),
)
