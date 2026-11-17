+++
id = "T-001"
title = "Agregar slugify a textutil"
role = "implement"
risk = "low"
allowed = ["src/textutil.py"]
protected = ["tests/**"]
+++

## Objetivo
Agregar la función `slugify` a `src/textutil.py` para convertir títulos en identificadores aptos para URL.

## Contexto
Lee `src/textutil.py` (estilo del módulo) y `tests/test_slugify.py` (define el comportamiento exacto).

## Cómo hacerlo
- Firma: `slugify(text: str, max_length: int | None = None) -> str`.
- Solo biblioteca estándar (`unicodedata`, `re`). Sin dependencias nuevas.
- Quita acentos, pasa a minúsculas y reemplaza cualquier secuencia de caracteres que no sean letras o dígitos ASCII por un solo guion; sin guiones al inicio ni al final.
- Con `max_length`, corta sin partir palabras: conserva solo las palabras completas que quepan.
- Docstring de una línea, igual que el resto del módulo.

## Criterios de aceptación
- Todos los tests de `tests/test_slugify.py` pasan sin modificarlos.
- Las funciones existentes del módulo no cambian.

## Fuera de alcance
- No crear otros archivos ni tocar el README.
