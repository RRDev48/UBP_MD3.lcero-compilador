"""Semántica de los operadores de L-Cero sobre ℤ.

Un único lugar para la aritmética, compartido por el plegado de constantes
del compilador y por la máquina virtual: así los dos nunca discrepan.
"""

from __future__ import annotations


class DivisionByZero(ArithmeticError):
    pass


def tdiv(a: int, b: int) -> int:
    """División entera truncada hacia cero (como C y Java)."""
    if b == 0:
        raise DivisionByZero
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def tmod(a: int, b: int) -> int:
    """Resto con el signo del dividendo: a == tdiv(a, b) * b + tmod(a, b)."""
    return a - tdiv(a, b) * b


BINOPS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": tdiv,
    "%": tmod,
    "==": lambda a, b: int(a == b),
    "!=": lambda a, b: int(a != b),
    "<": lambda a, b: int(a < b),
    "<=": lambda a, b: int(a <= b),
    ">": lambda a, b: int(a > b),
    ">=": lambda a, b: int(a >= b),
}


def apply(op: str, a: int, b: int) -> int:
    return BINOPS[op](a, b)
