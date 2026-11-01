"""Árbol de sintaxis abstracta (AST) de L-Cero.

El parser construye primero el árbol de derivación (concreto) y luego lo
traduce a estos nodos, que descartan los símbolos puramente sintácticos
(paréntesis, punto y coma, no terminales "cola").

Los campos ``uid`` los completa el análisis semántico: es el nombre único de
la variable tras resolver ámbitos (dos bloques hermanos pueden declarar ``t``
y en la RI se llaman ``t`` y ``t.1``).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    line: int = field(default=0, kw_only=True)
    col: int = field(default=0, kw_only=True)


# --- Expresiones --------------------------------------------------------------


@dataclass
class Num(Node):
    value: int


@dataclass
class Var(Node):
    name: str
    uid: str | None = None


@dataclass
class BinOp(Node):
    op: str  # + - * / % == != < <= > >=
    left: Expr
    right: Expr


@dataclass
class Neg(Node):
    operand: Expr


Expr = Num | Var | BinOp | Neg


# --- Sentencias ---------------------------------------------------------------


@dataclass
class Decl(Node):
    name: str
    init: Expr | None
    uid: str | None = None


@dataclass
class Assign(Node):
    name: str
    value: Expr
    uid: str | None = None


@dataclass
class Block(Node):
    body: list[Stmt]


@dataclass
class If(Node):
    cond: Expr
    then: Block
    orelse: Block | If | None


@dataclass
class While(Node):
    cond: Expr
    body: Block


@dataclass
class Print(Node):
    value: Expr


Stmt = Decl | Assign | Block | If | While | Print


@dataclass
class Program(Node):
    body: list[Stmt]


# --- Impresión ----------------------------------------------------------------


def expr_str(e: Expr) -> str:
    match e:
        case Num(value):
            return str(value)
        case Var(name):
            return name
        case Neg(operand):
            return f"-{expr_str(operand)}"
        case BinOp(op, left, right):
            return f"({expr_str(left)} {op} {expr_str(right)})"
    raise TypeError(e)


def dump(node: Program | Stmt, indent: int = 0) -> str:
    """Representación indentada del AST (para la CLI y el informe)."""
    pad = "  " * indent
    match node:
        case Program(body):
            return "Programa\n" + "\n".join(dump(s, indent + 1) for s in body)
        case Decl(name, init):
            return f"{pad}Decl {name}" + (f" = {expr_str(init)}" if init is not None else "")
        case Assign(name, value):
            return f"{pad}Asig {name} = {expr_str(value)}"
        case Print(value):
            return f"{pad}Print {expr_str(value)}"
        case Block(body):
            return f"{pad}Bloque\n" + "\n".join(dump(s, indent + 1) for s in body) if body else f"{pad}Bloque (vacío)"
        case While(cond, body):
            return f"{pad}While {expr_str(cond)}\n" + dump(body, indent + 1)
        case If(cond, then, orelse):
            out = f"{pad}If {expr_str(cond)}\n" + dump(then, indent + 1)
            if orelse is not None:
                out += f"\n{pad}Else\n" + dump(orelse, indent + 1)
            return out
    raise TypeError(node)
