# Project Context & Traceability Template

Este archivo es la fuente de verdad (Source of Truth) para el Agente.

## Variables de Configuración [CONFIG]
- **[CLIENTE]**: Nombre del Cliente/Proyecto
- **[TIPO_LOCALIZACION]**: (lov18resp1 | LocVe | otro)
- **[REPO_SUBMODULE_PATH]**: Ruta local absoluta al submódulo de localización.
- **[MAIN_REPO_SSH]**: SSH del repositorio principal en Odoo.sh.
- **[SUBMODULE_PATH_IN_MAIN]**: Ruta del submódulo dentro del repositorio principal.

## Entornos y Ramas [ENTORNOS]
- **[ESTABLE_GREEN_HASH]**: Último commit exitoso.
- **[RAMA_DESARROLLO]**: master
- **[RAMA_PRUEBA]**: Prueba
- **[RAMA_PRODUCCION]**: Produccion

## Bitácora de Despliegue [LOG]
<!-- El agente debe añadir una línea cada vez que haga un deploy -->
- YYYY-MM-DD: [Build ID] - [Resumen de cambios]

## Notas de Arquitectura [NOTES]
- Decisiones técnicas críticas para este cliente específico.
