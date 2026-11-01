"""Tests de la RI y de la asignación de registros (Fases 4 y 8)."""

from __future__ import annotations

import random

import pytest

from lcero.compiler import compile_source
from lcero.ir import format_tac, generate
from lcero.lexer import tokenize
from lcero.parser import parse
from lcero.reductions import PETERSEN, complete, cycle, graph_to_lcero, vertex_subgraph
from lcero.regalloc import (
    InterferenceGraph, allocate, chaitin_color, exact_coloring, interference_graph, liveness, spill_costs,
)
from lcero.semantic import analyze

from programas_util import programs


def tac(src: str):
    prog = parse(tokenize(src))
    analyze(prog)
    return generate(prog)


# --- Código de tres direcciones ---------------------------------------------------


def test_ri_de_un_while():
    code = format_tac(tac("int n = 3;\nwhile (n > 0) { n = n - 1; }\nprint(n);"))
    assert code == "\n".join([
        "    n = 3", "L1:", "    $t1 = n > 0", "    ifz $t1 goto L2", "    n = n - 1",
        "    goto L1", "L2:", "    print n", "    halt",
    ])


def test_plegado_de_constantes():
    code = tac("int x = 2 * (3 + 4) - -1;\nprint(x);")
    assert str(code[0]) == "x = 15"


def test_division_por_cero_constante_no_se_pliega():
    code = tac("print(1 / 0);")
    assert str(code[0]) == "$t1 = 1 / 0"


def test_escritura_directa_en_el_destino():
    assert [str(i) for i in tac("int a = 1;\nint b = a * a + 1;")[:3]] == ["a = 1", "$t1 = a * a", "b = $t1 + 1"]


def test_ri_y_profundidad_de_bucles():
    code = tac("int i = 0;\nwhile (i < 2) { int j = 0; while (j < 2) { j = j + 1; } i = i + 1; }")
    depths = {str(ins): ins.depth for ins in code}
    assert depths["j = j + 1"] == 2 and depths["i = i + 1"] == 1 and depths["i = 0"] == 0


# --- Vivacidad e interferencia ----------------------------------------------------


def test_vivacidad():
    code = tac("int a = 1;\nint b = 2;\nint c = a + b;\nprint(c);")
    live = liveness(code)
    assert live.live_out[0] == {"a"}
    assert live.live_out[1] == {"a", "b"}
    assert live.live_out[2] == {"c"}
    assert live.live_in[0] == set()


def test_vivacidad_en_bucles():
    code = tac("int s = 0;\nint i = 3;\nwhile (i > 0) { s = s + i; i = i - 1; }\nprint(s);")
    live = liveness(code)
    loop_head = next(k for k, ins in enumerate(code) if ins.op == "label")
    assert live.live_in[loop_head] == {"s", "i"}


def test_copia_no_interfiere_con_su_origen():
    code = tac("int a = 1;\nint b = a;\nprint(a + b);")
    g = interference_graph(code, liveness(code))
    # b = a es una copia: a sigue viva, pero b tiene el mismo valor, así que
    # pueden compartir registro. Después, nadie se define con el otro vivo.
    assert "b" not in g.neighbors("a")


def assert_valid_allocation(alloc):
    """Ningún par de nombres que interfieren comparte registro."""
    code = alloc.code
    live = liveness(code)
    for i, ins in enumerate(code):
        for d in ins.defs():
            for v in live.live_out[i]:
                if v != d and not (ins.op == "copy" and v == ins.a):
                    assert alloc.register[d] != alloc.register[v], (str(ins), d, v)
    assert all(0 <= r < alloc.k for r in alloc.register.values())


@pytest.mark.parametrize("k", [2, 3, 4, 8])
@pytest.mark.parametrize("prog", programs("validos"), ids=lambda p: p.id)
def test_asignacion_valida(prog, k):
    alloc = compile_source(prog.source, k).allocation
    assert_valid_allocation(alloc)


def test_con_muchos_registros_no_hay_derrames():
    for prog in programs("validos"):
        assert compile_source(prog.source, 16).allocation.slots == {}


def test_menos_de_dos_registros_es_error():
    with pytest.raises(ValueError):
        allocate(tac("print(1);"), 1)


def test_temporal_de_rango_minimo_no_se_derrama():
    code = tac("int n = 5;\nwhile (n > 1) { n = n - 1; }")
    g = interference_graph(code, liveness(code))
    cost = spill_costs(code, g)
    assert cost[g.index["$t1"]] == float("inf")
    assert cost[g.index["n"]] < float("inf")


def test_costo_pondera_bucles():
    code = tac("int a = 1;\nint b = 1;\nwhile (b < 9) { b = b + 1; }\nprint(a + b);")
    g = interference_graph(code, liveness(code))
    cost = spill_costs(code, g)
    assert cost[g.index["b"]] > 10 * cost[g.index["a"]] / 2


# --- Reducción k-COLOREO ≤p ASIGNACIÓN DE REGISTROS -------------------------------


GRAPHS = {"C5": (5, cycle(5)), "C4": (4, cycle(4)), "K4": (4, complete(4)), "K5": (5, complete(5)),
          "Petersen": (10, PETERSEN)}


@pytest.mark.parametrize("name", GRAPHS)
def test_interferencia_de_pg_es_exactamente_g(name):
    n, edges = GRAPHS[name]
    code = tac(graph_to_lcero(n, edges))
    g = interference_graph(code, liveness(code))
    assert vertex_subgraph(g, n) == {frozenset(e) for e in edges}


def test_reduccion_con_grafos_aleatorios():
    rng = random.Random(7)
    for _ in range(30):
        n = rng.randint(2, 9)
        edges = [(i, j) for i in range(n) for j in range(i + 1, n) if rng.random() < 0.4]
        code = tac(graph_to_lcero(n, edges))
        g = interference_graph(code, liveness(code))
        assert vertex_subgraph(g, n) == {frozenset(e) for e in edges}


def _graph(n: int, edges) -> list[set[int]]:
    adj = [set() for _ in range(n)]
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    return adj


def test_coloreo_exacto():
    assert exact_coloring(_graph(4, complete(4)), 3)[0] is None
    assert exact_coloring(_graph(4, complete(4)), 4)[0] is not None
    assert exact_coloring(_graph(5, cycle(5)), 2)[0] is None
    assert exact_coloring(_graph(10, PETERSEN), 3)[0] is not None


def test_chaitin_derrama_en_petersen_aunque_es_3_coloreable():
    adj = _graph(10, PETERSEN)
    g = InterferenceGraph([f"v{i}" for i in range(10)], {f"v{i}": i for i in range(10)}, adj)
    res = chaitin_color(g, 3, [1.0] * 10)
    assert res.spilled  # la heurística se bloquea: todos tienen grado 3
    colors, _ = exact_coloring(adj, 3)
    assert colors is not None and all(colors[u] != colors[v] for u, v in PETERSEN)


def test_chaitin_colorea_c4_con_dos_colores_sin_bloquearse_solo_si_k_3():
    n, edges = GRAPHS["C4"]
    g = InterferenceGraph([f"v{i}" for i in range(n)], {f"v{i}": i for i in range(n)}, _graph(n, edges))
    assert chaitin_color(g, 2, [1.0] * n).spilled  # C4 es 2-coloreable pero la heurística no lo ve
    assert not chaitin_color(g, 3, [1.0] * n).spilled


def test_si_chaitin_no_derrama_el_coloreo_es_valido():
    rng = random.Random(3)
    for _ in range(200):
        n = rng.randint(1, 12)
        edges = [(i, j) for i in range(n) for j in range(i + 1, n) if rng.random() < 0.35]
        adj = _graph(n, edges)
        g = InterferenceGraph([str(i) for i in range(n)], {str(i): i for i in range(n)}, adj)
        k = rng.randint(2, 5)
        res = chaitin_color(g, k, [1.0] * n)
        if not res.spilled:
            assert all(res.colors[u] != res.colors[v] for u, v in edges)
            assert exact_coloring(adj, k)[0] is not None  # coherente con el algoritmo exacto
