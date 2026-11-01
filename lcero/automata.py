"""Autómatas finitos construidos desde cero.

Cadena de construcción del analizador léxico (Fase 1):

    ER de cada token ──Thompson──▶ AFN-ε ──subconjuntos──▶ AFD ──Hopcroft──▶ AFD mínimo

Definiciones formales usadas en el informe:

* AFN-ε  N = (Q_N, Σ, Δ, q0, F_N),  Δ : Q_N × (Σ ∪ {ε}) → P(Q_N)
* AFD    M = (Q, Σ, δ, q0, F),      δ : Q × Σ → Q  (total: incluye el estado sumidero)

Como un lexer distingue *qué* token se reconoció, cada autómata lleva además
una función de etiquetado λ : F → Tokens. En el AFD, λ(S) es el token de
mayor prioridad entre los estados finales del AFN contenidos en S (por eso
``while`` es palabra reservada y no identificador).
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .regex import Alt, Cat, Eps, Regex, Star, Sym

EPS = None  # etiqueta de las transiciones ε

# ---------------------------------------------------------------------------
# AFN-ε y construcción de Thompson
# ---------------------------------------------------------------------------


class NFA:
    """AFN-ε. Los estados son enteros 0..n-1."""

    def __init__(self) -> None:
        self.edges: list[list[tuple[str | None, int]]] = []
        self.start: int = 0
        #: estado final -> (prioridad, etiqueta). Menor número = mayor prioridad.
        self.accepting: dict[int, tuple[int, object]] = {}

    @property
    def n_states(self) -> int:
        return len(self.edges)

    def new_state(self) -> int:
        self.edges.append([])
        return len(self.edges) - 1

    def add(self, src: int, symbol: str | None, dst: int) -> None:
        self.edges[src].append((symbol, dst))

    def epsilon_closure(self, states: Iterable[int]) -> frozenset[int]:
        """ε-clausura(T): estados alcanzables desde T usando solo transiciones ε."""
        closure = set(states)
        stack = list(closure)
        while stack:
            s = stack.pop()
            for symbol, t in self.edges[s]:
                if symbol is EPS and t not in closure:
                    closure.add(t)
                    stack.append(t)
        return frozenset(closure)

    def move(self, states: Iterable[int], symbol: str) -> set[int]:
        """mover(T, a): estados alcanzables desde T con una transición por ``a``."""
        return {t for s in states for sym, t in self.edges[s] if sym == symbol}


def thompson(nfa: NFA, r: Regex) -> tuple[int, int]:
    """Agrega a ``nfa`` el fragmento de Thompson para ``r``.

    Devuelve (inicial, final) del fragmento. Cada caso agrega a lo sumo dos
    estados, así que |Q_N| ≤ 2·|r|.
    """
    match r:
        case Sym(c):
            s, t = nfa.new_state(), nfa.new_state()
            nfa.add(s, c, t)
            return s, t
        case Eps():
            s, t = nfa.new_state(), nfa.new_state()
            nfa.add(s, EPS, t)
            return s, t
        case Cat(a, b):
            s1, e1 = thompson(nfa, a)
            s2, e2 = thompson(nfa, b)
            nfa.add(e1, EPS, s2)
            return s1, e2
        case Alt(a, b):
            s, t = nfa.new_state(), nfa.new_state()
            s1, e1 = thompson(nfa, a)
            s2, e2 = thompson(nfa, b)
            nfa.add(s, EPS, s1)
            nfa.add(s, EPS, s2)
            nfa.add(e1, EPS, t)
            nfa.add(e2, EPS, t)
            return s, t
        case Star(a):
            s, t = nfa.new_state(), nfa.new_state()
            s1, e1 = thompson(nfa, a)
            nfa.add(s, EPS, s1)
            nfa.add(s, EPS, t)
            nfa.add(e1, EPS, s1)
            nfa.add(e1, EPS, t)
            return s, t
    raise TypeError(f"nodo de ER desconocido: {r!r}")


def build_combined_nfa(patterns: Sequence[tuple[Regex, object]]) -> NFA:
    """AFN-ε de la unión de todos los tokens.

    Un estado inicial nuevo con una transición ε al inicio de cada fragmento.
    El orden de ``patterns`` define la prioridad (el primero gana).
    """
    nfa = NFA()
    nfa.start = nfa.new_state()
    for priority, (regex, label) in enumerate(patterns):
        s, e = thompson(nfa, regex)
        nfa.add(nfa.start, EPS, s)
        nfa.accepting[e] = (priority, label)
    return nfa


# ---------------------------------------------------------------------------
# AFD
# ---------------------------------------------------------------------------


@dataclass
class DFA:
    """AFD total M = (Q, Σ, δ, q0, F) con etiquetado λ : F → Tokens.

    ``trans[q][a]`` es δ(q, a) usando el índice de la clase ``a`` en
    ``alphabet``. ``accepting`` representa F y λ a la vez.
    """

    alphabet: tuple[str, ...]
    start: int
    trans: list[list[int]]
    accepting: dict[int, object]
    #: Para cada estado, el subconjunto de estados del AFN que representa
    #: (solo en el AFD salido de la construcción por subconjuntos).
    subsets: list[frozenset[int]] = field(default_factory=list)

    @property
    def n_states(self) -> int:
        return len(self.trans)

    @property
    def sink(self) -> int | None:
        """Estado sumidero (no final y con todas sus transiciones a sí mismo)."""
        for q, row in enumerate(self.trans):
            if q not in self.accepting and all(t == q for t in row):
                return q
        return None

    def run(self, word: Sequence[int]) -> int:
        """δ*(q0, w) para una palabra dada como índices de clase."""
        q = self.start
        for a in word:
            q = self.trans[q][a]
        return q


def subset_construction(nfa: NFA, alphabet: Sequence[str]) -> DFA:
    """Construcción por subconjuntos (determinización).

    Cada estado del AFD es un conjunto de estados del AFN cerrado por ε.
    El conjunto vacío aparece de forma natural y es el estado sumidero, así
    que δ queda total. Solo se generan los estados alcanzables desde q0.
    """
    alphabet = tuple(alphabet)
    start = nfa.epsilon_closure({nfa.start})
    index: dict[frozenset[int], int] = {start: 0}
    subsets: list[frozenset[int]] = [start]
    trans: list[list[int]] = []

    i = 0
    while i < len(subsets):  # cola implícita: los estados se procesan en orden de creación
        S = subsets[i]
        row = []
        for a in alphabet:
            T = nfa.epsilon_closure(nfa.move(S, a))
            if T not in index:
                index[T] = len(subsets)
                subsets.append(T)
            row.append(index[T])
        trans.append(row)
        i += 1

    accepting: dict[int, object] = {}
    for q, S in enumerate(subsets):
        finals = [nfa.accepting[s] for s in S if s in nfa.accepting]
        if finals:
            accepting[q] = min(finals, key=lambda pl: pl[0])[1]
    return DFA(alphabet, 0, trans, accepting, subsets)


def hopcroft_minimize(dfa: DFA) -> tuple[DFA, list[frozenset[int]]]:
    """Minimización de Hopcroft (refinamiento de particiones), O(k·n·log n).

    Partición inicial: un bloque con los estados no finales y un bloque por
    cada etiqueta de token (dos estados que aceptan tokens distintos nunca
    son equivalentes). Luego se refina con los "separadores" (A, a): un
    bloque Y se parte si algunos de sus estados van con ``a`` a A y otros no.

    Devuelve el AFD mínimo y, para cada estado nuevo, el bloque de estados
    originales que lo forma. El AFD mínimo se renumera por BFS desde q0
    (recorriendo Σ en orden) y el sumidero queda al final.
    """
    n, k = dfa.n_states, len(dfa.alphabet)

    # Transiciones inversas: inv[a][q] = { p | δ(p, a) = q }
    inv: list[list[list[int]]] = [[[] for _ in range(n)] for _ in range(k)]
    for p, row in enumerate(dfa.trans):
        for a, q in enumerate(row):
            inv[a][q].append(p)

    groups: dict[object, set[int]] = defaultdict(set)
    for q in range(n):
        groups[dfa.accepting.get(q)].add(q)
    partition: list[frozenset[int]] = [frozenset(g) for g in groups.values()]
    worklist: list[frozenset[int]] = list(partition)

    while worklist:
        A = worklist.pop()
        for a in range(k):
            X = {p for q in A for p in inv[a][q]}  # predecesores de A por a
            if not X:
                continue
            refined: list[frozenset[int]] = []
            for Y in partition:
                Y1 = Y & X
                if not Y1 or len(Y1) == len(Y):
                    refined.append(Y)
                    continue
                Y2 = Y - X
                refined += [Y1, Y2]
                if Y in worklist:
                    worklist.remove(Y)
                    worklist += [Y1, Y2]
                else:
                    worklist.append(Y1 if len(Y1) <= len(Y2) else Y2)
            partition = refined

    block_of = {q: b for b, Y in enumerate(partition) for q in Y}
    return _quotient(dfa, partition, block_of)


def _quotient(
    dfa: DFA, partition: list[frozenset[int]], block_of: dict[int, int]
) -> tuple[DFA, list[frozenset[int]]]:
    """Construye el AFD cociente M/≡ y lo renumera de forma canónica."""
    k = len(dfa.alphabet)

    def block_trans(b: int) -> list[int]:
        rep = next(iter(partition[b]))
        return [block_of[dfa.trans[rep][a]] for a in range(k)]

    sink_block = None
    for b, Y in enumerate(partition):
        rep = next(iter(Y))
        if rep not in dfa.accepting and all(t == b for t in block_trans(b)):
            sink_block = b

    # Renumeración BFS desde el inicial; el sumidero va al final.
    order: list[int] = []
    seen = {block_of[dfa.start]}
    queue = deque([block_of[dfa.start]])
    while queue:
        b = queue.popleft()
        if b != sink_block:
            order.append(b)
        for t in block_trans(b):
            if t not in seen:
                seen.add(t)
                queue.append(t)
    if sink_block is not None and sink_block in seen:
        order.append(sink_block)

    new_id = {b: i for i, b in enumerate(order)}
    trans = [[new_id[t] for t in block_trans(b)] for b in order]
    accepting = {}
    for b in order:
        rep = next(iter(partition[b]))
        if rep in dfa.accepting:
            accepting[new_id[b]] = dfa.accepting[rep]
    blocks = [partition[b] for b in order]
    return DFA(dfa.alphabet, new_id[block_of[dfa.start]], trans, accepting), blocks


# ---------------------------------------------------------------------------
# Verificaciones independientes (usadas por los tests y el informe)
# ---------------------------------------------------------------------------


def moore_partition(dfa: DFA) -> list[set[int]]:
    """Clases de equivalencia de Myhill-Nerode calculadas con el algoritmo de Moore.

    Es un algoritmo distinto de Hopcroft: se usa para verificar que el AFD
    minimizado no tiene dos estados equivalentes.
    """
    cls = {q: repr(dfa.accepting.get(q)) for q in range(dfa.n_states)}
    while True:
        signature = {q: (cls[q], tuple(cls[t] for t in dfa.trans[q])) for q in range(dfa.n_states)}
        ids: dict[tuple, int] = {}
        new_cls = {q: ids.setdefault(signature[q], len(ids)) for q in range(dfa.n_states)}
        if len(set(new_cls.values())) == len(set(cls.values())):
            break
        cls = new_cls  # type: ignore[assignment]
    groups: dict[object, set[int]] = defaultdict(set)
    for q, c in new_cls.items():
        groups[c].add(q)
    return list(groups.values())


def equivalent(d1: DFA, d2: DFA) -> bool:
    """¿Aceptan d1 y d2 el mismo lenguaje con las mismas etiquetas?

    Recorre el autómata producto: son equivalentes si ningún par alcanzable
    (p, q) tiene etiquetas distintas.
    """
    assert d1.alphabet == d2.alphabet
    start = (d1.start, d2.start)
    seen = {start}
    queue = deque([start])
    while queue:
        p, q = queue.popleft()
        if d1.accepting.get(p) != d2.accepting.get(q):
            return False
        for a in range(len(d1.alphabet)):
            nxt = (d1.trans[p][a], d2.trans[q][a])
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return True


def shortest_witnesses(dfa: DFA) -> dict[int, list[int]]:
    """Para cada estado, la palabra más corta (en orden de Σ) que lleva a él desde q0."""
    paths: dict[int, list[int]] = {dfa.start: []}
    queue = deque([dfa.start])
    while queue:
        q = queue.popleft()
        for a, t in enumerate(dfa.trans[q]):
            if t not in paths:
                paths[t] = paths[q] + [a]
                queue.append(t)
    return paths
