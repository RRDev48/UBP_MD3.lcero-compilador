# Fase 1 — Analizador léxico

> Resumen de la Fase 1. La versión completa y formal está en el informe técnico (`docs/informe/informe.tex`). Las tablas completas (matriz δ, estados,
> clases) están en [`generado/fase1_afd_minimo.md`](generado/fase1_afd_minimo.md)
> y el diagrama en [`generado/afd_minimo.svg`](generado/afd_minimo.svg).
> Se regeneran con `python scripts/generar_documentacion.py`.

## 1. Cadena de construcción

El AFD no se escribe a mano ni con un generador: se **calcula** a partir de
las expresiones regulares con implementaciones propias de los tres algoritmos
clásicos (`lcero/automata.py`).

```
 ER de los 26 tokens ──Thompson──▶ AFN-ε ──subconjuntos──▶ AFD ──Hopcroft──▶ AFD mínimo
                                   319 estados           95 estados        42 estados
```

| Paso | Algoritmo | Resultado | Costo |
|---|---|---|---|
| ER → AFN-ε | Thompson | 319 estados (≤ 2·\|r\|) | O(\|r\|) |
| AFN-ε → AFD | Construcción por subconjuntos | 95 estados alcanzables (incluye ∅) | O(2^\|Q_N\| · \|C\|) peor caso |
| AFD → AFD mínimo | Hopcroft (refinamiento de particiones) | 42 estados (39 finales + q0, q13, q∅) | O(\|C\| · n log n) |

### 1.1 Thompson

Cada ER se traduce recursivamente a un fragmento (inicial, final):

- símbolo `a`: `s —a→ t`
- concatenación `rs`: `final(r) —ε→ inicial(s)`
- unión `r | s`: nuevo `s₀` con ε a ambos iniciales; ambos finales con ε a un nuevo `t₀`
- clausura `r*`: nuevo `s₀` y `t₀`; `s₀ —ε→ t₀` (cero veces) y `final(r) —ε→ inicial(r)` (repetir)

Los 26 fragmentos se unen con un estado inicial nuevo y transiciones ε. El
final de cada fragmento queda etiquetado con su token y su prioridad.

**Tupla formal:** N = (Q_N, C, Δ, q₀ᴺ, F_N) con |Q_N| = 319,
Δ : Q_N × (C ∪ {ε}) → 𝒫(Q_N), F_N = los 26 finales de fragmento, y
λ_N : F_N → Tokens × ℕ (token y prioridad).

### 1.2 Construcción por subconjuntos

Cada estado del AFD es un conjunto S ⊆ Q_N cerrado por ε:

- q₀ᴰ = ε-clausura({q₀ᴺ})
- δ_D(S, a) = ε-clausura(mover(S, a))
- S es final si contiene algún final del AFN; λ_D(S) es el token **de mayor
  prioridad** entre ellos. Así, el conjunto alcanzado con `while` contiene el
  final de `WHILE` y el de `ID`, y gana `WHILE`.

El conjunto vacío aparece solo y es el **sumidero**: δ queda total.

### 1.3 Minimización de Hopcroft

Partición inicial: `{no finales}` más un bloque por cada token (dos estados
que aceptan tokens distintos no pueden ser equivalentes, aunque ambos sean
finales). Se refina con separadores (A, a): un bloque Y se parte en
Y ∩ pre_a(A) e Y − pre_a(A) cuando ambos son no vacíos. Al estabilizarse, cada
bloque es una clase de la relación de Myhill–Nerode y el cociente es el AFD
mínimo. El mayor ahorro está en q2 (identificador general), que fusiona 21
estados del AFD de subconjuntos, y en q27 (comentario), que fusiona 30.

**Tupla formal del AFD mínimo:** M = (Q, C, δ, q0, F) con

- Q = {q0, q1, …, q40, q∅} (|Q| = 42)
- C = las 30 clases de caracteres (columnas de la matriz)
- δ : Q × C → Q total, dada por la matriz de `generado/fase1_afd_minimo.md`
- q0 estado inicial
- F = Q − {q0, q13, q∅} (|F| = 39)
- λ : F → Tokens, la columna «λ» de la tabla de estados

### 1.4 Verificación

Los tests (`tests/test_automata.py`) comprueban con métodos independientes que:

1. el AFD mínimo es **equivalente** al de subconjuntos (recorrido del autómata producto);
2. es **mínimo**: el algoritmo de Moore, distinto de Hopcroft, no encuentra dos estados equivalentes;
3. Hopcroft y Moore llegan a la **misma partición** sobre el AFD sin minimizar;
4. δ es total, hay un único sumidero y todo estado es alcanzable y co-alcanzable;
5. el lexer con la matriz δ produce **los mismos tokens** que simular el AFN-ε
   directamente, sobre 2000 cadenas aleatorias.

## 2. El analizador

`Lexer.tokenize` interpreta la matriz δ con la regla del **máximo bocado**:
desde la posición actual avanza por el AFD recordando el último estado final
visitado; cuando cae en q∅ (o se termina la entrada) emite el token de ese
último final y retoma desde ahí. Los tokens *comentario* y *espacio* se
reconocen pero no se entregan al parser. Al final se agrega `EOF` (el `$` de
los conjuntos Follow).

### 2.1 Errores léxicos

Si desde la posición actual no se alcanza ningún estado final, hay error:

- carácter de Σ_O fuera de un comentario: *«el carácter '@' no pertenece al alfabeto de L-Cero»*;
- prefijo que no completa un token (solo `!` sin `=`): *«la secuencia '!', seguido de 'x' no forma ningún token válido»*.

El error lleva línea y columna (1-based) del inicio de la secuencia.

### 2.2 Complejidad

Sea n la longitud de la entrada.

- **Tiempo Θ(n).** El máximo bocado puede, en general, releer caracteres
  (si el AFD pasa por estados no finales después de haber aceptado). En este
  AFD los únicos estados no finales son q0, q13 y q∅, y q13 solo se alcanza
  desde q0: una vez que se aceptó algo, el autómata nunca atraviesa un estado
  no final antes de caer en q∅. Por eso cada carácter se examina a lo sumo dos
  veces (al consumirlo y, si fue el que llevó a q∅, al empezar el token
  siguiente): T(n) ≤ 2n + O(1). La cota inferior Ω(n) es trivial (hay que
  leer toda la entrada), así que T(n) = Θ(n).
- **Espacio Θ(n)** para la lista de tokens; O(1) adicional. La matriz δ ocupa
  |Q|·|C| = 42 · 30 = 1260 entradas, constante respecto de n.

En la Fase 7 se contrasta esta cota con mediciones reales.
