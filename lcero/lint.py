"""Avisos del compilador: análisis estático que no rechaza el programa.

Corre después del análisis semántico (usa los ``uid`` que este anota) y
señala construcciones válidas pero casi seguramente equivocadas:

1. **Variables sin leer:** declaradas que nunca se usan, o que reciben valores
   que nadie lee.
2. **Condiciones constantes** en ``if`` y ``while``: una rama que nunca se
   ejecuta o un bucle que no termina.
3. **Condición invariante:** ninguna variable de la condición de un ``while``
   se asigna en su cuerpo. Como L-Cero no tiene ``break`` ni expresiones con
   efectos, la condición vale siempre lo mismo: si el bucle entra, no termina.
4. **Código inalcanzable:** sentencias después de una que nunca termina
   (la misma idea de "completa normalmente" que usa Java).

Los avisos 2 y 3 son correctos pero no completos: por la Fase 6 ningún
análisis puede detectar todos los bucles infinitos.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ast as A
from .arith import DivisionByZero, apply
from .util import deep_recursion


@dataclass
class Aviso:
    mensaje: str
    linea: int
    columna: int

    def __str__(self) -> str:
        return f"Aviso (línea {self.linea}, columna {self.columna}): {self.mensaje}"


def constant(e: A.Expr) -> int | None:
    """Valor de ``e`` si no depende de ninguna variable (y no divide por cero)."""
    match e:
        case A.Num(value):
            return value
        case A.Var():
            return None
        case A.Neg(operand):
            v = constant(operand)
            return None if v is None else -v
        case A.BinOp(op, left, right):
            a, b = constant(left), constant(right)
            if a is None or b is None:
                return None
            try:
                return apply(op, a, b)
            except DivisionByZero:
                return None
    raise TypeError(e)


def variables(e: A.Expr) -> set[str]:
    """uids de las variables que lee ``e``."""
    match e:
        case A.Num():
            return set()
        case A.Var(uid=uid):
            return {uid}
        case A.Neg(operand):
            return variables(operand)
        case A.BinOp(_, left, right):
            return variables(left) | variables(right)
    raise TypeError(e)


def assigned_in(s: A.Stmt) -> set[str]:
    """uids que ``s`` puede asignar (declaraciones con valor incluidas)."""
    match s:
        case A.Decl(uid=uid, init=init):
            return {uid} if init is not None else set()
        case A.Assign(uid=uid):
            return {uid}
        case A.Print():
            return set()
        case A.Block(body):
            return set().union(*map(assigned_in, body))
        case A.If(_, then, orelse):
            return assigned_in(then) | (assigned_in(orelse) if orelse is not None else set())
        case A.While(_, body):
            return assigned_in(body)
    raise TypeError(s)


class Linter:
    def __init__(self) -> None:
        self.avisos: list[Aviso] = []
        self.decls: dict[str, A.Decl] = {}
        self.reads: set[str] = set()
        self.writes: set[str] = set()

    def lint(self, program: A.Program) -> list[Aviso]:
        self._stmts(program.body)
        for uid, d in self.decls.items():
            if uid in self.reads:
                continue
            if uid in self.writes:
                self._warn(f"la variable '{d.name}' recibe valores que nunca se leen", d)
            else:
                self._warn(f"la variable '{d.name}' se declara pero nunca se usa", d)
        return sorted(self.avisos, key=lambda w: (w.linea, w.columna))

    def _warn(self, mensaje: str, node: A.Node) -> None:
        self.avisos.append(Aviso(mensaje, node.line, node.col))

    # --- sentencias: devuelven si pueden terminar ("completar normalmente")

    def _stmts(self, body: list[A.Stmt]) -> bool:
        completes = True
        for s in body:
            if not completes:
                self._warn("código inalcanzable: la sentencia anterior no termina nunca", s)
                completes = True  # se avisa una vez por secuencia
            completes = self._stmt(s)
        return completes

    def _stmt(self, s: A.Stmt) -> bool:
        match s:
            case A.Decl(_, init, uid):
                self.decls[uid] = s
                if init is not None:
                    self._expr(init)
                    self.writes.add(uid)
                return True
            case A.Assign(_, value, uid):
                self._expr(value)
                self.writes.add(uid)
                return True
            case A.Print(value):
                self._expr(value)
                return True
            case A.Block(body):
                return self._stmts(body)
            case A.If(cond, then, orelse):
                self._expr(cond)
                c = constant(cond)
                then_ok = self._stmt(then)
                else_ok = self._stmt(orelse) if orelse is not None else True
                if c is None:
                    return then_ok or else_ok
                if c:
                    self._warn("la condición del if es siempre verdadera"
                               + (": el else nunca se ejecuta" if orelse is not None else ""), cond)
                    return then_ok
                self._warn("la condición del if es siempre falsa: el bloque nunca se ejecuta", cond)
                return else_ok
            case A.While(cond, body):
                self._expr(cond)
                self._stmt(body)
                c = constant(cond)
                if c is not None:
                    if c:
                        self._warn("la condición del while es siempre verdadera: el bucle no termina nunca", cond)
                        return False
                    self._warn("la condición del while es siempre falsa: el cuerpo nunca se ejecuta", cond)
                elif not variables(cond) & assigned_in(body):
                    self._warn("ninguna variable de la condición cambia en el cuerpo: "
                               "si el bucle entra, no termina nunca", cond)
                return True
        raise TypeError(s)

    def _expr(self, e: A.Expr) -> None:
        self.reads |= variables(e)


def lint(program: A.Program) -> list[Aviso]:
    """Avisos de un programa ya validado por el análisis semántico."""
    with deep_recursion():
        return Linter().lint(program)
