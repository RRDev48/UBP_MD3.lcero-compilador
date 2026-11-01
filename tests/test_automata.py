"""Tests de la construcción ER → AFN-ε → AFD → AFD mínimo.

Además de casos puntuales, se verifica con algoritmos independientes que:
  * el AFD mínimo es equivalente al AFD de subconjuntos (autómata producto),
  * no tiene estados equivalentes (algoritmo de Moore, distinto de Hopcroft),
  * el lexer basado en la matriz δ produce los mismos tokens que simular el
    AFN-ε directamente, sobre miles de cadenas aleatorias.
"""

from __future__ import annotations

import random

import pytest

from lcero.alphabet import CLASS_INDEX, CLASSES, REPRESENTATIVE, class_index
from lcero.automata import (
    NFA, build_combined_nfa, equivalent, hopcroft_minimize, moore_partition, subset_construction,
)
from lcero.errors import LexicalError
from lcero.lexer import Lexer, lexer_automata
from lcero.regex import alt, plus, seq, star, sym
from lcero.tokens import SKIPPED, TokenType as T


# --- Construcciones sobre un ejemplo de libro ---------------------------------


def _accepts(dfa, word: str) -> bool:
    q = dfa.start
    for ch in word:
        q = dfa.trans[q][dfa.alphabet.index(ch)]
    return q in dfa.accepting


def test_ejemplo_clasico_a_o_b_estrella_abb():
    # (a|b)*abb: el AFD mínimo clásico tiene 4 estados (sin sumidero, porque es total).
    r = seq(star(alt(sym("a"), sym("b"))), sym("a"), sym("b"), sym("b"))
    nfa = build_combined_nfa([(r, "ok")])
    dfa = subset_construction(nfa, ("a", "b"))
    mdfa, _ = hopcroft_minimize(dfa)
    assert mdfa.n_states == 4
    assert equivalent(dfa, mdfa)
    for w in ["abb", "aabb", "babb", "ababb"]:
        assert _accepts(mdfa, w)
    for w in ["", "a", "ab", "abba", "bbb"]:
        assert not _accepts(mdfa, w)


def test_thompson_acota_estados():
    # |Q_N| ≤ 2·|r|: cada nodo de la ER agrega a lo sumo dos estados.
    r = plus(alt(sym("a"), sym("b")))  # Cat(Alt(a,b), Star(Alt(a,b))) → 7 nodos
    nfa = NFA()
    from lcero.automata import thompson
    thompson(nfa, r)
    assert nfa.n_states <= 2 * 7


def test_prioridad_resuelve_empates():
    r = seq(sym("a"), sym("b"))
    nfa = build_combined_nfa([(r, "PRIMERO"), (r, "SEGUNDO")])
    dfa = subset_construction(nfa, ("a", "b"))
    q = dfa.run([0, 1])
    assert dfa.accepting[q] == "PRIMERO"


# --- Propiedades del AFD del lexer --------------------------------------------


def test_cantidades_de_estados():
    a = lexer_automata()
    assert a.nfa.n_states > a.dfa.n_states > a.min_dfa.n_states
    assert a.min_dfa.n_states == 42


def test_minimo_es_equivalente_al_de_subconjuntos():
    a = lexer_automata()
    assert equivalent(a.dfa, a.min_dfa)


def test_minimo_no_tiene_estados_equivalentes():
    m = lexer_automata().min_dfa
    blocks = moore_partition(m)
    assert len(blocks) == m.n_states
    assert all(len(b) == 1 for b in blocks)


def test_hopcroft_coincide_con_moore_sobre_el_afd_sin_minimizar():
    dfa = lexer_automata().dfa
    _, hop_blocks = hopcroft_minimize(dfa)
    moore_blocks = moore_partition(dfa)
    assert sorted(map(sorted, hop_blocks)) == sorted(map(sorted, moore_blocks))


def test_delta_es_total_y_hay_un_unico_sumidero():
    m = lexer_automata().min_dfa
    assert all(len(row) == len(CLASSES) for row in m.trans)
    assert all(0 <= t < m.n_states for row in m.trans for t in row)
    sinks = [q for q, row in enumerate(m.trans) if q not in m.accepting and all(t == q for t in row)]
    assert sinks == [m.n_states - 1]


def test_todos_los_estados_son_alcanzables_y_coaccesibles():
    m = lexer_automata().min_dfa
    from lcero.automata import shortest_witnesses
    assert len(shortest_witnesses(m)) == m.n_states
    # Todo estado salvo el sumidero puede llegar a un estado final.
    alive = set(m.accepting)
    changed = True
    while changed:
        changed = False
        for q, row in enumerate(m.trans):
            if q not in alive and any(t in alive for t in row):
                alive.add(q)
                changed = True
    assert alive == set(range(m.n_states)) - {m.sink}


def test_cada_token_tiene_un_estado_final():
    m = lexer_automata().min_dfa
    labels = set(m.accepting.values())
    assert labels == set(T) - {T.EOF}


# --- Oráculo: simulación directa del AFN-ε ------------------------------------


def nfa_tokenize(nfa: NFA, source: str) -> list[tuple[T, str]]:
    """Lexer de referencia que simula el AFN-ε con conjuntos de estados (sin AFD)."""
    out, pos = [], 0
    while pos < len(source):
        S = nfa.epsilon_closure({nfa.start})
        i, last = pos, None
        while i < len(source) and S:
            S = nfa.epsilon_closure(nfa.move(S, CLASSES[class_index(source[i])]))
            i += 1
            finals = [nfa.accepting[s] for s in S if s in nfa.accepting]
            if finals:
                last = (min(finals, key=lambda pl: pl[0])[1], i)
        if last is None:
            raise LexicalError("oráculo", 0, 0)
        tt, end = last
        if tt not in SKIPPED:
            out.append((tt, source[pos:end]))
        pos = end
    return out


FUZZ_ALPHABET = list("intfelswhpr" "xyz_AQ" "0179" "+-*/%=!<>(){};" "  \n\t") + ["while", "print", "int", "else", "//"]


@pytest.mark.parametrize("seed", range(5))
def test_lexer_coincide_con_simulacion_del_afn(seed):
    rng = random.Random(seed)
    nfa = lexer_automata().nfa
    lexer = Lexer()
    for _ in range(400):
        src = "".join(rng.choice(FUZZ_ALPHABET) for _ in range(rng.randint(0, 25)))
        try:
            expected = nfa_tokenize(nfa, src)
        except LexicalError:
            with pytest.raises(LexicalError):
                lexer.tokenize(src)
            continue
        got = [(t.type, t.lexeme) for t in lexer.tokenize(src)[:-1]]
        assert got == expected, src


def test_representantes_pertenecen_a_su_clase():
    for c, ch in REPRESENTATIVE.items():
        assert class_index(ch) == CLASS_INDEX[c]
