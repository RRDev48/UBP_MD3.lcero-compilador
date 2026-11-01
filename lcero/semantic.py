"""Análisis semántico estático (Fase 3).

Verifica, sobre el AST, las restricciones que la gramática libre de contexto
no puede expresar:

1. **Declaración previa:** toda variable usada o asignada fue declarada en un
   ámbito visible.
2. **Doble declaración:** no se declara un nombre ya visible (ni en el mismo
   bloque ni en uno que lo contiene: no hay sombreado).
3. **Asignación definida:** no se lee una variable que, en algún camino
   posible, todavía no recibió valor (análisis de flujo como el de Java).

Por qué esto excede a un autómata con pila (justificación completa en el
informe): el lenguaje de los programas con "declaración antes de uso",
intersecado con un lenguaje regular, es esencialmente {w c w}, que no es
libre de contexto; sí lo reconoce un autómata linealmente acotado.

Además resuelve cada nombre a un identificador único (``uid``) para la RI.

Recuperación: ante un error se lo registra y se sigue con el resto del
programa. Para no repetir el mismo problema, cada nombre sin declarar y cada
variable sin inicializar se informa una sola vez; una doble declaración no
reemplaza a la original.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ast as A
from .errors import SemanticError, first_of
from .util import deep_recursion


@dataclass
class Symbol:
    name: str
    uid: str
    line: int
    col: int


class SemanticAnalyzer:
    def __init__(self) -> None:
        # nombre -> símbolo visible. Como no hay sombreado, alcanza un único
        # diccionario más una pila de "qué se declaró en cada bloque".
        self.visible: dict[str, Symbol] = {}
        self.scopes: list[list[str]] = []
        self.uid_count: dict[str, int] = {}
        self.symbols: list[Symbol] = []
        self.errors: list[SemanticError] = []
        self.reported: set[str] = set()  # nombres sin declarar y uids sin inicializar ya informados

    def analyze(self, program: A.Program) -> list[Symbol]:
        self.scopes.append([])
        self._stmts(program.body, frozenset())
        self.scopes.pop()
        if self.errors:
            raise first_of(self.errors)
        return self.symbols

    def _error(self, mensaje: str, node: A.Node, key: str | None = None) -> None:
        if key is not None:
            if key in self.reported:
                return
            self.reported.add(key)
        self.errors.append(SemanticError(mensaje, node.line, node.col))

    # --- ámbitos ------------------------------------------------------------

    def _declare(self, d: A.Decl) -> Symbol:
        if d.name in self.visible:
            prev = self.visible[d.name]
            self._error(f"doble declaración: '{d.name}' ya fue declarada en la línea {prev.line}, columna {prev.col}", d)
            return prev
        n = self.uid_count.get(d.name, 0)
        self.uid_count[d.name] = n + 1
        sym = Symbol(d.name, d.name if n == 0 else f"{d.name}.{n}", d.line, d.col)
        self.visible[d.name] = sym
        self.scopes[-1].append(d.name)
        self.symbols.append(sym)
        return sym

    def _lookup(self, name: str, node: A.Node) -> Symbol | None:
        sym = self.visible.get(name)
        if sym is None:
            self._error(f"la variable '{name}' no está declarada en este ámbito", node, key=name)
        return sym

    # --- sentencias: devuelven el conjunto de variables definitivamente asignadas

    def _stmts(self, body: list[A.Stmt], assigned: frozenset[str]) -> frozenset[str]:
        for s in body:
            assigned = self._stmt(s, assigned)
        return assigned

    def _stmt(self, s: A.Stmt, assigned: frozenset[str]) -> frozenset[str]:
        match s:
            case A.Decl(_, init):
                sym = self._declare(s)
                s.uid = sym.uid
                if init is not None:
                    self._expr(init, assigned)
                    return assigned | {sym.uid}
                return assigned
            case A.Assign(name, value):
                sym = self._lookup(name, s)
                self._expr(value, assigned)
                if sym is None:
                    return assigned
                s.uid = sym.uid
                return assigned | {sym.uid}
            case A.Print(value):
                self._expr(value, assigned)
                return assigned
            case A.Block(body):
                self.scopes.append([])
                out = self._stmts(body, assigned)
                for name in self.scopes.pop():
                    del self.visible[name]
                return out
            case A.If(cond, then, orelse):
                self._expr(cond, assigned)
                after_then = self._stmt(then, assigned)
                after_else = self._stmt(orelse, assigned) if orelse is not None else assigned
                return after_then & after_else  # asignada solo si lo fue en ambas ramas
            case A.While(cond, body):
                self._expr(cond, assigned)
                self._stmt(body, assigned)
                return assigned  # el cuerpo puede no ejecutarse nunca
        raise TypeError(s)

    def _expr(self, e: A.Expr, assigned: frozenset[str]) -> None:
        match e:
            case A.Num():
                return
            case A.Var(name):
                sym = self._lookup(name, e)
                if sym is None:
                    return
                if sym.uid not in assigned:
                    self._error(f"la variable '{name}' puede usarse sin haber sido inicializada", e, key=sym.uid)
                e.uid = sym.uid
            case A.Neg(operand):
                self._expr(operand, assigned)
            case A.BinOp(_, left, right):
                self._expr(left, assigned)
                self._expr(right, assigned)
            case _:
                raise TypeError(e)


def analyze(program: A.Program) -> list[Symbol]:
    """Valida el programa y anota los ``uid``. Devuelve la tabla de símbolos."""
    with deep_recursion():
        return SemanticAnalyzer().analyze(program)
