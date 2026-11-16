+++
id = "{{id}}"
title = "{{title}}"
role = "implement"
risk = "medium"            # low: se acepta con el resumen · medium: Claude lee el diff · high: no se delega
allowed = ["«src/modulo/**»"]          # únicos archivos que agy puede crear o modificar
protected = ["«tests/**»"]             # agy no puede tocarlos (tests que definen "correcto")
# forbidden = []                       # exclusiones dentro de allowed
# seed = ["«tests/nuevo_test»"]        # archivos tuyos aún sin commit que agy debe ver (no puede cambiarlos)
# search = ["«NombreDeClase»"]         # texto exacto que el ejecutor busca y adjunta (agy no tiene buscador)
# verify = ["«comando de test»"]       # si se omite, usa verify de .agy/config.toml
# max_fixups = 2
# max_diff_lines = 800
# timeout_min = 30
+++

## Objetivo
«Qué debe quedar funcionando y para qué, en 2–4 líneas. Comportamiento observable, no pasos.»

## Contexto
«Dónde vive esto en el código: archivos y funciones que agy debe leer primero, y el patrón existente que debe imitar.»

## Cómo hacerlo
«Decisiones ya tomadas: enfoque, nombres, firmas, convenciones. Todo lo que no quieras que agy decida.»

## Criterios de aceptación
- «Condición verificable 1 (idealmente un test concreto que debe pasar)»
- «Condición verificable 2»

## Fuera de alcance
- «Lo que agy NO debe hacer aunque parezca relacionado»
