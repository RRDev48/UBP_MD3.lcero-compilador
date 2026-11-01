"""Tests del analizador léxico (Fase 1)."""

from __future__ import annotations

import pytest

from lcero.errors import LexicalError
from lcero.lexer import tokenize
from lcero.tokens import TokenType as T

from programas_util import programs


def types(src: str) -> list[T]:
    return [t.type for t in tokenize(src)][:-1]  # sin EOF


def lexemes(src: str) -> list[str]:
    return [t.lexeme for t in tokenize(src)][:-1]


# --- Palabras reservadas e identificadores --------------------------------------


def test_palabras_reservadas():
    assert types("int if else while print") == [T.INT, T.IF, T.ELSE, T.WHILE, T.PRINT]


@pytest.mark.parametrize("src", ["i", "in", "iff", "int2", "integer", "e", "el", "els", "elsex",
                                 "w", "whil", "whiles", "p", "prin", "printer", "If", "WHILE", "_", "_x9", "x_y"])
def test_prefijos_y_extensiones_de_reservadas_son_identificadores(src):
    assert types(src) == [T.ID]


def test_reservadas_pegadas_a_simbolos():
    assert types("while(x)") == [T.WHILE, T.LPAREN, T.ID, T.RPAREN]
    assert types("print(x);") == [T.PRINT, T.LPAREN, T.ID, T.RPAREN, T.SEMI]


# --- Números ------------------------------------------------------------------


def test_numeros():
    toks = tokenize("0 42 007 123456789012345678901234567890")
    assert [t.type for t in toks[:-1]] == [T.NUM] * 4
    assert [t.value for t in toks[:-1]] == [0, 42, 7, 123456789012345678901234567890]


def test_numero_seguido_de_letras_son_dos_tokens():
    # Máximo bocado: "123abc" = NUM(123) ID(abc). El error, si lo hay, es sintáctico.
    assert types("123abc") == [T.NUM, T.ID]
    assert lexemes("123abc") == ["123", "abc"]


def test_menos_no_forma_parte_del_literal():
    assert types("-5") == [T.MINUS, T.NUM]
    assert types("x-1") == [T.ID, T.MINUS, T.NUM]


# --- Operadores (máximo bocado) -----------------------------------------------


def test_operadores_de_dos_caracteres():
    assert types("== != <= >=") == [T.EQ, T.NEQ, T.LE, T.GE]


def test_maximo_bocado_en_operadores():
    assert types("a<=b==c!=d>=e<f>g=h") == [
        T.ID, T.LE, T.ID, T.EQ, T.ID, T.NEQ, T.ID, T.GE, T.ID, T.LT, T.ID, T.GT, T.ID, T.ASSIGN, T.ID,
    ]
    assert types("===") == [T.EQ, T.ASSIGN]
    assert types("<==") == [T.LE, T.ASSIGN]
    assert types("= =") == [T.ASSIGN, T.ASSIGN]


def test_todos_los_simbolos_simples():
    assert types("+-*/%(){};") == [
        T.PLUS, T.MINUS, T.STAR, T.SLASH, T.PERCENT, T.LPAREN, T.RPAREN, T.LBRACE, T.RBRACE, T.SEMI,
    ]


# --- Comentarios y espacios ---------------------------------------------------


def test_comentarios_hasta_fin_de_linea():
    assert types("x // esto no se tokeniza: while @ ñ \"\nz") == [T.ID, T.ID]


def test_division_versus_comentario():
    assert types("a/b//c") == [T.ID, T.SLASH, T.ID]
    assert types("a / / b") == [T.ID, T.SLASH, T.SLASH, T.ID]


def test_comentario_al_final_sin_salto_de_linea():
    assert types("x // fin") == [T.ID]


def test_entrada_vacia_y_solo_espacios():
    assert [t.type for t in tokenize("")] == [T.EOF]
    assert [t.type for t in tokenize(" \t\r\n\n // nada\n")] == [T.EOF]


def test_fin_de_linea_windows():
    toks = tokenize("int x;\r\nx = 1;")
    assert [(t.lexeme, t.line, t.col) for t in toks[:4]] == [("int", 1, 1), ("x", 1, 5), (";", 1, 6), ("x", 2, 1)]


# --- Posiciones ---------------------------------------------------------------


def test_lineas_y_columnas():
    src = "int x = 1;\n  while (x)\n{\n}"
    got = [(t.type, t.line, t.col) for t in tokenize(src)]
    assert got == [
        (T.INT, 1, 1), (T.ID, 1, 5), (T.ASSIGN, 1, 7), (T.NUM, 1, 9), (T.SEMI, 1, 10),
        (T.WHILE, 2, 3), (T.LPAREN, 2, 9), (T.ID, 2, 10), (T.RPAREN, 2, 11),
        (T.LBRACE, 3, 1), (T.RBRACE, 4, 1), (T.EOF, 4, 2),
    ]


# --- Errores léxicos ----------------------------------------------------------


@pytest.mark.parametrize(
    "src, line, col, fragment",
    [
        ("x @ y", 1, 3, "'@'"),
        ("int año;", 1, 6, "'ñ'"),
        ('print("hola");', 1, 7, "'\"'"),
        ("a && b", 1, 3, "'&'"),
        ("x = 1;\n  $", 2, 3, "'$'"),
        ("if (!x)", 1, 5, "'!'"),
        ("x !", 1, 3, "'!'"),
    ],
)
def test_errores_lexicos(src, line, col, fragment):
    with pytest.raises(LexicalError) as exc:
        tokenize(src)
    assert (exc.value.linea, exc.value.columna) == (line, col)
    assert fragment in exc.value.mensaje


def test_mensaje_de_signo_de_exclamacion_suelto():
    with pytest.raises(LexicalError, match="no forma ningún token"):
        tokenize("!x")


# --- Programas de la suite ----------------------------------------------------


@pytest.mark.parametrize("prog", programs("error_lexico"), ids=lambda p: p.id)
def test_programas_con_error_lexico(prog):
    assert prog.error_phase == "léxico"
    with pytest.raises(LexicalError) as exc:
        tokenize(prog.source)
    assert (exc.value.linea, exc.value.columna) == prog.error_pos


@pytest.mark.parametrize(
    "prog",
    programs("validos", "error_sintactico", "error_semantico", "bucle_infinito"),
    ids=lambda p: p.id,
)
def test_programas_lexicamente_validos(prog):
    toks = tokenize(prog.source)
    assert toks[-1].type is T.EOF
