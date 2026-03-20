# Contexto del Proyecto: DEVENALSA (Odoo 18)

## Estrella del Norte
Estabilización y despliegue de la localización venezolana Fase 92 en Odoo.sh para Devenalsa.

## Configuración del Entorno
- **Repositorio Local**: `/home/nerdop/laboratorio/Devenalsa`
- **Submódulo Localización**: `nerdop44/lov18resp1`
- **Rama de Trabajo (Verdad)**: devenalsa (Submódulo)
- **Repositorio Odoo.sh**: `tbriceno65/Devenalsa`
- **SSH Alias Odoo.sh**: `25365911`

## Variables de Sincronización
[REPO_SUBMODULE_PATH]: /home/nerdop/laboratorio/Devenalsa/nerdop44/lov18resp1
[MAIN_REPO_SSH]: git@github.com:tbriceno65/Devenalsa.git
[SUBMODULE_PATH_IN_MAIN]: nerdop44/lov18resp1

**REGLA DE ORO**: La rama `devenalsa` del submódulo es la Fuente de Verdad. Los despliegues a `Producción` y `prueba-02` del maestro SIEMPRE deben rastrear esta rama tras pasar por un Green Build.

## Bitácora
- [2026-03-20 10:40]: **PURGA INTEGRAL**. Eliminación de contexto v162 discordante. Restauración absoluta a Fase 92 (v92). Rama de trabajo fijada en `devenalsa`.
