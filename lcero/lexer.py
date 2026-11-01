"""Analizador léxico de L-Cero (Fase 1).

El lexer es un intérprete de la matriz δ del AFD mínimo. La matriz se
obtiene a partir de las ER de ``lexer_spec.py`` con nuestras propias
implementaciones de Thompson, subconjuntos y Hopcroft (``automata.py``);
no se usa ningún generador de analizadores ni el módulo ``re``.

Estrategia: *máximo bocado* (longest match). Desde la posición actual se
avanza por el AFD recordando el último estado final visitado; cuando el AFD
cae en el sumidero (o se termina la entrada) se emite el token de ese último
estado final y se retoma desde donde terminó.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .alphabet import CLASSES, OTRO_INDEX, class_index
from .automata import DFA, NFA, build_combined_nfa, hopcroft_minimize, subset_construction
from .errors import LexicalError
from .lexer_spec import TOKEN_SPECS
from .tokens import SKIPPED, Token, TokenType


@dataclass(frozen=True)
class LexerAutomata:
    """Los tres autómatas de la cadena de construcción (para el informe y los tests)."""

    nfa: NFA
    dfa: DFA
    min_dfa: DFA
    #: Para cada estado del AFD mínimo, los estados del AFD que agrupa.
    blocks: list[frozenset[int]]


@lru_cache(maxsize=1)
def lexer_automata() -> LexerAutomata:
    """ER → AFN-ε (Thompson) → AFD (subconjuntos) → AFD mínimo (Hopcroft)."""
    nfa = build_combined_nfa([(spec.regex, spec.type) for spec in TOKEN_SPECS])
    dfa = subset_construction(nfa, CLASSES)
    min_dfa, blocks = hopcroft_minimize(dfa)
    return LexerAutomata(nfa, dfa, min_dfa, blocks)


class Lexer:
    """Convierte código fuente L-Cero en una lista de tokens terminada en EOF."""

    def __init__(self, dfa: DFA | None = None) -> None:
        self.dfa = dfa or lexer_automata().min_dfa
        self._delta = self.dfa.trans
        self._start = self.dfa.start
        self._sink = self.dfa.sink
        self._label: list[TokenType | None] = [
            self.dfa.accepting.get(q) for q in range(self.dfa.n_states)  # type: ignore[misc]
        ]

    def tokenize(self, source: str) -> list[Token]:
        delta, label, sink = self._delta, self._label, self._sink
        tokens: list[Token] = []
        n = len(source)
        pos, line, col = 0, 1, 1

        while pos < n:
            q = self._start
            i = pos
            last_type: TokenType | None = None
            last_end = pos
            # Avanzar por el AFD mientras no caiga en el sumidero.
            while i < n:
                q = delta[q][class_index(source[i])]
                if q == sink:
                    break
                i += 1
                if label[q] is not None:
                    last_type, last_end = label[q], i

            if last_type is None:
                raise LexicalError(self._describe_error(source, pos, i), line, col)

            lexeme = source[pos:last_end]
            if last_type not in SKIPPED:
                tokens.append(Token(last_type, lexeme, line, col))

            # Actualizar línea y columna.
            newlines = lexeme.count("\n")
            if newlines:
                line += newlines
                col = len(lexeme) - lexeme.rfind("\n")
            else:
                col += len(lexeme)
            pos = last_end

        tokens.append(Token(TokenType.EOF, "", line, col))
        return tokens

    @staticmethod
    def _describe_error(source: str, pos: int, stop: int) -> str:
        ch = source[pos]
        if class_index(ch) == OTRO_INDEX:
            return f"el carácter {_show(ch)} no pertenece al alfabeto de L-Cero"
        fragment = source[pos:stop]
        following = f", seguido de {_show(source[stop])}" if stop < len(source) else " al final del archivo"
        return f"la secuencia {_show(fragment)}{following} no forma ningún token válido"


def _show(s: str) -> str:
    return "'" + s.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r") + "'"


def tokenize(source: str) -> list[Token]:
    """Atajo: tokeniza ``source`` con el AFD mínimo del lenguaje."""
    return Lexer().tokenize(source)
