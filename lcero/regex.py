"""Expresiones regulares como árboles sintácticos.

No se usa el módulo ``re`` de Python: las ER se representan con los cinco
constructores de la definición inductiva (símbolo, ε, concatenación, unión y
clausura de Kleene) y la Fase 1 las traduce a autómatas con la construcción
de Thompson (ver ``automata.py``).

Los símbolos son *clases de caracteres* de ``alphabet.CLASSES``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import reduce


class Regex:
    """Nodo de una expresión regular."""


@dataclass(frozen=True)
class Sym(Regex):
    """Un símbolo del alfabeto (una clase de caracteres)."""

    c: str


@dataclass(frozen=True)
class Eps(Regex):
    """La cadena vacía ε."""


@dataclass(frozen=True)
class Cat(Regex):
    """Concatenación r·s."""

    a: Regex
    b: Regex


@dataclass(frozen=True)
class Alt(Regex):
    """Unión r | s."""

    a: Regex
    b: Regex


@dataclass(frozen=True)
class Star(Regex):
    """Clausura de Kleene r*."""

    a: Regex


# --- Azúcar sintáctico: todo se reduce a los cinco constructores de arriba ---


def sym(c: str) -> Regex:
    return Sym(c)


def seq(*rs: Regex) -> Regex:
    """r1 · r2 · ... · rn"""
    if not rs:
        return Eps()
    return reduce(Cat, rs)


def alt(*rs: Regex) -> Regex:
    """r1 | r2 | ... | rn"""
    if not rs:
        raise ValueError("alt() necesita al menos una alternativa")
    return reduce(Alt, rs)


def star(r: Regex) -> Regex:
    return Star(r)


def plus(r: Regex) -> Regex:
    """r⁺ = r · r*"""
    return Cat(r, Star(r))


def to_str(r: Regex) -> str:
    """Representación textual (para depuración)."""
    match r:
        case Sym(c):
            return c if len(c) == 1 else f"[{c}]"
        case Eps():
            return "ε"
        case Cat(a, b):
            return _paren(a, Alt) + _paren(b, Alt)
        case Alt(a, b):
            return f"{to_str(a)}|{to_str(b)}"
        case Star(a):
            inner = to_str(a)
            return f"({inner})*" if isinstance(a, (Cat, Alt)) else f"{inner}*"
    raise TypeError(r)


def _paren(r: Regex, kind: type) -> str:
    s = to_str(r)
    return f"({s})" if isinstance(r, kind) else s
