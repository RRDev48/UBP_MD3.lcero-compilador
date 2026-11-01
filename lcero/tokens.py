"""Categorías léxicas (tokens) de L-Cero.

El valor de cada miembro de ``TokenType`` es el símbolo terminal con el que
aparece en la gramática de la Fase 2 (por ejemplo ``id``, ``num``, ``while``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    # Palabras reservadas
    INT = "int"
    IF = "if"
    ELSE = "else"
    WHILE = "while"
    PRINT = "print"
    # Identificadores y literales
    ID = "id"
    NUM = "num"
    # Operadores aritméticos
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    # Asignación y operadores relacionales
    ASSIGN = "="
    EQ = "=="
    NEQ = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    # Delimitadores
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    SEMI = ";"
    # Marca de fin de entrada (el "$" de los conjuntos Follow)
    EOF = "$"
    # Categorías que el lexer reconoce pero descarta
    COMMENT = "comentario"
    WS = "espacio"

    def __str__(self) -> str:
        return self.value


#: Tokens que el lexer reconoce pero no entrega al parser.
SKIPPED = frozenset({TokenType.COMMENT, TokenType.WS})


@dataclass(frozen=True, slots=True)
class Token:
    """Un token: categoría, lexema y posición (línea y columna, 1-based)."""

    type: TokenType
    lexeme: str
    line: int
    col: int

    @property
    def value(self) -> int | None:
        """Valor entero de un literal ``num``; ``None`` para el resto."""
        return int(self.lexeme) if self.type is TokenType.NUM else None

    def __str__(self) -> str:
        if self.type in (TokenType.ID, TokenType.NUM):
            return f"{self.type.name}({self.lexeme}) @{self.line}:{self.col}"
        return f"{self.type.name} @{self.line}:{self.col}"
