"""Tests de la gramática LL(1) y del parser predictivo (Fase 2)."""

from __future__ import annotations

import pytest

from lcero import ast as A
from lcero.errors import ParseError
from lcero.grammar import END, EPSILON, Grammar
from lcero.lcero_grammar import lcero_grammar
from lcero.lexer import tokenize
from lcero.parser import Parser, TraceRow

from programas_util import programs

STMT = {"int", "id", "if", "while", "print", "{"}
EXPR = {"num", "id", "(", "-"}
REL = {"==", "!=", "<", "<=", ">", ">="}


def parse(src: str) -> A.Program:
    return Parser().parse(tokenize(src))


# --- Conjuntos First / Follow (valores calculados a mano en el informe) -------


def test_first_calculado_a_mano():
    g = lcero_grammar()
    assert g.first["Sent"] == STMT
    assert g.first["ListaSent"] == STMT | {EPSILON}
    assert g.first["Expr"] == g.first["Arit"] == g.first["Term"] == g.first["Factor"] == EXPR
    assert g.first["ExprRel"] == REL | {EPSILON}
    assert g.first["AritCola"] == {"+", "-", EPSILON}
    assert g.first["TermCola"] == {"*", "/", "%", EPSILON}
    assert g.first["SiNo"] == {"else", EPSILON}
    assert g.first["CuerpoSiNo"] == {"{", "if"}
    assert g.first["DeclInit"] == {"=", EPSILON}


def test_follow_calculado_a_mano():
    g = lcero_grammar()
    assert g.follow["Programa"] == {END}
    assert g.follow["ListaSent"] == {END, "}"}
    assert g.follow["Sent"] == STMT | {END, "}"}
    assert g.follow["Bloque"] == STMT | {END, "}", "else"}
    assert g.follow["SiNo"] == STMT | {END, "}"}
    assert g.follow["Expr"] == g.follow["ExprRel"] == {";", ")"}
    assert g.follow["Arit"] == g.follow["AritCola"] == REL | {";", ")"}
    assert g.follow["Term"] == g.follow["TermCola"] == REL | {";", ")", "+", "-"}
    assert g.follow["Factor"] == REL | {";", ")", "+", "-", "*", "/", "%"}
    assert g.follow["DeclInit"] == {";"}


def test_condicion_ll1_predict_disjuntos():
    g = lcero_grammar()
    for N in g.nonterminals:
        prods = g.by_lhs[N]
        for i, p in enumerate(prods):
            for q in prods[i + 1:]:
                assert not (g.predict(p) & g.predict(q)), (p, q)


def test_tabla_sin_conflictos():
    table, conflicts = lcero_grammar().ll1_table()
    assert conflicts == []
    assert len(table) == 93


def test_else_no_esta_en_follow_de_sent():
    # La clave de que no haya "else colgante": else ∉ Follow(SiNo).
    g = lcero_grammar()
    assert "else" not in g.follow["SiNo"]


def test_detecta_gramatica_ambigua_con_else_colgante():
    g = Grammar("S", [
        ("S", ["if", "S", "E"]), ("S", ["a"]),
        ("E", ["else", "S"]), ("E", []),
    ], ["if", "else", "a", END])
    _, conflicts = g.ll1_table()
    assert [(c.nonterminal, c.terminal) for c in conflicts] == [("E", "else")]


def test_detecta_recursion_a_izquierda():
    g = Grammar("E", [("E", ["E", "+", "n"]), ("E", ["n"])], ["+", "n", END])
    assert not g.is_ll1()


# --- AST ----------------------------------------------------------------------


def test_precedencia_y_asociatividad():
    prog = parse("print(1 - 2 - 3 * 4 / 5);")
    e = prog.body[0].value
    # (1 - 2) - ((3 * 4) / 5)
    assert A.expr_str(e) == "((1 - 2) - ((3 * 4) / 5))"


def test_menos_unario_y_parentesis():
    assert A.expr_str(parse("print(-(a + -b) * c);").body[0].value) == "(-(a + -b) * c)"


def test_relacional_es_el_nivel_mas_bajo():
    assert A.expr_str(parse("print(a + 1 <= b * 2);").body[0].value) == "((a + 1) <= (b * 2))"


def test_else_if_encadenado():
    prog = parse("if (a) { } else if (b) { } else { x = 1; }")
    s = prog.body[0]
    assert isinstance(s, A.If) and isinstance(s.orelse, A.If)
    assert isinstance(s.orelse.orelse, A.Block)


def test_posiciones_en_el_ast():
    prog = parse("int x = 1;\n  x = x + 2;")
    assert (prog.body[0].line, prog.body[0].col) == (1, 5)
    assert (prog.body[1].line, prog.body[1].col) == (2, 3)


def test_programa_vacio():
    assert parse("").body == []
    assert parse("// nada\n").body == []


def test_programas_largos_y_anidados_no_agotan_la_pila():
    long = "int x = 0;\n" + "x = x + 1;\n" * 20000
    assert len(parse(long).body) == 20001
    deep = "int x = 0;\n" + "if (x == 0) {\n" * 400 + "x = 1;\n" + "}\n" * 400
    assert len(parse(deep).body) == 2
    expr = "print(" + "(" * 300 + "1" + ")" * 300 + ");"
    assert isinstance(parse(expr).body[0].value, A.Num)


# --- Autómata de pila -----------------------------------------------------------


def test_traza_del_automata_de_pila():
    trace: list[TraceRow] = []
    Parser().parse_tree(tokenize("print(x);"), trace)
    assert trace[0].stack == "$ Programa" and trace[0].input == "print ( id ) ; $"
    assert trace[-1].action == "aceptar"
    assert any(r.action.startswith("(20) Imprimir") for r in trace)


def test_cantidad_de_pasos_lineal():
    p = Parser()
    steps = []
    for n in (100, 200, 300):
        p.parse(tokenize("x = 1;\n" * n))
        steps.append(p.steps)
    # Diferencias constantes: pasos(n) = a·n + b exactamente.
    assert steps[2] - steps[1] == steps[1] - steps[0] > 0


# --- Errores sintácticos ---------------------------------------------------------


@pytest.mark.parametrize("prog", programs("error_sintactico"), ids=lambda p: p.id)
def test_programas_con_error_sintactico(prog):
    with pytest.raises(ParseError) as exc:
        parse(prog.source)
    assert (exc.value.linea, exc.value.columna) == prog.error_pos


@pytest.mark.parametrize(
    "src, fragment",
    [
        ("int x = 1\nprint(x);", "se esperaba un operador o ';'"),
        ("while (x) { x = 1;", "se esperaba una sentencia o '}', pero se encontró fin de archivo"),
        ("int = 3;", "se esperaba un identificador, pero se encontró '='"),
        ("x = ;", "se esperaba una expresión"),
        ("print x;", "se esperaba '('"),
        ("}", "se esperaba una sentencia o fin de archivo"),
        ("if (x) { } else x = 1;", "se esperaba 'if' o '{'"),
    ],
)
def test_mensajes_de_error(src, fragment):
    with pytest.raises(ParseError, match=fragment.replace("(", r"\(").replace("{", r"\{").replace("}", r"\}")):
        parse(src)


@pytest.mark.parametrize("prog", programs("validos", "error_semantico", "bucle_infinito"), ids=lambda p: p.id)
def test_programas_sintacticamente_validos(prog):
    parse(prog.source)


# --- Recuperación en modo pánico --------------------------------------------------


def errores(src: str) -> list[tuple[int, int]]:
    with pytest.raises(ParseError) as exc:
        parse(src)
    return [(e.linea, e.columna) for e in exc.value.errores]


def test_informa_todos_los_errores_independientes():
    src = "int x = 1\nprint(x +);\nwhile (x < 3) {\n    x = x + * 2;\n}\nprint(x;\n"
    assert errores(src) == [(2, 1), (2, 10), (4, 13), (6, 8)]


def test_el_primer_error_es_el_que_se_lanza():
    with pytest.raises(ParseError) as exc:
        parse("int x = 1\nint y = ;")
    assert exc.value is exc.value.errores[0]
    assert (exc.value.linea, exc.value.columna) == (2, 1)


def test_un_solo_error_no_produce_cascada():
    # Basura que sobra al final de una sentencia: se descarta y se sigue.
    assert errores("int x = 1;\nelse { x = 2; }\nprint(x);") == [(2, 1)]
    assert errores("/* comentario */\nint x = 1;") == [(1, 1)]


def test_se_callan_los_errores_cercanos_al_anterior():
    # Dos errores a menos de SILENCIO tokens: solo se informa el primero.
    assert errores("x = = = 1;") == [(1, 5)]


def test_falta_de_parentesis_se_repara_por_insercion():
    assert errores("if x > 0 {\n    print(x);\n}\nint = 2;") == [(1, 4), (1, 10), (4, 5)]


@pytest.mark.parametrize("prog", programs("error_sintactico"), ids=lambda p: p.id)
def test_la_recuperacion_termina_y_conserva_el_primer_error(prog):
    errs = errores(prog.source)
    assert errs[0] == prog.error_pos
    assert errs == sorted(errs)
