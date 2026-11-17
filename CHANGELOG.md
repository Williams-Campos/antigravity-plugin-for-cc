# Registro de cambios

## 0.3.1 — 2026-11-17

### Añadido
- Licencia MIT.

## 0.3.0 — 2026-11-16

### Añadido
- La contención de agy se comprueba sola una vez por versión instalada, antes de delegar. Si
  falla, el ejecutor se niega a lanzar ninguna tarea. Los ocho sondeos corren en paralelo.
- Lanzador `bin/agy-task` que localiza un Python 3.11 o superior aunque el `python3` del `PATH`
  sea más antiguo. `AGY_BRIDGE_PYTHON` permite fijar uno.
- Comando `stats`: sesiones, intentos, tiempos y consumo a partir de `usage.jsonl`.
- `agy-task --version`.
- Un resultado `failed (gates)` incluye el final de la verificación fallida y los archivos que
  dejó agy.
- Integración continua en Linux y macOS, ejemplos de manuales y este registro.

### Cambiado
- El ejecutor se reorganizó en `lib/agy_task.py`, con una sola vía para lanzar procesos.
- `cancel` detiene también los comandos de verificación en curso, no solo a agy.
- `accept` muestra solo los archivos de la tarea aceptada.

### Corregido
- `reject` ya no permite marcar como rechazada una tarea aceptada.
- `accept` avisa con claridad si la rama de la tarea ya no existe.
- El manual admite BOM y líneas en blanco antes de la cabecera.

## 0.2.0 — 2026-11-16

Ajustes tras la primera prueba en un proyecto real (Flutter).

### Añadido
- `autofix`: el ejecutor aplica el formateador tras cada turno, porque agy no tiene terminal.
- `seed`: archivos sin commit (pruebas escritas por Claude) llegan al worktree, agy no puede
  modificarlos y no entran en su diff.
- `search`: el ejecutor adjunta búsquedas de texto exacto, porque agy no tiene buscador.
- `baseline`: comprueba la verificación en un worktree limpio, sin gastar cuota.

### Cambiado
- `accept` integra la tarea como parche atómico: se pueden aceptar varias tareas seguidas y
  conviven con cambios sin commit.
- El mapa de archivos omite multimedia y binarios.
- El resultado muestra tiempo de trabajo acumulado, y `usage.jsonl` registra cada sesión.

### Eliminado
- La detección por fecha de modificación de dependencias enlazadas: daba falsos incidentes con
  tareas en paralelo, y agy ya deniega escribir a través de enlaces que salen del workspace.

## 0.1.0 — 2026-11-16

Primera versión: ejecutor `agy-task` con los roles `implement`, `explore` y `review`, worktree por
tarea, compuertas de alcance y verificación, skill para Claude Code e instalador.
