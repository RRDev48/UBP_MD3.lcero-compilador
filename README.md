# L-Cero — Compilador y Máquina Virtual Abstracta

Trabajo Práctico Integrador (Evaluación Parcial N°2): diseño, formalización,
implementación y análisis de un compilador y una máquina virtual para el
mini-lenguaje imperativo **L-Cero**. Todos los analizadores están escritos
desde cero en Python, sin generadores de parsers ni el módulo `re`.

**Informe técnico:** fuente LaTeX en [`docs/informe/informe.tex`](docs/informe/informe.tex);
el PDF se entrega por separado y no se versiona.

## Estado

| Hito | Fase | Resultado |
|---|---|---|
| I | 1. Lexer | ER → AFN-ε (Thompson, 319) → AFD (subconjuntos, 95) → AFD mínimo (Hopcroft, 42); matriz δ |
| I | 2. Parser LL(1) | 43 producciones, First/Follow, tabla de 93 celdas sin conflictos; autómata de pila |
| I | 3. Semántico | declaración previa, doble declaración, asignación definida; prueba de que no es GLC |
| II | 4. RI | código de tres direcciones con registros virtuales |
| II | 5. Máquina | máquina de registros con cinta, cabezal, estados y δ explícitos; Turing-completa |
| II | 6. Indecidibilidad | reducción ejecutable Halting Problem → terminación de L-Cero |
| III | 7. Complejidad | cotas O/Ω/Θ contrastadas con profiling real |
| III | 8. Registros | coloreo de Chaitin; reducción ejecutable k-COLOREO → asignación (NP-completo) |

## Uso

Requiere Python ≥ 3.10, sin dependencias en tiempo de ejecución. La
instalación en modo editable deja disponible el comando `lcero` y, con el
extra `dev`, las dependencias de los tests y los gráficos (pytest, matplotlib):

```bash
pip install -e ".[dev]"
```

```bash
python -m pytest                            # suite completa (351 pruebas)
lcero ejecutar programa.l0 -k 4             # compilar y ejecutar con k registros
lcero tokens programa.l0                    # Fase 1: tokens
lcero afd                                   # Fase 1: autómatas y matriz δ
lcero gramatica                             # Fase 2: First, Follow, tabla LL(1)
lcero ast programa.l0                       # Fases 2-3: AST validado
lcero avisos programa.l0                    # Fase 3: avisos del compilador
lcero ri programa.l0                        # Fase 4: código de tres direcciones
lcero registros programa.l0 -k 3            # Fase 8: interferencia y coloreo
lcero maquina programa.l0 -k 3              # Fase 5: programa de la máquina
lcero traza programa.l0 --max-pasos 50      # Fase 5: configuraciones
```

Sin instalar, cada comando funciona igual con `python -m lcero` en lugar de `lcero`.

**Diagnósticos.** El parser se recupera de los errores en modo pánico
(sincroniza con First/Follow) y el análisis semántico sigue después de cada
error, así que un programa con varios errores los informa todos de una vez.
Además, el compilador da avisos que no rechazan el programa: variables que
nunca se leen, condiciones constantes, bucles cuya condición no cambia en el
cuerpo y código inalcanzable. `lcero ejecutar` los muestra por stderr (se
apagan con `--sin-avisos`).

Para regenerar el informe (las figuras en PDF no se versionan: las genera
`generar_documentacion.py`, que para los diagramas necesita Graphviz):

```bash
python scripts/profiling.py                 # mediciones de la Fase 7 (unos minutos)
python scripts/generar_documentacion.py     # tablas, números y figuras del informe (diagramas: requiere Graphviz)
cd docs/informe && latexmk -xelatex informe.tex
```

El informe usa la plantilla de la UBP (logos en `docs/informe/plantilla/`). Los
datos de la carátula (asignatura, docente, autores, URL del
repositorio) se completan al principio de `docs/informe/informe.tex`.

## Estructura

```
lcero/
  tokens.py, errors.py   categorías léxicas y errores por fase (con línea y columna)
  alphabet.py            Σ y su partición en 30 clases de caracteres
  regex.py               ER como árboles (símbolo, ε, concatenación, unión, Kleene)
  automata.py            Thompson, subconjuntos, Hopcroft, Moore, equivalencia
  lexer_spec.py, lexer.py  ER de los tokens; lexer de máximo bocado sobre la matriz δ
  grammar.py             GLC genérica: anulables, First, Follow, tabla LL(1)
  lcero_grammar.py       la gramática BNF de L-Cero
  parser.py, ast.py      autómata de pila LL(1), árbol de derivación y AST
  semantic.py            ámbitos, doble declaración, asignación definida
  lint.py                avisos: variables sin leer, condiciones constantes, código inalcanzable
  arith.py               semántica de los operadores (compartida con la máquina)
  ir.py                  generación de código de tres direcciones
  regalloc.py            vivacidad, interferencia, Chaitin, coloreo exacto
  vm.py                  ensamblador y máquina de registros (cinta, cabezal, δ)
  compiler.py            orquestación de todas las fases
  turing.py              MT, su simulación y la traducción MT → L-Cero (Fase 6)
  reductions.py          traducción grafo → programa P_G (Fase 8)
  generator.py           programas de prueba para el profiling
  report.py              exportación de tablas y diagramas
tests/
  programas/             33 programas L-Cero con su salida o error esperado en la
                         primera línea (validos, error_lexico, error_sintactico,
                         error_semantico, bucle_infinito)
  test_*.py              pruebas de cada fase
docs/
  especificacion.md      definición del lenguaje
  informe/               informe técnico (LaTeX + PDF)
  generado/              matriz δ, mediciones y gráficos en formatos abiertos
scripts/
  generar_documentacion.py, profiling.py
```
