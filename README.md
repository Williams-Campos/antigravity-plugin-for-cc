# agy-bridge

[![CI](https://github.com/Williams-Campos/antigravity-agent-for-claude-code/actions/workflows/ci.yml/badge.svg)](https://github.com/Williams-Campos/antigravity-agent-for-claude-code/actions/workflows/ci.yml)
![versión](https://img.shields.io/badge/versión-0.3.1--beta-blue)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
[![licencia: MIT](https://img.shields.io/badge/licencia-MIT-green)](LICENSE)

**Antigravity (`agy`, Gemini) como trabajador estrictamente supervisado desde Claude Code.**

Claude decide, escribe un manual por tarea y acepta o rechaza. agy ejecuta aislado: en su propio
worktree, sin terminal y sin poder escribir fuera de él. Un ejecutor (`agy-task`) aplica compuertas
automáticas y devuelve un resultado corto, para que Claude no tenga que releer todo el trabajo.

El objetivo es reservar a Claude para lo que exige criterio (diseño, decisiones, aceptación) y
dejar a agy la ejecución que se puede especificar y verificar.

> **Beta.** Probado en macOS con agy 1.5.8 y 1.5.9, sobre un proyecto Flutter real. Las pruebas
> automáticas corren además en Linux.

## Cómo funciona

```
Claude escribe .agy/tasks/T-001.md   (manual: objetivo, alcance, criterios, verificación)
        │
agy-task run T-001
        ├─ crea un worktree y una rama propios (agy/T-001), fuera del proyecto
        ├─ lanza agy sin terminal y sin escritura fuera de ese worktree
        ├─ ejecuta el formateador del proyecto (agy no puede)
        ├─ revierte y registra todo cambio fuera de alcance o sobre archivos protegidos
        ├─ ejecuta la verificación (tests, build) por su cuenta; no se fía de agy
        ├─ si falla, devuelve el error a agy, hasta max_fixups veces
        └─ escribe un resultado corto: estado, compuertas, incidentes, archivos, resumen
        │
Claude lee el resultado  →  accept (staged, sin commit)  ·  fix  ·  reject
```

Hay tres roles:

| Rol | Qué hace | Dónde trabaja | Permisos |
|---|---|---|---|
| `implement` | Escribe código según el manual | Worktree propio | Edita solo dentro del worktree; sin terminal |
| `explore` | Responde una pregunta sobre el código, con ruta y línea | El proyecto | Solo lectura |
| `review` | Revisa el diff de una tarea o los cambios sin commit, con otro modelo | Worktree de la tarea o el proyecto | Solo lectura |

## Garantías

| Garantía | Cómo se asegura |
|---|---|
| agy no escribe fuera de su worktree ni usa la terminal | Permisos por sesión de agy, comprobados en vivo una vez por versión de agy antes de delegar |
| Lo que llega a `review` está dentro de `allowed` y no toca `protected` | El ejecutor revierte cualquier otro cambio y lo registra como incidente |
| Lo que llega a `review` pasó la verificación | La ejecuta el ejecutor, fuera de agy, sobre el estado ya filtrado |
| Nada entra en tu rama sin `accept` | agy trabaja en otra rama y otro directorio |
| `accept` no hace commit ni rompe tu trabajo en curso | Se aplica como parche atómico al índice: entra completo o no toca nada |
| Las tareas de riesgo no se aceptan a ciegas | Riesgo medio, incidentes o diff grande exigen `accept --reviewed` |

## Requisitos

- [Antigravity CLI](https://antigravity.google/) (`agy`) instalado y con sesión iniciada.
- `git` y Python 3.11 o superior (sin dependencias externas).
- macOS o Linux. En Windows, WSL.
- El proyecto donde delegues debe ser un repositorio git con al menos un commit.

## Instalación

```bash
git clone https://github.com/Williams-Campos/antigravity-agent-for-claude-code.git agy-bridge
```

```bash
cd agy-bridge && ./install.sh
```

Crea dos enlaces simbólicos: `~/.local/bin/agy-task` y `~/.claude/skills/agy-bridge`. No modifica
la configuración de Claude Code ni la de agy. Para quitarlos: `./install.sh --uninstall`.

`agy-task` localiza por sí mismo un Python adecuado, aunque el `python3` del `PATH` sea más antiguo
(en macOS suele ser 3.9). Para fijar uno: `export AGY_BRIDGE_PYTHON=/ruta/a/python3`.

## Primeros pasos

Una vez por proyecto:

```bash
cd mi-proyecto
agy-task init        # crea .agy/ y sugiere el comando de verificación
$EDITOR .agy/config.toml
agy-task baseline    # comprueba, sin gastar cuota, que la verificación pasa en un worktree limpio
```

Por cada tarea:

```bash
agy-task new T-001 --role implement --title "Agregar slugify a textutil"
$EDITOR .agy/tasks/T-001.md
agy-task check T-001
agy-task run T-001
agy-task diff T-001          # si el resultado lo exige
agy-task accept T-001        # o: fix "…" / reject
```

Dentro de Claude Code basta con pedirlo («delega esto a agy»): el skill `agy-bridge` le indica
cuándo delegar, cómo escribir el manual y qué hacer con cada resultado.

## El manual de una tarea

Un manual es un archivo Markdown con una cabecera TOML. Hay ejemplos completos en
[`examples/`](examples/).

```markdown
+++
id = "T-001"
title = "Agregar slugify a textutil"
role = "implement"
risk = "low"
allowed = ["src/textutil.py"]
protected = ["tests/**"]
+++

## Objetivo
Agregar `slugify` a `src/textutil.py` para convertir títulos en identificadores aptos para URL.

## Contexto
Lee `src/textutil.py` (estilo del módulo) y `tests/test_slugify.py` (define el comportamiento).

## Cómo hacerlo
- Firma: `slugify(text: str, max_length: int | None = None) -> str`.
- Solo biblioteca estándar.

## Criterios de aceptación
- Todos los tests de `tests/test_slugify.py` pasan sin modificarlos.

## Fuera de alcance
- No crear otros archivos.
```

| Campo | Roles | Significado |
|---|---|---|
| `id`, `title` | todos | Identificador (igual al nombre del archivo) y título corto |
| `role` | todos | `implement`, `explore` o `review` |
| `risk` | implement | `low`: se puede aceptar con el resumen · `medium`: exige leer el diff · `high`: no se delega |
| `allowed` | implement, explore | Únicos archivos que agy puede tocar. En `explore`, zonas de interés |
| `protected` | implement | Archivos que definen qué es correcto (tests). agy no puede cambiarlos |
| `forbidden` | implement | Exclusiones dentro de `allowed` |
| `seed` | implement | Archivos tuyos aún sin commit que agy debe ver, p. ej. una prueba recién escrita. No puede cambiarlos y no entran en su diff |
| `search` | todos | Textos exactos que el ejecutor busca en el proyecto y adjunta al prompt |
| `verify` | implement | Comandos de verificación. Si se omite, usa los de `config.toml` |
| `target` | review | Id de la tarea a revisar, o `"working"` para los cambios sin commit |
| `model`, `max_fixups`, `max_diff_lines`, `timeout_min` | todos | Sustituyen los valores por defecto del proyecto |

Secciones obligatorias: `## Objetivo` siempre, y `## Criterios de aceptación` en `implement`.

## Estados

| Estado | Significado | Qué hacer |
|---|---|---|
| `review` · revisión `resumen` | Pasó las compuertas; riesgo bajo y sin incidentes | `accept` |
| `review` · revisión `diff` | Pasó las compuertas; riesgo medio, incidentes o diff grande | `diff`, leerlo, `accept --reviewed` |
| `blocked` | agy tiene preguntas o el contrato no se puede cumplir | `fix "respuesta"` |
| `failed (gates)` | No pasó la verificación tras las correcciones | `fix "indicación"`, `run --restart` o hacerlo a mano |
| `failed (setup)` | Falló la preparación del worktree | Corregir `setup`/`link` y repetir `baseline` |
| `failed (quota·auth·timeout)` | Fallo de agy | Esperar, iniciar sesión o ampliar `timeout_min` |
| `done` | Reporte de `explore` o `review` listo | Usarlo |
| `accepted`, `rejected` | Cerradas | — |

## Comandos

| Comando | Descripción |
|---|---|
| `init` | Prepara `.agy/` en el proyecto |
| `baseline` | Ejecuta la verificación sobre el último commit, sin agy |
| `new <id> --role … --title …` | Crea un manual desde la plantilla |
| `check <id>` | Valida un manual sin ejecutarlo |
| `run <id> [--restart] [--allow-overlap]` | Ejecuta la tarea y aplica las compuertas |
| `fix <id> "mensaje"` | Envía una corrección o respuesta a agy y repite las compuertas |
| `result <id>` | Muestra el resultado, o el progreso si sigue en curso |
| `diff <id> [--stat] [rutas…]` | Muestra el diff de una tarea |
| `accept <id> [--reviewed] [--keep]` | Integra el trabajo en la rama actual, staged y sin commit |
| `reject <id> [--reason …]` | Descarta el trabajo: borra worktree y rama |
| `cancel <id>` | Cancela una tarea en ejecución |
| `status` | Lista tareas y estados |
| `stats` | Resume sesiones, intentos, tiempos y consumo |
| `doctor [--probe]` | Comprueba la instalación; con `--probe`, sondea la contención en vivo |

Códigos de salida de `run` y `fix`: `0` listo · `1` uso o manual inválido · `2` bloqueado ·
`3` compuertas fallidas · `4` fallo del ejecutor · `10` cuota · `11` autenticación · `12` timeout.

## Configuración del proyecto

`.agy/config.toml`; todas las claves son opcionales.

| Clave | Por defecto | Para qué |
|---|---|---|
| `verify` | `[]` | Comandos que definen «correcto». Sin al menos uno no se delega implementación |
| `link` | `[]` | Rutas que git no copia al worktree y se enlazan: dependencias instaladas, SDK local |
| `setup` | `[]` | Comandos que preparan el worktree antes de verificar, p. ej. `npm ci` |
| `autofix` | `[]` | Formateadores que el ejecutor aplica tras cada turno de agy |
| `model_implement`, `model_explore` | `gemini-4-hydrogen-high` | Modelo por rol (`agy models`) |
| `model_review` | `gemini-4-argon-high` | Conviene que sea distinto del que implementa |
| `max_fixups` | `2` | Correcciones automáticas antes de devolver el control a Claude |
| `max_diff_lines` | `800` | Por encima, la tarea exige leer el diff |
| `timeout_min` | `30` | Límite por turno de agy |
| `verify_timeout_min` | `15` | Límite por comando de verificación |
| `worktree_root` | `~/.agy-bridge/worktrees` | Dónde se crean los worktrees |

## Qué se midió

Primera prueba en un proyecto Flutter real (unos 190 archivos Dart y 158 pruebas), con
`bash scripts/check.sh` como verificación: resolución de dependencias, generación de código,
formato, análisis y pruebas.

| Encargo | Resultado | Tiempo |
|---|---|---|
| 2 `explore` en paralelo | Referencias de ruta y línea correctas al contrastarlas con el código | 41 s y 46 s |
| 2 `implement` en paralelo (pruebas unitarias nuevas, 69 y 77 líneas) | Pasaron todas las compuertas al primer intento | ~1 min de agy + ~4 min de verificación cada una |
| 2 `review` con otro modelo | Un hallazgo menor y válido, corregido luego con `fix` | ~1 min cada una |
| Contrato imposible a propósito, con presión para «hacerlo pasar» | `blocked` las dos veces; no intentó tocar lo prohibido | 17 s |

Es una muestra pequeña, no un benchmark. La lección práctica: el tiempo lo domina la verificación
del proyecto, no agy, así que conviene lanzar en paralelo las tareas independientes.

## Límites conocidos

- **Sin comando de verificación no se delega implementación.** Es deliberado.
- **agy no tiene terminal, listado de directorios ni búsqueda.** Recibe un mapa de rutas y los
  resultados de `search`. En agy, permitir un solo comando (`command(ls)`) permite también
  redirecciones y encadenados, es decir, la terminal entera; por eso no existe esa opción.
- **El worktree parte del último commit.** Los cambios sin commit no llegan a agy, salvo los
  archivos listados en `seed`.
- **La verificación corre en tu máquina, con tus permisos**, y ejecuta el código que escribió agy.
  Mantén `allowed` estrecho y `risk` honesto.
- **El código viaja a Google** al delegar. No delegues archivos con secretos.
- **La cuota depende de tu plan de Google.** Un fallo de cuota termina la tarea con código 10.
- **Las compuertas prueban que el trabajo cumple el contrato, no que el diseño sea bueno.** Para
  eso están `risk = "medium"`, la lectura del diff y el rol `review`.
- **Cada worktree nuevo repite la preparación del proyecto** (instalar, generar código), lo que
  alarga la verificación.

## Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `LA VERIFICACIÓN BASE FALLA` | La verificación no pasa ni sin cambios: falta algo en `link` o `setup`, o el proyecto ya estaba roto. Mira `.agy/runs/_baseline.log` |
| `la contención de agy X falló` | Esa versión de agy no respeta los permisos esperados. No se delega; repite con `agy-task doctor --probe` |
| `failed (gates)` repetido en formato o lint | Falta el formateador en `autofix`: agy no puede ejecutarlo |
| `blocked` porque agy no encuentra un archivo | Da la ruta exacta en el manual o añade el nombre a `search` |
| `no se pudo integrar` al aceptar | Los archivos de la tarea cambiaron en el proyecto. Confirma o descarta esos cambios, o `run --restart` |
| `requiere Python 3.11` | Define `AGY_BRIDGE_PYTHON` con la ruta de un Python reciente |

## Desarrollo

```
bin/agy-task        lanzador: localiza un Python adecuado
lib/agy_task.py     ejecutor, sin dependencias externas
rules/              reglas fijas que recibe agy según el rol
templates/          plantillas de manual y de configuración
examples/           manuales de ejemplo
claude/skills/      skill para Claude Code
tests/              pruebas con un agy simulado
```

Las pruebas no llaman al agy real ni gastan cuota:

```bash
python3 tests/test_agy_task.py
```

En cada proyecto, `agy-task` usa `.agy/tasks/` (manuales), `.agy/config.toml` y `.agy/runs/`
(estado, registros y `usage.jsonl`; ignorado por git). El historial de cambios está en
[`CHANGELOG.md`](CHANGELOG.md).

## Licencia

[MIT](LICENSE). agy-bridge es un proyecto independiente, sin relación con Google ni con Anthropic.
«Antigravity», «Gemini», «Claude» y «Claude Code» son marcas de sus respectivos dueños. El uso de
agy y de Claude se rige por los términos de cada servicio, y lo que delegues viaja a ellos.
