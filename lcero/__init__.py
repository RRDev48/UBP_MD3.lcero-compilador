"""L-Cero: compilador y máquina virtual abstracta (TPI de Teoría de la Computación).

Módulos por fase:
    alphabet, regex, automata, lexer_spec, lexer   Fase 1 — análisis léxico
"""

from .lexer import tokenize

__all__ = ["tokenize"]
__version__ = "0.1.0"
