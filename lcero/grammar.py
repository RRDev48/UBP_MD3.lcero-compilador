"""Gramáticas libres de contexto: First, Follow y tabla LL(1).

Implementación genérica (sirve para cualquier GLC en BNF sin ε explícito:
una producción A → ε se escribe con lado derecho vacío). La Fase 2 la usa
con la gramática de L-Cero (``lcero_grammar.py``).

Definiciones (para un símbolo X y una cadena α de símbolos):

* First(α) = { a ∈ T | α ⇒* aβ } ∪ { ε si α ⇒* ε }
* Follow(A) = { a ∈ T ∪ {$} | S$ ⇒* αAaβ }
* Predict(A → α) = (First(α) − {ε}) ∪ (Follow(A) si ε ∈ First(α))

La gramática es LL(1) si, para cada no terminal, los Predict de sus
producciones son disjuntos dos a dos; equivalentemente, si ninguna celda de
la tabla M[A, a] tiene más de una producción.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

EPSILON = "ε"
END = "$"


@dataclass(frozen=True)
class Production:
    index: int  # numeración 1-based, la del informe
    lhs: str
    rhs: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.lhs} → {' '.join(self.rhs) if self.rhs else EPSILON}"


@dataclass(frozen=True)
class Contribution:
    """Una regla aplicada en el cálculo de Follow (para mostrar el cálculo explícito)."""

    target: str  # el no terminal B cuyo Follow crece
    production: Production  # A → α B β
    kind: str  # "first" (aporta First(β) − ε) o "follow" (aporta Follow(A))
    symbols: frozenset[str]


@dataclass
class Conflict:
    nonterminal: str
    terminal: str
    productions: list[Production] = field(default_factory=list)


class Grammar:
    def __init__(self, start: str, rules: Sequence[tuple[str, Sequence[str]]], terminals: Iterable[str]):
        self.start = start
        self.terminals: tuple[str, ...] = tuple(dict.fromkeys(terminals))
        self.productions: tuple[Production, ...] = tuple(
            Production(i + 1, lhs, tuple(rhs)) for i, (lhs, rhs) in enumerate(rules)
        )
        self.nonterminals: tuple[str, ...] = tuple(dict.fromkeys(p.lhs for p in self.productions))
        self._check_symbols()
        self.by_lhs: dict[str, list[Production]] = {A: [] for A in self.nonterminals}
        for p in self.productions:
            self.by_lhs[p.lhs].append(p)

        self.nullable: frozenset[str] = self._compute_nullable()
        self.first: dict[str, frozenset[str]] = self._compute_first()
        self.follow: dict[str, frozenset[str]] = self._compute_follow()

    # --- validación ---------------------------------------------------------

    def _check_symbols(self) -> None:
        known = set(self.terminals) | set(self.nonterminals)
        for p in self.productions:
            for x in p.rhs:
                if x not in known:
                    raise ValueError(f"símbolo desconocido {x!r} en {p}")
        if self.start not in self.nonterminals:
            raise ValueError(f"el símbolo inicial {self.start!r} no tiene producciones")

    def is_terminal(self, x: str) -> bool:
        return x not in self.by_lhs

    # --- anulables, First y Follow (puntos fijos) -----------------------------

    def _compute_nullable(self) -> frozenset[str]:
        nullable: set[str] = set()
        changed = True
        while changed:
            changed = False
            for p in self.productions:
                if p.lhs not in nullable and all(x in nullable for x in p.rhs):
                    nullable.add(p.lhs)
                    changed = True
        return frozenset(nullable)

    def _compute_first(self) -> dict[str, frozenset[str]]:
        first: dict[str, set[str]] = {A: set() for A in self.nonterminals}
        changed = True
        while changed:
            changed = False
            for p in self.productions:
                before = len(first[p.lhs])
                first[p.lhs] |= self._first_seq(p.rhs, first) - {EPSILON}
                if p.lhs in self.nullable:
                    first[p.lhs].add(EPSILON)
                changed |= len(first[p.lhs]) != before
        return {A: frozenset(s) for A, s in first.items()}

    def _first_seq(self, seq: Sequence[str], first: dict[str, set[str]] | dict[str, frozenset[str]]) -> set[str]:
        out: set[str] = set()
        for x in seq:
            if self.is_terminal(x):
                out.add(x)
                return out
            out |= first[x] - {EPSILON}
            if x not in self.nullable:
                return out
        out.add(EPSILON)
        return out

    def first_of(self, seq: Sequence[str]) -> frozenset[str]:
        """First de una cadena de símbolos (incluye ε si la cadena es anulable)."""
        return frozenset(self._first_seq(seq, self.first))

    def _compute_follow(self) -> dict[str, frozenset[str]]:
        follow: dict[str, set[str]] = {A: set() for A in self.nonterminals}
        follow[self.start].add(END)
        changed = True
        while changed:
            changed = False
            for c in self.follow_rules():
                before = len(follow[c.target])
                follow[c.target] |= c.symbols if c.kind == "first" else follow[c.production.lhs]
                changed |= len(follow[c.target]) != before
        return {A: frozenset(s) for A, s in follow.items()}

    def follow_rules(self) -> list[Contribution]:
        """Las reglas que generan los Follow, una por cada aparición A → α B β.

        * regla 2: Follow(B) ⊇ First(β) − {ε}
        * regla 3: Follow(B) ⊇ Follow(A)  si β ⇒* ε
        (la regla 1 es $ ∈ Follow(S)).
        """
        rules: list[Contribution] = []
        for p in self.productions:
            for i, B in enumerate(p.rhs):
                if self.is_terminal(B):
                    continue
                fb = self.first_of(p.rhs[i + 1:])  # First(β); requiere self.first ya calculado
                if fb - {EPSILON}:
                    rules.append(Contribution(B, p, "first", frozenset(fb - {EPSILON})))
                if EPSILON in fb and B != p.lhs:
                    rules.append(Contribution(B, p, "follow", frozenset()))
        return rules

    # --- tabla LL(1) ----------------------------------------------------------

    def predict(self, p: Production) -> frozenset[str]:
        f = self.first_of(p.rhs)
        out = set(f - {EPSILON})
        if EPSILON in f:
            out |= self.follow[p.lhs]
        return frozenset(out)

    def ll1_table(self) -> tuple[dict[tuple[str, str], Production], list[Conflict]]:
        """Tabla predictiva M[A, a] y la lista de conflictos (vacía si G es LL(1))."""
        cells: dict[tuple[str, str], list[Production]] = {}
        for p in self.productions:
            for a in self.predict(p):
                cells.setdefault((p.lhs, a), []).append(p)
        table = {key: ps[0] for key, ps in cells.items()}
        conflicts = [Conflict(A, a, ps) for (A, a), ps in cells.items() if len(ps) > 1]
        return table, conflicts

    def is_ll1(self) -> bool:
        return not self.ll1_table()[1]
