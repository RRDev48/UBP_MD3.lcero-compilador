"""Tests del análisis semántico (Fase 3)."""

from __future__ import annotations

import pytest

from lcero import ast as A
from lcero.errors import SemanticError
from lcero.lexer import tokenize
from lcero.parser import parse
from lcero.semantic import analyze

from programas_util import programs


def check(src: str):
    prog = parse(tokenize(src))
    return prog, analyze(prog)


def fails(src: str, fragment: str) -> SemanticError:
    with pytest.raises(SemanticError, match=fragment) as exc:
        check(src)
    return exc.value


@pytest.mark.parametrize("prog", programs("error_semantico"), ids=lambda p: p.id)
def test_programas_con_error_semantico(prog):
    with pytest.raises(SemanticError) as exc:
        check(prog.source)
    assert (exc.value.linea, exc.value.columna) == prog.error_pos


@pytest.mark.parametrize("prog", programs("validos", "bucle_infinito"), ids=lambda p: p.id)
def test_programas_semanticamente_validos(prog):
    check(prog.source)


def test_doble_declaracion_en_el_mismo_bloque():
    e = fails("int a = 1;\nint b = 2;\nint a = 3;", "doble declaración: 'a' ya fue declarada en la línea 1")
    assert (e.linea, e.columna) == (3, 5)


def test_sin_sombreado_en_bloques_anidados():
    fails("int a = 1;\nwhile (a > 0) { int a = 0; }", "doble declaración")


def test_bloques_hermanos_pueden_repetir_nombres():
    prog, syms = check("{ int t = 1; print(t); }\n{ int t = 2; print(t); }")
    assert [s.uid for s in syms] == ["t", "t.1"]
    assert prog.body[1].body[1].value.uid == "t.1"


def test_redeclarar_despues_de_cerrar_el_bloque():
    _, syms = check("{ int t = 1; }\nint t = 5;\nprint(t);")
    assert [s.uid for s in syms] == ["t", "t.1"]


def test_no_declarada():
    fails("x = 1;", "'x' no está declarada")
    fails("print(y);", "'y' no está declarada")


def test_uso_antes_de_la_declaracion():
    fails("x = 1;\nint x;", "'x' no está declarada")


def test_autorreferencia_en_la_inicializacion():
    fails("int x = x + 1;", "'x' puede usarse sin haber sido inicializada")


def test_asignacion_definida_if_sin_else():
    fails("int c = 1;\nint x;\nif (c) { x = 1; }\nprint(x);", "sin haber sido inicializada")


def test_asignacion_definida_if_con_else():
    check("int c = 1;\nint x;\nif (c) { x = 1; } else { x = 2; }\nprint(x);")


def test_asignacion_definida_else_if_sin_else_final():
    fails("int c = 1;\nint x;\nif (c) { x = 1; } else if (c) { x = 2; }\nprint(x);", "inicializada")


def test_asignacion_definida_while_no_cuenta_despues():
    fails("int c = 1;\nint x;\nwhile (c) { x = 1; c = 0; }\nprint(x);", "inicializada")


def test_asignacion_dentro_del_cuerpo_antes_de_usar():
    check("int c = 1;\nwhile (c) { int y; y = 3; print(y); c = 0; }")


def test_lectura_en_iteracion_siguiente_no_cuenta():
    fails("int c = 2;\nint x;\nwhile (c) { print(x); x = 1; c = c - 1; }", "inicializada")


def test_condicion_tambien_se_verifica():
    fails("int x;\nwhile (x < 3) { x = 1; }", "inicializada")


def test_uids_anotados_en_todo_el_ast():
    prog, _ = check("int a = 1;\na = a + 1;\nprint(a);")
    decl, asg, pr = prog.body
    assert decl.uid == asg.uid == "a"
    assert isinstance(asg.value, A.BinOp) and asg.value.left.uid == "a"


# --- Recuperación: todos los errores de una vez -------------------------------------


def todos(src: str) -> list[tuple[int, int, str]]:
    with pytest.raises(SemanticError) as exc:
        check(src)
    return [(e.linea, e.columna, e.mensaje.split(":")[0].split(" '")[0]) for e in exc.value.errores]


def test_informa_todos_los_errores_semanticos():
    src = "int a = 1;\nint a = 2;\nint b;\nprint(b);\nprint(c);\n{ int d = 1; }\nprint(d);"
    assert todos(src) == [
        (2, 5, "doble declaración"),
        (4, 7, "la variable"),
        (5, 7, "la variable"),
        (7, 7, "la variable"),
    ]


def test_cada_nombre_sin_declarar_se_informa_una_vez():
    assert [p[:2] for p in todos("x = 1;\nprint(x);\nprint(x + y);")] == [(1, 1), (3, 11)]


def test_cada_variable_sin_inicializar_se_informa_una_vez():
    assert [p[:2] for p in todos("int a;\nprint(a);\nprint(a + 1);")] == [(2, 7)]


def test_la_doble_declaracion_conserva_la_original():
    # La segunda declaración no reemplaza a la primera: 'a' sigue inicializada.
    assert [p[:2] for p in todos("int a = 1;\nint a;\nprint(a);")] == [(2, 5)]
