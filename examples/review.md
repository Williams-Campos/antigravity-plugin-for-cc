+++
id = "R-001"
title = "Revisión de slugify"
role = "review"
target = "T-001"
+++

## Objetivo
El cambio agrega `slugify(text, max_length=None)` a `src/textutil.py`. Debe quitar acentos, usar solo `[a-z0-9]` separados por un guion y, con `max_length`, no partir palabras. Comprueba contra el código los casos borde: `max_length` menor que la primera palabra, `max_length = 0` y texto vacío.
