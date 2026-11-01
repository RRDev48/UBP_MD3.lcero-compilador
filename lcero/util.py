"""Utilidades comunes."""

from __future__ import annotations

import sys
from contextlib import contextmanager

from .errors import LCeroError

#: Límite de recursión durante las fases que recorren el árbol. Cada nivel de
#: anidamiento del programa usa unos pocos marcos de Python; con este límite
#: se admiten miles de niveles.
RECURSION_LIMIT = 50_000


@contextmanager
def deep_recursion():
    """Sube temporalmente el límite de recursión y traduce el desborde a un error del compilador."""
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, RECURSION_LIMIT))
    try:
        yield
    except RecursionError:
        raise LCeroError("el programa tiene un anidamiento demasiado profundo") from None
    finally:
        sys.setrecursionlimit(old)
