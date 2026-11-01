"""Tests de los avisos del compilador."""

from __future__ import annotations

import pytest

from lcero.__main__ import main
from lcero.lexer import tokenize
from lcero.lint import constant, lint
from lcero.parser import parse
from lcero.semantic import analyze

from programas_util import programs


def avisos(src: str) -> list[tuple[int, int, str]]:
    prog = parse(tokenize(src))
    analyze(prog)
    return [(w.linea, w.columna, w.mensaje) for w in lint(prog)]


def mensajes(src: str) -> list[str]:
    return [m for _, _, m in avisos(src)]


@pytest.mark.parametrize("prog", programs("validos"), ids=lambda p: p.id)
def test_los_programas_validos_no_tienen_avisos(prog):
    assert avisos(prog.source) == []


def test_variable_sin_usar():
    assert avisos("int x;") == [(1, 5, "la variable 'x' se declara pero nunca se usa")]


def test_variable_escrita_pero_nunca_leida():
    assert mensajes("int x = 1;\nx = 2;") == ["la variable 'x' recibe valores que nunca se leen"]


def test_variables_homonimas_en_bloques_hermanos_se_distinguen():
    src = "{ int t = 1; print(t); }\n{ int t = 2; }"
    assert avisos(src) == [(2, 7, "la variable 't' recibe valores que nunca se leen")]


@pytest.mark.parametrize(
    "src, value",
    [("3", 3), ("-(2 * 3) + 1", -5), ("7 / 2 == 3", 1), ("1 < 0", 0), ("x + 1", None), ("1 / 0", None)],
)
def test_constant(src, value):
    prog = parse(tokenize(f"int x = 0;\nprint({src});"))
    assert constant(prog.body[1].value) == value


def test_if_constante():
    assert mensajes("if (1 > 2) { print(1); }") == ["la condición del if es siempre falsa: el bloque nunca se ejecuta"]
    assert mensajes("if (1) { print(1); } else { print(2); }") == [
        "la condición del if es siempre verdadera: el else nunca se ejecuta"
    ]


def test_while_constante():
    assert mensajes("while (0) { print(1); }") == ["la condición del while es siempre falsa: el cuerpo nunca se ejecuta"]
    assert mensajes("while (1 == 1) { }") == ["la condición del while es siempre verdadera: el bucle no termina nunca"]


def test_condicion_invariante():
    src = "int i = 0;\nint n = 3;\nwhile (i < n) {\n    print(i);\n}"
    assert avisos(src) == [(3, 10, "ninguna variable de la condición cambia en el cuerpo: "
                                   "si el bucle entra, no termina nunca")]


def test_condicion_que_cambia_en_una_rama_no_avisa():
    # Puede no terminar, pero el análisis no lo afirma: solo avisa lo que es seguro.
    src = "int i = 0;\nwhile (i < 10) {\n    if (i > 100) { i = i + 1; }\n}"
    assert avisos(src) == []


def test_codigo_inalcanzable():
    src = "int x = 0;\nwhile (1) {\n    x = x + 1;\n}\nprint(x);\nprint(x);"
    assert (5, 1, "código inalcanzable: la sentencia anterior no termina nunca") in avisos(src)
    assert len([m for m in mensajes(src) if m.startswith("código inalcanzable")]) == 1


def test_inalcanzable_se_propaga_por_bloques_e_ifs():
    assert "código inalcanzable: la sentencia anterior no termina nunca" in mensajes(
        "{ while (1) { } }\nprint(1);"
    )
    assert "código inalcanzable: la sentencia anterior no termina nunca" in mensajes(
        "int x = 0;\nif (x) { while (1) { } } else { while (1) { } }\nprint(x);"
    )
    assert "código inalcanzable: la sentencia anterior no termina nunca" not in mensajes(
        "int x = 0;\nif (x) { while (1) { } }\nprint(x);"
    )


def test_cli_avisos(tmp_path, capsys):
    f = tmp_path / "p.l0"
    f.write_text("int x;\nwhile (0) { }\n", encoding="utf-8")
    assert main(["avisos", str(f)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "2 avisos"


def test_cli_muestra_todos_los_errores(tmp_path, capsys):
    f = tmp_path / "p.l0"
    f.write_text("int x = 1\nprint(x +);\n", encoding="utf-8")
    assert main(["ejecutar", str(f)]) == 1
    err = capsys.readouterr().err.splitlines()
    assert err[-1] == "2 errores" and len(err) == 3
