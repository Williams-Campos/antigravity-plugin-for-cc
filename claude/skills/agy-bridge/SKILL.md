---
name: agy-bridge
description: Delega trabajo a Antigravity (agy / Gemini) como trabajador estrictamente supervisado, mediante el comando `agy-task`. Úsalo cuando el usuario pida "usar agy", "delegar a agy/Gemini", "que agy lo haga", o cuando haya implementación bien especificada y verificable, exploración amplia de código o una primera revisión que no necesiten el criterio de Claude. Claude decide, escribe el manual y acepta o rechaza; agy ejecuta aislado y sin terminal.
---

# agy-bridge — agy como trabajador supervisado

Tú (Claude) eres la cabeza: decides, especificas y aceptas. agy es el trabajador: ejecuta un manual dentro de un worktree aislado, sin terminal y sin poder escribir fuera de su carpeta. `agy-task` aplica compuertas automáticas y te devuelve un resultado corto. **Tu atención es el recurso escaso: no releas lo que las compuertas ya garantizan.**

## Cuándo delegar

| Delega a agy | Hazlo tú |
|---|---|
| Implementación con criterios verificables por un comando (tests, build, lint) | Arquitectura, diseño, requisitos ambiguos |
| Exploración: "¿dónde y cómo se hace X?" (rol `explore`) | Ediciones pequeñas (< ~30 líneas): el ida y vuelta cuesta más |
| Tests, migraciones mecánicas, código repetitivo | Código sensible: seguridad, pagos, datos, migraciones de BD |
| Primera revisión de un diff con otro modelo (rol `review`) | Cualquier cosa sin forma automática de verificarse |

## Flujo

1. Una vez por proyecto: `agy-task init`, y completa `.agy/config.toml` con el comando de verificación del proyecto (`verify`), las rutas que git no copia (`link`: dependencias, SDK local) y el formateador (`autofix`). Después `agy-task baseline`: comprueba, sin gastar cuota de agy, que la verificación pasa en un worktree limpio. Si falla, nada de lo que delegues podrá pasar.
2. `agy-task new <ID> --role implement|explore|review --title "..."` y **rellena el manual** en `.agy/tasks/<ID>.md`.
3. `agy-task check <ID>` hasta que sea válido.
4. `agy-task run <ID>`. Si puede tardar más de 2 minutos, ejecútalo en segundo plano (Bash con `run_in_background`) y sigue con otra cosa; no hagas polling.
5. Lee **solo el resultado** que imprime (`agy-task result <ID>` para verlo de nuevo) y decide según el estado.

## Cómo escribir un buen manual (implement)

El manual es la única información que agy tiene. Lo que no decidas tú, lo decide agy.

- **Objetivo**: comportamiento observable, no pasos.
- **Contexto**: rutas exactas que debe leer y el patrón existente que debe imitar. agy no tiene búsqueda ni listado: recibe un mapa de rutas y los resultados de los términos que pongas en `search` (texto exacto, p. ej. el nombre de una clase).
- **Cómo hacerlo**: todas las decisiones de diseño ya tomadas (firmas, nombres, librerías permitidas).
- **Criterios de aceptación**: verificables, con valores concretos. Lo ideal es escribir tú primero las pruebas y listarlas en `seed`: agy las recibe aunque no tengan commit, no puede modificarlas y no entran en su diff. Así el contrato es ejecutable.
- Si no estás seguro de un valor esperado, dilo en el manual y pide `blocked` en caso de discrepancia, en vez de dejar que agy lo "arregle".
- **allowed** lo más estrecho posible; **risk** honesto.
- Una tarea = un cambio coherente. Si no puedes escribir criterios verificables, no la delegues.

## Qué hacer con cada estado

| Estado | Significado | Acción |
|---|---|---|
| `review` · revisión `resumen` | Compuertas OK, riesgo bajo, sin incidentes | `agy-task accept <ID>` sin leer el diff |
| `review` · revisión `diff` | Compuertas OK, pero riesgo medio, incidentes o diff grande | `agy-task diff <ID>`, léelo, luego `accept <ID> --reviewed` |
| `blocked` | agy tiene preguntas | Responde con `agy-task fix <ID> "..."` |
| `failed (gates)` | No pasó la verificación tras las correcciones | `fix` con una indicación concreta, `run --restart` con mejor manual, o hazlo tú |
| `failed (quota/auth/timeout)` | Fallo del ejecutor | Informa al usuario; no reintentes en bucle |
| `done` | Reporte de `explore` o `review` listo | Úsalo; verifica por tu cuenta lo que vaya a sostener una decisión importante |

`accept` deja los cambios **preparados (staged) sin commit** en la rama actual. El commit sigue las reglas normales del usuario.

Cada tarea se verifica sola, en su worktree. Después de aceptar varias tareas, ejecuta una vez la verificación del proyecto sobre el conjunto antes de dar el trabajo por bueno.

## Patrones que rinden

- **Explorar antes de especificar**: un `explore` (20–60 s) te da rutas, líneas y huecos con los que escribir un manual preciso sin leer tú el código. Comprueba dos o tres de sus referencias antes de fiarte.
- **Paralelo**: lanza a la vez las tareas independientes (cada una en segundo plano). La verificación domina el tiempo, no agy.
- **Revisión cruzada**: tras un `implement`, un `review` con `target = "<ID>"` usa otro modelo y cuesta ~1 minuto. Si encuentra algo real, pásaselo a agy con `fix`.
- **Contrato ejecutable**: escribe tú la prueba, ponla en `seed` y deja que agy implemente hasta que pase.

## Comandos

```
agy-task init | baseline | status | doctor [--probe]
agy-task new <ID> --role R --title "..." [--target <ID>|working]
agy-task check|run|result|cancel <ID>      run: --restart, --allow-overlap
agy-task fix <ID> "mensaje para agy"
agy-task diff <ID> [--stat] [rutas...]
agy-task accept <ID> [--reviewed] [--keep]   ·   agy-task reject <ID> [--reason "..."]
```

Salida de `run`/`fix`: 0 listo · 2 bloqueado · 3 compuertas fallidas · 4 fallo del ejecutor · 10 cuota · 11 autenticación · 12 timeout.

## Reglas que no se negocian

- Nunca aceptes una tarea que exige `--reviewed` sin haber leído el diff.
- Nunca edites a mano el worktree de agy para "ayudarle" a pasar: corrige con `fix` o hazlo tú desde cero.
- Los incidentes (cambios fuera de alcance, tests modificados) se revierten solos, pero cuentan: dos tareas seguidas con incidentes indican un manual ambiguo; reescríbelo.
- No lances en paralelo tareas `implement` con `allowed` solapado (el ejecutor lo bloquea).
- Varias tareas independientes sí pueden ir en paralelo, cada una en segundo plano.
- Tras actualizar agy, ejecuta `agy-task doctor --probe` antes de delegar: comprueba que la contención sigue funcionando.
- El código del proyecto viaja a Google al delegar. No delegues archivos con secretos.
