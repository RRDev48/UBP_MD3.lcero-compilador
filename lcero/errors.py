"""Jerarquía de errores del compilador L-Cero.

Cada fase lanza su propia subclase para que los tests (y el usuario) puedan
distinguir en qué etapa falló un programa. Todas llevan línea y columna
(1-based) cuando el error se puede ubicar en el código fuente.

Las fases que se recuperan de los errores (sintáctica y semántica) siguen
analizando y lanzan el primero, con todos los de la fase en ``errores``.
"""

from __future__ import annotations


class LCeroError(Exception):
    """Base de todos los errores del compilador y de la máquina virtual."""

    fase = "general"

    def __init__(self, mensaje: str, linea: int | None = None, columna: int | None = None):
        self.mensaje = mensaje
        self.linea = linea
        self.columna = columna
        #: Todos los errores que encontró la fase, en orden; este es el primero.
        self.errores: list[LCeroError] = [self]
        super().__init__(self.__str__())

    def __str__(self) -> str:
        pos = ""
        if self.linea is not None and self.columna is not None:
            pos = f" (línea {self.linea}, columna {self.columna})"
        elif self.linea is not None:
            pos = f" (línea {self.linea})"
        return f"Error {self.fase}{pos}: {self.mensaje}"


def first_of(errores: list[LCeroError]) -> LCeroError:
    """El primer error de la lista, que lleva a todos en ``errores`` (para lanzarlo)."""
    e = errores[0]
    e.errores = errores
    return e


class LexicalError(LCeroError):
    """La entrada contiene una secuencia que no forma ningún token (Fase 1)."""

    fase = "léxico"


class ParseError(LCeroError):
    """La secuencia de tokens no pertenece a L(G) (Fase 2)."""

    fase = "sintáctico"


class SemanticError(LCeroError):
    """El programa es sintácticamente válido pero viola una regla estática (Fase 3)."""

    fase = "semántico"


class VMError(LCeroError):
    """Error en tiempo de ejecución dentro de la máquina virtual (Fase 5)."""

    fase = "de ejecución"
