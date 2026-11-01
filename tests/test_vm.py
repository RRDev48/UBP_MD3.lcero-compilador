"""Tests de la máquina virtual y del compilador completo (Fases 4, 5 y 6)."""

from __future__ import annotations

import random

import pytest

from lcero.compiler import compile_source, run_source
from lcero.errors import LCeroError, LexicalError, ParseError, SemanticError, VMError
from lcero.turing import (
    BINARY_INCREMENT, BUSY_BEAVER_2, BUSY_BEAVER_3, PING_PONG, RUNAWAY, L, N, R, TuringMachine, simulate, to_lcero,
)
from lcero.vm import HALT, Imm, Instr, Machine, Reg

from programas_util import programs

ERRORS = {"léxico": LexicalError, "sintáctico": ParseError, "semántico": SemanticError}


# --- Función de transición ----------------------------------------------------------


def test_delta_instruccion_por_instruccion():
    prog = [
        Instr("mov", 0, Imm(7)),
        Instr("add", 1, Reg(0), Imm(5)),
        Instr("jz", a=Imm(0), target=4),
        Instr("print", a=Imm(-1)),
        Instr("print", a=Reg(1)),
        Instr("halt"),
    ]
    m = Machine(prog, 2)
    c = m.initial()
    m.delta(c)
    assert (c.q, c.R) == (1, [7, 0])
    m.delta(c)
    assert (c.q, c.R) == (2, [7, 12])
    m.delta(c)
    assert c.q == 4  # saltó
    m.delta(c)
    m.delta(c)
    assert c.q == HALT and c.out == [12] and c.steps == 5


def test_el_cabezal_se_mueve_una_celda_por_paso():
    prog = [Instr("store", a=Imm(9), addr=3), Instr("load", 0, addr=0), Instr("halt")]
    m = Machine(prog, 1)
    c = m.initial()
    positions = []
    while c.q != HALT:
        m.delta(c)
        positions.append((c.q, c.h))
    # 3 pasos para ir de 0 a 3, 1 para escribir, 3 para volver, 1 para leer, 1 halt
    assert positions == [(0, 1), (0, 2), (0, 3), (1, 3), (1, 2), (1, 1), (1, 0), (2, 0), (HALT, 0)]
    assert c.tape == {3: 9} and c.R == [0]


def test_division_y_resto_truncados():
    r = run_source("int a = -7;\nint b = 2;\nprint(a / b);\nprint(a % b);\nprint(7 / -2);\nprint(7 % -2);")
    assert r.output == [-3, -1, -3, 1]


def test_enteros_sin_cota():
    r = run_source("int x = 1;\nint i = 0;\nwhile (i < 100) { x = x * 2; i = i + 1; }\nprint(x);")
    assert r.output == [2 ** 100]


def test_division_por_cero_en_ejecucion():
    with pytest.raises(VMError, match=r"\(línea 3\): división por cero"):
        run_source("int a = 1;\nint b = a - 1;\nprint(a / b);")
    with pytest.raises(VMError, match="resto por cero"):
        run_source("print(5 % 0);")


def test_traza_de_configuraciones():
    trace: list[str] = []
    compile_source("print(1 + 2);", 2).machine().run(trace=trace)
    assert trace[0].startswith("(q0, R=[0, 0], h=0")
    assert trace[-1].startswith("(q_f")


# --- Compilador completo ---------------------------------------------------------------


@pytest.mark.parametrize("k", [2, 3, 4, 8])
@pytest.mark.parametrize("prog", programs("validos"), ids=lambda p: p.id)
def test_programas_validos_producen_la_salida_esperada(prog, k):
    r = run_source(prog.source, k, max_steps=10_000_000)
    assert r.halted
    assert tuple(r.output) == prog.expected_output


@pytest.mark.parametrize(
    "prog", programs("error_lexico", "error_sintactico", "error_semantico"), ids=lambda p: p.id
)
def test_cada_error_lo_detecta_su_fase(prog):
    with pytest.raises(LCeroError) as exc:
        compile_source(prog.source)
    assert type(exc.value) is ERRORS[prog.error_phase]
    assert (exc.value.linea, exc.value.columna) == prog.error_pos


@pytest.mark.parametrize("prog", programs("bucle_infinito"), ids=lambda p: p.id)
def test_bucles_infinitos_no_se_detienen_en_el_presupuesto(prog):
    # Semidecisión: solo podemos afirmar que no se detuvo en N pasos (Fase 6).
    r = run_source(prog.source, 3, max_steps=200_000)
    assert not r.halted and r.steps == 200_000


# --- Máquinas de Turing en L-Cero (Turing-completitud y reducción) -----------------


@pytest.mark.parametrize(
    "tm, w",
    [(BUSY_BEAVER_2, []), (BUSY_BEAVER_3, []), (BINARY_INCREMENT, [2, 1, 2, 2]), (BINARY_INCREMENT, [2, 2, 2])],
    ids=["BB2", "BB3", "inc-1011", "inc-111"],
)
def test_simulacion_de_mt_coincide_con_la_referencia(tm, w):
    ref = simulate(tm, w, 10_000)
    r = run_source(to_lcero(tm, w), 4, max_steps=1_000_000)
    assert ref.halted and r.halted
    assert r.output == [ref.ones, ref.steps]


@pytest.mark.parametrize("tm", [RUNAWAY, PING_PONG], ids=lambda t: t.name)
def test_mt_que_no_para_da_programa_que_no_termina(tm):
    assert not simulate(tm, [], 10_000).halted
    assert not run_source(to_lcero(tm, []), 4, max_steps=100_000).halted


def random_tm(rng: random.Random) -> TuringMachine:
    states = tuple("ABC"[: rng.randint(1, 3)])
    delta = {}
    for q in states:
        for s in range(2):
            if rng.random() < 0.85:
                delta[(q, s)] = (rng.choice(states + ("H",)), rng.randint(0, 1), rng.choice((L, R, N)))
    return TuringMachine("aleatoria", states, 2, delta, "A")


def test_reduccion_halting_con_maquinas_aleatorias():
    """M se detiene en ≤ n pasos ⟺ P_M se detiene; si M no para en n pasos, P_M tampoco en 5n pasos de VM."""
    rng = random.Random(11)
    n = 300
    halting = looping = 0
    for _ in range(60):
        tm = random_tm(rng)
        ref = simulate(tm, [], n)
        source = to_lcero(tm, [])
        if ref.halted:
            r = run_source(source, 3, max_steps=2_000_000)
            assert r.halted and r.output == [ref.ones, ref.steps]
            halting += 1
        else:
            # Cada paso de M cuesta al menos 5 transiciones de la VM, así que en
            # 5n pasos la VM simuló a lo sumo n pasos de M: no puede haber parado.
            assert not run_source(source, 3, max_steps=5 * n).halted
            looping += 1
    assert halting and looping  # se probaron ambos casos
