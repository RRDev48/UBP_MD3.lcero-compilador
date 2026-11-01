"""Alfabeto Σ de L-Cero y su partición en clases de caracteres.

Σ es el conjunto de caracteres que puede aparecer en un programa. Para que la
matriz de transición δ sea legible, Σ se particiona en *clases*: dos
caracteres caen en la misma clase si y solo si ninguna expresión regular de
los tokens los distingue. Sobre esa partición el autómata se comporta igual
que sobre Σ original (la partición es una congruencia respecto de todas las
ER), así que el lenguaje reconocido no cambia.

Clases (30 en total):

* una clase por cada letra que aparece en alguna palabra reservada
  (``e f h i l n p r s t w``), porque el AFD tiene que seguirlas una por una;
* ``LET``: el resto de las letras ASCII y el guion bajo;
* ``DIG``: los dígitos ``0``–``9``;
* una clase por cada símbolo ``+ - * / % = ! < > ( ) { } ;``;
* ``ESP``: espacio, tabulación y retorno de carro;
* ``NL``: salto de línea (se separa porque termina los comentarios);
* ``OTRO``: cualquier otro carácter. Solo es válido dentro de un comentario.
"""

from __future__ import annotations

from .tokens import TokenType

#: Palabras reservadas del lenguaje.
KEYWORDS: dict[str, TokenType] = {
    "int": TokenType.INT,
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "print": TokenType.PRINT,
}

KEYWORD_LETTERS: tuple[str, ...] = tuple(sorted(set("".join(KEYWORDS))))
SYMBOLS: tuple[str, ...] = tuple("+-*/%=!<>(){};")

#: Clases de caracteres, en el orden de las columnas de la matriz δ.
CLASSES: tuple[str, ...] = (*KEYWORD_LETTERS, "LET", "DIG", *SYMBOLS, "ESP", "NL", "OTRO")
CLASS_INDEX: dict[str, int] = {c: i for i, c in enumerate(CLASSES)}

#: Descripción de cada clase para el informe.
CLASS_DESCRIPTION: dict[str, str] = {
    **{c: f"la letra '{c}'" for c in KEYWORD_LETTERS},
    "LET": "[a-zA-Z_] menos {" + ", ".join(KEYWORD_LETTERS) + "}",
    "DIG": "[0-9]",
    **{c: f"el símbolo '{c}'" for c in SYMBOLS},
    "ESP": "espacio, \\t, \\r",
    "NL": "\\n",
    "OTRO": "cualquier otro carácter (solo válido en comentarios)",
}

#: Un carácter concreto de cada clase (para construir testigos legibles).
REPRESENTATIVE: dict[str, str] = {
    **{c: c for c in KEYWORD_LETTERS},
    "LET": "a",
    "DIG": "0",
    **{c: c for c in SYMBOLS},
    "ESP": " ",
    "NL": "\n",
    "OTRO": "@",
}

_KEYWORD_LETTER_SET = frozenset(KEYWORD_LETTERS)
_SYMBOL_SET = frozenset(SYMBOLS)


def char_class(ch: str) -> str:
    """Devuelve el nombre de la clase de ``ch`` (la función de partición de Σ)."""
    if ch in _KEYWORD_LETTER_SET:
        return ch
    if ch.isascii() and (ch.isalpha() or ch == "_"):
        return "LET"
    if ch.isascii() and ch.isdigit():
        return "DIG"
    if ch in _SYMBOL_SET:
        return ch
    if ch in " \t\r":
        return "ESP"
    if ch == "\n":
        return "NL"
    return "OTRO"


# Tabla precalculada para ASCII: el lexer hace una sola indexación por carácter.
_ASCII_TABLE: tuple[int, ...] = tuple(CLASS_INDEX[char_class(chr(i))] for i in range(128))
OTRO_INDEX: int = CLASS_INDEX["OTRO"]


def class_index(ch: str) -> int:
    """Índice de columna de ``ch`` en la matriz δ. Costo O(1)."""
    o = ord(ch)
    return _ASCII_TABLE[o] if o < 128 else OTRO_INDEX
