# agy-bridge

> **Beta (v0.1.0).** Probado en macOS con agy 1.5.8 y 1.5.9 y Python 3.14. Sin licencia definida todavía: repositorio privado hasta decidirla.

Usa Antigravity (`agy`, Gemini) como trabajador estrictamente supervisado desde Claude Code.
Claude decide, escribe un manual por tarea y acepta o rechaza. agy ejecuta aislado. Un ejecutor
(`agy-task`) aplica compuertas automáticas para que Claude no tenga que releer todo el trabajo.

## Cómo funciona

```
Claude escribe .agy/tasks/T-001.md  (manual: objetivo, alcance, criterios, verificación)
        │
agy-task run T-001
        ├─ crea un worktree y rama propios (agy/T-001) fuera del proyecto
        ├─ lanza agy sin terminal y sin escritura fuera de ese worktree
        ├─ revierte y registra todo cambio fuera de alcance o sobre archivos protegidos
        ├─ ejecuta la verificación (tests/build) por su cuenta, no agy
        ├─ si falla, devuelve el error a agy (hasta max_fixups veces)
        └─ escribe un resultado corto con estado, compuertas, incidentes y resumen
        │
Claude lee el resultado → accept (staged, sin commit) · fix · reject
```

Tres roles: `implement` (escribe en su worktree), `explore` (solo lectura, devuelve hallazgos con
ruta y línea) y `review` (solo lectura, revisa el diff de una tarea o los cambios sin commit).

## Instalación

```bash
./install.sh
```

Crea dos enlaces: `~/.local/bin/agy-task` y `~/.claude/skills/agy-bridge`. Para quitarlos:
`./install.sh --uninstall`. Requiere `agy` autenticado, `git` y Python 3.11+.

## Uso en un proyecto

```bash
cd mi-proyecto            # debe ser un repositorio git con al menos un commit
agy-task init             # crea .agy/ ; edita .agy/config.toml (verify, link)
agy-task new T-001 --role implement --title "..."
agy-task check T-001
agy-task run T-001
agy-task diff T-001       # si el resultado lo exige
agy-task accept T-001     # o: fix / reject
```

Dentro de Claude Code basta con pedirlo ("delega esto a agy"): el skill `agy-bridge` contiene la
política de cuándo delegar y cómo escribir el manual.

## Garantías y límites

Comprobado en agy 1.5.8 y 1.5.9. agy se actualiza solo, así que tras cada actualización
conviene repetir la comprobación en vivo con `agy-task doctor --probe`:

- El implementador puede escribir dentro de su worktree, no fuera, y no tiene terminal.
- El explorador y el revisor no pueden escribir ni ejecutar nada.
- Lo que llega a `review` está siempre dentro de `allowed`, no toca `protected` y pasó `verify`.
- Nada llega a la rama del proyecto sin `accept`, y `accept` no hace commit.

Límites conocidos:

- **Sin comando de verificación no se puede delegar implementación.** Es deliberado.
- **agy no tiene terminal, ni listado, ni búsqueda.** Recibe un mapa de rutas en el prompt. En agy,
  permitir un solo comando (`command(ls)`) permite también redirecciones y encadenados, es decir,
  la terminal entera; por eso no existe la opción.
- **La verificación corre en tu máquina** con tus permisos: ejecuta el código que agy escribió.
  Mantén `allowed` estrecho y `risk` honesto.
- **Dependencias enlazadas** (`link`): agy podría modificarlas a través del enlace; se detecta y
  se registra como incidente, pero no se revierte.
- **El código viaja a Google** al delegar. No delegues archivos con secretos.
- **La cuota** depende de tu plan de Google; un fallo de cuota termina la tarea con código 10.
- El resultado de agy es un primer borrador: las compuertas prueban que cumple el contrato, no que
  el diseño sea bueno. Para eso están `risk = "medium"` y la lectura del diff.

## Estructura

```
bin/agy-task          ejecutor (Python, sin dependencias)
rules/                reglas fijas que recibe agy según el rol
templates/            plantillas de manual y de config
claude/skills/        skill para Claude Code
tests/                pruebas con un agy simulado: python3 tests/test_agy_task.py
```

En cada proyecto: `.agy/tasks/` (manuales), `.agy/config.toml`, `.agy/runs/` (estado, registros y
`usage.jsonl` con métricas por tarea; ignorado por git). Los worktrees viven en
`~/.agy-bridge/worktrees/`.
