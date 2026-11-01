"""Gramática LL(1) de L-Cero en BNF.

Se obtiene de la EBNF de ``docs/especificacion.md`` eliminando las
repeticiones { } y opcionales [ ] con no terminales "cola" recursivos a
derecha (ListaSent, AritCola, TermCola) y factorizando a izquierda donde
hacía falta (DeclInit, SiNo, ExprRel). No tiene recursión a izquierda.

Los terminales son los valores de ``TokenType`` (``id``, ``num``, ``int``,
``(``...) más ``$`` (fin de entrada).
"""

from __future__ import annotations

from functools import lru_cache

from .grammar import END, Grammar
from .tokens import SKIPPED, TokenType

RULES: list[tuple[str, list[str]]] = [
    ("Programa", ["ListaSent"]),                                   # 1
    ("ListaSent", ["Sent", "ListaSent"]),                          # 2
    ("ListaSent", []),                                             # 3
    ("Sent", ["Decl"]),                                            # 4
    ("Sent", ["Asig"]),                                            # 5
    ("Sent", ["Si"]),                                              # 6
    ("Sent", ["Mientras"]),                                        # 7
    ("Sent", ["Imprimir"]),                                        # 8
    ("Sent", ["Bloque"]),                                          # 9
    ("Decl", ["int", "id", "DeclInit", ";"]),                      # 10
    ("DeclInit", ["=", "Expr"]),                                   # 11
    ("DeclInit", []),                                              # 12
    ("Asig", ["id", "=", "Expr", ";"]),                            # 13
    ("Si", ["if", "(", "Expr", ")", "Bloque", "SiNo"]),            # 14
    ("SiNo", ["else", "CuerpoSiNo"]),                              # 15
    ("SiNo", []),                                                  # 16
    ("CuerpoSiNo", ["Bloque"]),                                    # 17
    ("CuerpoSiNo", ["Si"]),                                        # 18
    ("Mientras", ["while", "(", "Expr", ")", "Bloque"]),           # 19
    ("Imprimir", ["print", "(", "Expr", ")", ";"]),                # 20
    ("Bloque", ["{", "ListaSent", "}"]),                           # 21
    ("Expr", ["Arit", "ExprRel"]),                                 # 22
    ("ExprRel", ["OpRel", "Arit"]),                                # 23
    ("ExprRel", []),                                               # 24
    ("OpRel", ["=="]),                                             # 25
    ("OpRel", ["!="]),                                             # 26
    ("OpRel", ["<"]),                                              # 27
    ("OpRel", ["<="]),                                             # 28
    ("OpRel", [">"]),                                              # 29
    ("OpRel", [">="]),                                             # 30
    ("Arit", ["Term", "AritCola"]),                                # 31
    ("AritCola", ["+", "Term", "AritCola"]),                       # 32
    ("AritCola", ["-", "Term", "AritCola"]),                       # 33
    ("AritCola", []),                                              # 34
    ("Term", ["Factor", "TermCola"]),                              # 35
    ("TermCola", ["*", "Factor", "TermCola"]),                     # 36
    ("TermCola", ["/", "Factor", "TermCola"]),                     # 37
    ("TermCola", ["%", "Factor", "TermCola"]),                     # 38
    ("TermCola", []),                                              # 39
    ("Factor", ["num"]),                                           # 40
    ("Factor", ["id"]),                                            # 41
    ("Factor", ["(", "Expr", ")"]),                                # 42
    ("Factor", ["-", "Factor"]),                                   # 43
]

#: Terminales de la gramática, en el orden de las columnas de la tabla LL(1).
TERMINALS: tuple[str, ...] = tuple(
    t.value for t in TokenType if t not in SKIPPED and t is not TokenType.EOF
) + (END,)


@lru_cache(maxsize=1)
def lcero_grammar() -> Grammar:
    return Grammar("Programa", RULES, TERMINALS)


def terminal_of(tt: TokenType) -> str:
    """Símbolo terminal de la gramática que corresponde a un tipo de token."""
    return tt.value
