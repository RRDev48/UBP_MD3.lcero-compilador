"""Analizador sintáctico LL(1) predictivo dirigido por tabla (Fase 2).

Es la implementación directa de un autómata de pila determinista con un
solo estado:

    P = ({q}, T, Γ, δ, q, $, ∅)   con Γ = N ∪ T ∪ {$}

* Si el tope es un no terminal A y el símbolo de preanálisis es a:
  δ(q, ε, A) = (q, αᴿ) cuando M[A, a] = A → α  (se apila α al revés).
* Si el tope es un terminal a igual al preanálisis: δ(q, a, a) = (q, ε).
* Acepta cuando se desapila $ con el preanálisis $ (pila vacía).

La pila guarda, junto a cada símbolo, el nodo del árbol de derivación que le
corresponde; así el árbol se arma sin recursión. Después se traduce a AST
(``build_ast``).

Reporte de errores: si M[A, a] está vacía pero A es anulable, se aplica
A → ε igual (producción por defecto) y el error se detecta más abajo en la
pila, sin consumir entrada, con un mensaje más preciso ("se esperaba ';'").
Esto no cambia el lenguaje aceptado: lo que queda debajo de A en la pila
solo puede empezar con símbolos de Follow(A), y a ∉ Follow(A), así que el
error se detecta antes de consumir a.

Recuperación (modo pánico): en lugar de abortar en el primer error, el
autómata se resincroniza y sigue, para informar todos los errores de una vez.

* Tope terminal X ≠ a: se supone que faltaba X y se lo desapila (inserción).
  Si X es $ sobra entrada: se descarta hasta un símbolo que pueda empezar una
  sentencia y se vuelve a apilar el símbolo inicial.
* Celda M[A, a] vacía: se descarta entrada hasta un símbolo de First(A) (se
  reintenta A) o de Follow(A) (se abandona A). $ nunca se descarta.

Cada paso consume entrada o achica la pila, así que el análisis termina. Para
no informar errores en cascada, después de cada error se callan los
siguientes hasta emparejar ``SILENCIO`` tokens (la misma regla que usa Bison).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ast as A
from .errors import ParseError, first_of
from .grammar import END, EPSILON, Grammar, Production
from .lcero_grammar import lcero_grammar
from .tokens import Token, TokenType
from .util import deep_recursion

#: Tokens a emparejar después de un error antes de volver a informar otro.
SILENCIO = 3


@dataclass
class ParseNode:
    """Nodo del árbol de derivación (árbol sintáctico concreto)."""

    symbol: str
    children: list[ParseNode] = field(default_factory=list)
    token: Token | None = None
    production: Production | None = None


@dataclass
class TraceRow:
    """Una fila de la traza del autómata de pila (para el informe)."""

    stack: str
    input: str
    action: str


class Parser:
    def __init__(self, grammar: Grammar | None = None) -> None:
        self.g = grammar or lcero_grammar()
        self.table, conflicts = self.g.ll1_table()
        if conflicts:
            raise ValueError(f"la gramática no es LL(1): {conflicts}")
        self.epsilon_prod = {p.lhs: p for p in self.g.productions if not p.rhs}
        self.first_no_eps = {N: self.g.first[N] - {EPSILON} for N in self.g.nonterminals}
        #: Cantidad de transiciones del autómata en el último análisis (para la Fase 7).
        self.steps = 0

    def parse_tree(self, tokens: list[Token], trace: list[TraceRow] | None = None) -> ParseNode:
        g, table = self.g, self.table
        root = ParseNode(g.start)
        stack: list[tuple[str, ParseNode]] = [(END, ParseNode(END)), (g.start, root)]
        i = 0
        tok = tokens[0]
        a = tok.type.value
        expected: set[str] = set()  # terminales que habrían sido válidos en esta posición
        errors: list[ParseError] = []
        silence = 0  # tokens que faltan emparejar para volver a informar errores
        steps = 0

        while stack:
            steps += 1
            X, node = stack[-1]
            if trace is not None:
                trace.append(TraceRow(_stack_str(stack), _input_str(tokens, i), ""))

            if g.is_terminal(X):
                if X != a:
                    if not silence:
                        errors.append(self._error(expected | {X}, tok))
                    silence = SILENCIO
                    expected.clear()
                    if trace is not None:
                        trace[-1].action = f"error: falta {X}"
                    if X != END:
                        stack.pop()  # inserción: se supone que X estaba
                        continue
                    # Sobra entrada: se descarta hasta poder empezar otra sentencia.
                    while a != END and a not in self.first_no_eps[g.start]:
                        i += 1
                        tok = tokens[i]
                        a = tok.type.value
                    if a != END:
                        stack.append((g.start, ParseNode(g.start)))
                    continue
                stack.pop()
                node.token = tok
                if trace is not None:
                    trace[-1].action = "aceptar" if X == END else f"emparejar {X}"
                if X == END:
                    break
                i += 1
                tok = tokens[i]
                a = tok.type.value
                expected.clear()
                if silence:
                    silence -= 1
                continue

            p = table.get((X, a))
            if p is None:
                if X not in self.epsilon_prod:
                    if not silence:
                        valid = self.first_no_eps[X] | (g.follow[X] if X in g.nullable else set())
                        errors.append(self._error(expected | valid, tok))
                    silence = SILENCIO
                    expected.clear()
                    if trace is not None:
                        trace[-1].action = f"error: se descarta hasta First/Follow({X})"
                    # Modo pánico: se descarta entrada hasta sincronizar con X.
                    while a != END and a not in self.first_no_eps[X] and a not in g.follow[X]:
                        i += 1
                        tok = tokens[i]
                        a = tok.type.value
                    if a not in self.first_no_eps[X]:
                        stack.pop()  # a ∈ Follow(X) o fin de entrada: se abandona X
                    continue
                p = self.epsilon_prod[X]  # producción por defecto (ver docstring)
            stack.pop()
            node.production = p
            node.children = [ParseNode(Y) for Y in p.rhs]
            for Y, child in zip(reversed(p.rhs), reversed(node.children)):
                stack.append((Y, child))
            if not p.rhs:
                expected |= self.first_no_eps[X]
            if trace is not None:
                trace[-1].action = f"({p.index}) {p}"

        self.steps = steps
        if errors:
            raise first_of(errors)
        return root

    def parse(self, tokens: list[Token]) -> A.Program:
        tree = self.parse_tree(tokens)
        with deep_recursion():
            return build_ast(tree)

    @staticmethod
    def _error(expected: set[str], tok: Token) -> ParseError:
        return ParseError(
            f"se esperaba {describe_expected(expected)}, pero se encontró {describe_token(tok)}",
            tok.line,
            tok.col,
        )


def parse(tokens: list[Token]) -> A.Program:
    return Parser().parse(tokens)


# --- Mensajes de error --------------------------------------------------------

_STMT = {"int", "id", "if", "while", "print", "{"}
_EXPR = {"num", "id", "(", "-"}
_ARITH = {"+", "-", "*", "/", "%"}
_REL = {"==", "!=", "<", "<=", ">", ">="}


def describe_expected(expected: set[str]) -> str:
    rest = set(expected)
    parts: list[str] = []
    if _STMT <= expected:
        parts.append("una sentencia")
        rest -= _STMT
    if _EXPR <= expected:
        parts.append("una expresión")
        rest -= _EXPR
    if (_ARITH | _REL) <= expected:
        parts.append("un operador")
        rest -= _ARITH | _REL
    else:
        if _ARITH <= expected:
            parts.append("un operador aritmético")
            rest -= _ARITH
        if _REL <= expected:
            parts.append("un operador relacional")
            rest -= _REL
    order = {t: i for i, t in enumerate(lcero_grammar().terminals)}
    for t in sorted(rest, key=lambda t: order.get(t, 99)):
        parts.append({"id": "un identificador", "num": "un número", END: "fin de archivo"}.get(t, f"'{t}'"))
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " o " + parts[-1]


def describe_token(tok: Token) -> str:
    if tok.type is TokenType.EOF:
        return "fin de archivo"
    if tok.type is TokenType.ID:
        return f"el identificador '{tok.lexeme}'"
    if tok.type is TokenType.NUM:
        return f"el número {tok.lexeme}"
    return f"'{tok.lexeme}'"


def _stack_str(stack: list[tuple[str, ParseNode]]) -> str:
    return " ".join(sym for sym, _ in stack)


def _input_str(tokens: list[Token], i: int) -> str:
    return " ".join(t.type.value for t in tokens[i:])


# --- Árbol de derivación → AST ------------------------------------------------


def build_ast(root: ParseNode) -> A.Program:
    """Traduce el árbol de derivación a AST.

    Las listas (ListaSent) y las colas de operadores (AritCola, TermCola) se
    recorren con bucles, no con recursión, para que programas largos no
    agoten la pila de Python. Las colas se pliegan a izquierda: así
    ``a - b - c`` queda ``(a - b) - c``.
    """
    return A.Program(_stmt_list(root.children[0]), line=1, col=1)


def _stmt_list(node: ParseNode) -> list[A.Stmt]:
    out = []
    while node.children:  # ListaSent → Sent ListaSent | ε
        out.append(_stmt(node.children[0].children[0]))
        node = node.children[1]
    return out


def _stmt(node: ParseNode) -> A.Stmt:
    c = node.children
    match node.symbol:
        case "Decl":  # int id DeclInit ;
            ident = c[1].token
            init = _expr(c[2].children[1]) if c[2].children else None
            return A.Decl(ident.lexeme, init, line=ident.line, col=ident.col)
        case "Asig":  # id = Expr ;
            ident = c[0].token
            return A.Assign(ident.lexeme, _expr(c[2]), line=ident.line, col=ident.col)
        case "Si":
            return _if(node)
        case "Mientras":  # while ( Expr ) Bloque
            kw = c[0].token
            return A.While(_expr(c[2]), _block(c[4]), line=kw.line, col=kw.col)
        case "Imprimir":  # print ( Expr ) ;
            kw = c[0].token
            return A.Print(_expr(c[2]), line=kw.line, col=kw.col)
        case "Bloque":
            return _block(node)
    raise AssertionError(node.symbol)


def _if(node: ParseNode) -> A.If:  # if ( Expr ) Bloque SiNo
    c = node.children
    kw = c[0].token
    orelse = None
    sino = c[5]
    if sino.children:  # SiNo → else CuerpoSiNo
        body = sino.children[1].children[0]  # CuerpoSiNo → Bloque | Si
        orelse = _block(body) if body.symbol == "Bloque" else _if(body)
    return A.If(_expr(c[2]), _block(c[4]), orelse, line=kw.line, col=kw.col)


def _block(node: ParseNode) -> A.Block:  # { ListaSent }
    lb = node.children[0].token
    return A.Block(_stmt_list(node.children[1]), line=lb.line, col=lb.col)


def _expr(node: ParseNode) -> A.Expr:  # Expr → Arit ExprRel
    left = _arit(node.children[0])
    rel = node.children[1]
    if not rel.children:
        return left
    op_tok = rel.children[0].children[0].token  # ExprRel → OpRel Arit
    return A.BinOp(op_tok.lexeme, left, _arit(rel.children[1]), line=op_tok.line, col=op_tok.col)


def _arit(node: ParseNode) -> A.Expr:  # Arit → Term AritCola
    acc = _term(node.children[0])
    tail = node.children[1]
    while tail.children:  # AritCola → op Term AritCola
        op = tail.children[0].token
        acc = A.BinOp(op.lexeme, acc, _term(tail.children[1]), line=op.line, col=op.col)
        tail = tail.children[2]
    return acc


def _term(node: ParseNode) -> A.Expr:  # Term → Factor TermCola
    acc = _factor(node.children[0])
    tail = node.children[1]
    while tail.children:  # TermCola → op Factor TermCola
        op = tail.children[0].token
        acc = A.BinOp(op.lexeme, acc, _factor(tail.children[1]), line=op.line, col=op.col)
        tail = tail.children[2]
    return acc


def _factor(node: ParseNode) -> A.Expr:
    c = node.children
    first = c[0]
    if first.symbol == "num":
        t = first.token
        return A.Num(int(t.lexeme), line=t.line, col=t.col)
    if first.symbol == "id":
        t = first.token
        return A.Var(t.lexeme, line=t.line, col=t.col)
    if first.symbol == "(":
        return _expr(c[1])
    # Factor → - Factor
    t = first.token
    return A.Neg(_factor(c[1]), line=t.line, col=t.col)
