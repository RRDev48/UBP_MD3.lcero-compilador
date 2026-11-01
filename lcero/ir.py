"""Representación intermedia: código de tres direcciones (Fase 4).

El compilador no ejecuta el AST: lo traduce a una secuencia de instrucciones
elementales con a lo sumo tres direcciones (dos operandos y un destino).
Los nombres son *registros virtuales* ilimitados: las variables del programa
(por su ``uid``) y temporales ``$t1, $t2, ...`` (``$`` no pertenece a Σ, así
que no chocan con nombres del usuario). La Fase 8 les asigna registros
físicos.

Instrucciones (``a`` y ``b`` son nombres o constantes enteras):

    x = a op b      op ∈ { + - * / % == != < <= > >= }
    x = -a
    x = a           copia (o carga de constante)
    print a
    L:              etiqueta
    goto L
    ifz a goto L    salta si a == 0
    halt
    x = load [n]    lectura de la celda n de la cinta (solo código de derrame)
    store [n] = a   escritura en la cinta (solo código de derrame)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ast as A
from .arith import DivisionByZero, apply
from .util import deep_recursion

Operand = str | int


@dataclass
class TAC:
    op: str  # bin, neg, copy, print, label, goto, ifz, halt, load, store
    dst: str | None = None
    a: Operand | None = None
    b: Operand | None = None
    binop: str | None = None
    label: str | None = None
    slot: int | None = None
    #: Línea del código fuente (para errores de ejecución).
    line: int = field(default=0, compare=False)
    #: Profundidad de anidamiento de bucles (peso del costo de derrame).
    depth: int = field(default=0, compare=False)

    def uses(self) -> list[str]:
        """Nombres que la instrucción lee (use)."""
        return [x for x in (self.a, self.b) if isinstance(x, str)]

    def defs(self) -> list[str]:
        """Nombres que la instrucción escribe (def)."""
        return [self.dst] if self.dst is not None else []

    def __str__(self) -> str:
        match self.op:
            case "bin":
                return f"{self.dst} = {self.a} {self.binop} {self.b}"
            case "neg":
                return f"{self.dst} = -{self.a}"
            case "copy":
                return f"{self.dst} = {self.a}"
            case "print":
                return f"print {self.a}"
            case "label":
                return f"{self.label}:"
            case "goto":
                return f"goto {self.label}"
            case "ifz":
                return f"ifz {self.a} goto {self.label}"
            case "halt":
                return "halt"
            case "load":
                return f"{self.dst} = load [{self.slot}]"
            case "store":
                return f"store [{self.slot}] = {self.a}"
        raise ValueError(self.op)


def format_tac(code: list[TAC]) -> str:
    lines = []
    for ins in code:
        lines.append(str(ins) if ins.op == "label" else f"    {ins}")
    return "\n".join(lines)


class IRGenerator:
    """AST anotado (con uid) → código de tres direcciones.

    Optimizaciones locales: plegado de constantes (``2 * 3`` → ``6``, salvo
    divisiones por cero, que se dejan para que fallen en ejecución) y
    escritura directa en la variable destino (``x = a + b`` sin temporal).
    """

    def __init__(self) -> None:
        self.code: list[TAC] = []
        self.n_temps = 0
        self.n_labels = 0
        self.line = 0
        self.depth = 0

    def generate(self, program: A.Program) -> list[TAC]:
        for s in program.body:
            self._stmt(s)
        self._emit(TAC("halt"))
        return self.code

    # --- utilidades ---------------------------------------------------------

    def _emit(self, ins: TAC) -> None:
        ins.line = self.line
        ins.depth = self.depth
        self.code.append(ins)

    def _temp(self) -> str:
        self.n_temps += 1
        return f"$t{self.n_temps}"

    def _label(self) -> str:
        self.n_labels += 1
        return f"L{self.n_labels}"

    # --- sentencias ---------------------------------------------------------

    def _stmt(self, s: A.Stmt) -> None:
        self.line = s.line
        match s:
            case A.Decl(_, init):
                if init is not None:
                    self._expr(init, dest=s.uid)
            case A.Assign(_, value):
                self._expr(value, dest=s.uid)
            case A.Print(value):
                v = self._expr(value)
                self.line = s.line
                self._emit(TAC("print", a=v))
            case A.Block(body):
                for t in body:
                    self._stmt(t)
            case A.If(cond, then, orelse):
                l_else, l_end = self._label(), self._label()
                c = self._expr(cond)
                self.line = s.line
                self._emit(TAC("ifz", a=c, label=l_else if orelse is not None else l_end))
                self._stmt(then)
                if orelse is not None:
                    self._emit(TAC("goto", label=l_end))
                    self._emit(TAC("label", label=l_else))
                    self._stmt(orelse)
                self._emit(TAC("label", label=l_end))
            case A.While(cond, body):
                l_start, l_end = self._label(), self._label()
                self.depth += 1
                self._emit(TAC("label", label=l_start))
                c = self._expr(cond)
                self.line = s.line
                self._emit(TAC("ifz", a=c, label=l_end))
                self._stmt(body)
                self.line = s.line
                self._emit(TAC("goto", label=l_start))
                self.depth -= 1
                self._emit(TAC("label", label=l_end))
            case _:
                raise TypeError(s)

    # --- expresiones --------------------------------------------------------

    def _expr(self, e: A.Expr, dest: str | None = None) -> Operand:
        """Genera código para ``e``; devuelve el operando con su valor.

        Si se da ``dest``, el resultado queda en esa variable.
        """
        match e:
            case A.Num(value):
                return self._place(value, dest)
            case A.Var():
                return self._place(e.uid, dest)
            case A.Neg(operand):
                v = self._expr(operand)
                if isinstance(v, int):
                    return self._place(-v, dest)
                d = dest or self._temp()
                self._emit(TAC("neg", dst=d, a=v))
                return d
            case A.BinOp(op, left, right):
                l = self._expr(left)
                r = self._expr(right)
                if isinstance(l, int) and isinstance(r, int):
                    try:
                        return self._place(apply(op, l, r), dest)
                    except DivisionByZero:
                        pass  # se deja la operación: fallará en tiempo de ejecución
                d = dest or self._temp()
                self._emit(TAC("bin", dst=d, a=l, b=r, binop=op))
                return d
        raise TypeError(e)

    def _place(self, v: Operand, dest: str | None) -> Operand:
        if dest is None:
            return v
        self._emit(TAC("copy", dst=dest, a=v))
        return dest


def generate(program: A.Program) -> list[TAC]:
    with deep_recursion():
        return IRGenerator().generate(program)
