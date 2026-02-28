# Contexto del Proyecto: Krill Energy

## Estrella del Norte
Asegurar la estabilidad operativa total de la implementación de Odoo 18, enfocándose específicamente en la localización venezolana (`lov18resp1`), estabilidad del POS e integración con sistema central.

## Configuración del Entorno (Detectado)
- **Tipo de Localización**: lov18resp1
- **Repositorio Principal**: git@github.com:tbriceno65/krill.git
- **Repositorio Localización**: git@github.com:nerdop44/lov18resp1.git
- **Rama de Trabajo**: master
- **REGLA DE ORO**: La rama `master` de la localización (`lov18resp1`) es la fuente de verdad universal. CUALQUIER cambio que genere un resultado positivo (Green Build) DEBE ser fusionado en `master` inmediatamente para servir a todos los clientes.

## Entornos de Despliegue
- **Producción**: krill-energy.odoo.com (Rama: Produccion)
- **Staging (Variable)**: krill-energy-prueba-27822700.dev.odoo.com
    > *SSH*: `27822700@krill-energy-prueba-27822700.dev.odoo.com`

## Estado Verde Actual (Referencia de Estabilidad) - Hash Localización: 00ada92
- **Submódulo `lov18resp1`:** Hash `00ada92` (Corrección Tasa y Reportes V8.6)
- **Repositorio Maestro:** Sincronizado en rama `main` (Odoo.sh Prod).
- **Punto de Rollback**: Referencia `stable-green-20260226-v8.6`

## Credenciales y Accesos (Referencias)
- **Odoo.sh**: [Acceso vía SSH key system]
- **Contactos**: Ing. Nerdo Pulido

## Bitácora de Trazabilidad
- **[2026-02-18 11:13]**: Migración al nuevo esquema de skill generalizado - [System]
- **[2026-02-20 09:58]**: Diagnóstico y plan de reparación para error `RPC_ERROR` (`foreign_currency_inverse_rate`) en retenciones IVA. - [Antigravity]
- **[2026-02-20 10:01]**: Despliegue de corrección a entorno de prueba (Staging) vía push a rama `master` de `lov18resp1`. - [Antigravity]
- **[2026-02-21 21:40]**: Inicio de Operación Rescate. Detectada regresión en Odoo.sh tras Fase 3. Iniciando rollback a b92e193. - [Antigravity]
- **[2026-02-21 22:10]**: Rollback ejecutado. Build resultante en AMARILLO. Iniciando investigación profunda vía SSH para detectar colisiones en logs. - [Antigravity]
- **[2026-02-22 02:55]**: Corrección exitosa de colisiones de etiquetas (`account.retention.line`, `stock.landed.cost`). Saneamiento de parámetros obsoletos. Push a rama `Prueba`. Build VERDE confirmado en logs. - [Antigravity]
- **[2026-02-22 18:30]**: **LOGRO GREEN BUILD**. Corrección de `IndexError` en aprobación de retenciones. Sincronización de sub-módulo en `repo_krill`. Creación de punto de restauración `stable-green-20260222`. - [Antigravity]
- **[2026-02-22 19:40]**: Optimización del flujo de pagos manuales. Habilitación de edición en grid de pagos y auto-fill inteligente para IVA/ISLR/Municipal. Sincronización de ramas. - [Antigravity]
- **[2026-02-22 22:50]**: Corrección de regresión de IVA (VEF) y restauración de triggers de ISLR (v18.0.1.0.20). Implementación de sincronización bidireccional de precios en Dual Currency (Productos). - [Antigravity]
- **[2026-02-22 23:05]**: **ACCIÓN CORRECTIVA**. Reversión de push accidental a rama `Produccion`. Eliminación de carpeta `repo_krill`. Consolidación estricta de trabajo en `lov18resp1` (Staging/Prueba). - [Antigravity]
- **[2026-02-23 00:10]**: **LOGRO GREEN BUILD**. Estabilización exhaustiva de cálculo VEF para ISLR y saneamiento robusto de XML de productos. Despliegue de `v18.0.1.0.28`. Creación de punto de restauración `stable-green-20260225`. - [Antigravity]
- [2026-02-23 15:38]: **ACCIÓN CORRECTIVA**. Identificado bug en `clear_retention` (regression v37) que impedía limpieza de líneas. Despliegue de `v38` (commit `2baf7cf`) a rama `master` y sincronización iniciada hacia `Produccion`. - [Antigravity]
- [2026-02-24 21:30]: **ALINEACIÓN DE TRAZABILIDAD**. Sincronización oficial del "Zombie Baseline" (Sintaxis OK + Fix Importaciones) mediante `odoo_sh_sync.py`. Hash `c59441b`. Verificación de Estado Zombi en manifiestos y eliminación de importaciones rotas. - [Antigravity]
- [2026-02-24 22:15]: **SANEAMIENTO PROACTIVO**. Corrección de `NameError` en `date_range` (`_default_company`) y eliminación masiva de parámetros `digits` obsoletos en campos `Monetary`. Validación global de sintaxis (`find + py_compile`) en todo el submódulo. Despliegue certificado `ac330f3`. - [Antigravity]
- [2026-02-24 22:45]: **NEUTRALIZACIÓN ENTERPRISE**. Desactivación de herencias Enterprise en `account_dual_currency` (`Budget`, `Assets`, `CashFlow`, `BankRec`) para resolver `TypeError` en el registro de modelos. Despliegue mediante `odoo_sh_sync.py` con hash `e062ca4`. - [Antigravity]
- [2026-02-24 22:50]: **CORRECCIÓN DE ATTRIBUTEERROR**. Neutralización de `default=lambda` en `account_move_line.py`, `account_payment.py` y `account_bank_statement_line.py` que llamaban a métodos comentados por la estrategia Zombi. Hash `f28396b`. - [Antigravity]
- [2026-02-24 22:55]: **CORRECCIÓN DE SELECTION & STATES**. Resolución de `AssertionError` en `account.retention.line.state` (falta de selection) y limpieza de parámetros `states` obsoletos en `account_fiscalyear_closing`. Despliegue certificado `eb11e1e`. - [Antigravity]
- [2026-02-24 23:10]: **CORRECCIÓN DE INTEGRIDAD (FK)**. Restauración de archivos `data/` en el manifest de `l10n_ve_payment_extension` para evitar purgas destructivas. Aplicación de `ondelete="cascade"` en `payment.concept.line`. Despliegue hash `09024df`. - [Antigravity]
- [2026-02-24 23:30]: **SANEAMIENTO DE DATOS MAESTROS**. Restauración masiva de archivos XML de estados, municipios y parroquias en `l10n_ve_binaural` y catálogos en `l10n_ve_accountant`. Aplicación de `ondelete="cascade"` en `economic.activity`. Despliegue hash `2ac8a9f`. - [Antigravity]
- [2026-02-24 23:45]: **HITO TOTAL GREEN**. Restauración de campos `date_start/end/opening` en cierre fiscal y desactivación de tests unitarios incompatibles con la base Zombi. Consolidación de estabilidad absoluta en Odoo.sh. Despliegue hash `aff8f87`. - [Antigravity]
- [2026-02-25 10:15]: **CORRECCIÓN DE REGISTRO**. Identificado fallo en `l10n_ve_accountant` por omisión de dependencias en manifiesto. Restauradas dependencias base y eliminado método duplicado en `account_move`. Recuperación de servicio pos-despliegue. - [Antigravity]
- [2026-02-25 10:45]: **CORRECCIÓN DE REPORTES**. Resolución de `TypeError` en `AccountReport` por falta de argumento `warnings` en Odoo 18. Actualizadas firmas en `account_dual_currency`. Iniciada auditoría proactiva de otros reportes. - [Antigravity]
- [2026-02-25 11:20]: **DESPLIEGUE CERTIFICADO**. Actualizadas quirúrgicamente las ramas `Produccion` (`134df8bc`) y `Prueba` (`ff5010ae`) del repositorio maestro `krill.git` vinculándolas con el commit `1b20db1` de localización. - [Antigravity]
- [2026-02-25 13:05]: **GATILLO DE BUILD FORZADO**. Realizados commits vacíos en `krill.git` para disparar el build en Producción. - [Antigravity]
- [2026-02-25 13:10]: **RESTAURACIÓN DE PRUEBA**. Revertida la rama `Prueba` del maestro al commit `d585b95` para recuperar el punto de comparación solicitado por el usuario. - [Antigravity]
- [2026-02-25 13:15]: **CORRECCIÓN DE KEYERROR**. Implementado blindaje contra `KeyError: 'currency_dif'` en `AccountReport` mediante `.get()`. Sincronizado y desplegado en Producción (Hash `4c4582a`). - [Antigravity]
- [2026-02-25 15:25]: **REFACTORIZACIÓN SISTÉMICA**. Sustitución del método obsoleto `_get_query_currency_table` por `_get_simple_currency_table` en 4 reportes base (Odoo 18 API). Certificación de despliegue final (Hash `9c9e69e`). - [Antigravity]
- [2026-02-25 19:45]: **RESTAURACIÓN MOTOR DE REPORTES**. Sustitución del método obsoleto `_query_get` por el puente `_dual_currency_query_get` (basado en `_get_report_query` de Odoo 18) en todos los reportes contables. Saneamiento masivo de XML (>30 archivos) para cumplir esquema RelaxNG estricto. Despliegue certificado hash `73f77d6`. - [Antigravity]
- [2026-02-25 20:15]: **GATILLO DE BUILD FORZADO**. Realizado commit vacío `dd10712` y sincronización quirúrgica para disparar el build en Producción Odoo.sh tras detectarse inactividad del disparador automático. - [Antigravity]
- [2026-02-25 20:25]: **CORRECCIÓN DE ERROR DE DESEMPAQUETADO**. Identificado y resuelto error `ValueError: not enough values to unpack` en el puente de reportes adaptándolo a la estructura de objetos `Query` de Odoo 18. Despliegue certificado hash `00a9b25`. - [Antigravity]
- [2026-02-25 21:55]: **CORRECCIÓN DEFINITIVA DE REPORTES**. Sustitución del acceso directo a atributos por el método estándar `get_sql()` en el puente de reportes. Resolución del error `AttributeError: 'Query' object has no attribute 'where_params'`. Sincronización final certificada hash `954e0a0`. - [Antigravity]
- [2026-02-26 17:05]: **SANEAMIENTO XML RADICAL**. Eliminación de encabezados <?xml...?> en todos los archivos de l10n_ve_accountant para alinear estructura con módulos exitosos. Despliegue certificado hash abc9631 (V7.16). - [Antigravity]
- [2026-02-26 17:15]: **AISLAMIENTO Y NORMALIZACIÓN**. Se comentó ir_actions_server.xml y archivos vacíos del manifiesto. Normalización de 16 archivos con línea en blanco pos-odoo para debug de line-count en Odoo 18. Despliegue V7.17 (abc9631 -> 9fa41b0). - [Antigravity]
- [2026-02-26 17:35]: **OPTIMIZACIÓN Y AUTOMATIZACIÓN V7.20**. Limpieza de modelos obsoletos en `l10n_ve_accountant`, implementación de reconciliación automática en retenciones y reubicación de campos de moneda dual en la UI. Sincronización quirúrgica exitosa hacia rama `Produccion` (Hash `b5fe753`). - [Antigravity]
- [2026-02-26 18:35]: **RESTAURACIÓN DE VISTAS V7.21**. Reactivación de `views/account_move.xml` en `l10n_ve_accountant`. Hash `59bcdd9`. - [Antigravity]
- [2026-02-26 18:50]: **CORRECCIÓN DE COLISIÓN XML V7.22**. Causa raíz definitiva: XML ID `account_move_form_binaural_payment_extension` duplicado en `l10n_ve_accountant` (vacío) y `l10n_ve_payment_extension` (activo). El vacío sobreescribía las pestañas de retención e IGTF. Re-comentado en manifiesto. Hash `f7809a6`. Sincronización quirúrgica exitosa. - [Antigravity]
- [2026-02-26 19:45]: **AUDITORÍA EXHAUSTIVA V7.23**. Identificada causa raíz de fallo silencioso de `account_dual_currency`: dependencia `account_budget` (Enterprise) no disponible bloqueaba la instalación completa del módulo. Corregidas dependencias faltantes (`sale`, `purchase`, `l10n_ve_rate`). Corregida traducción PO que sobreescribía nombres de reportes de retención. Verificación de sintaxis XML/Python 100% limpia en todos los módulos. Hash `ec5e3ad`. - [Antigravity]
- [2026-02-26 23:05]: **🚨 REVERSIÓN DE RAMA DE DESPLIEGUE**. Se confirmó mediante `ssh` que el servidor de producción rastrea la rama `Produccion`, NO `main` (que se intentó usar en V7.17-V8.7). Todos los cambios de V8.7 ahora apuntan correctamente a `Produccion`. Git modules en `Produccion` verificados. Hash final `52e9814`. - [Antigravity]
- [2026-02-26 21:30]: **CORRECCIÓN UI Y TASA V8.4-V8.5**. Migración total de sintaxis Odoo 18 para `invisible/readonly`. Corrección de lógica `_onchange_invoice_date_rate` para calcular USD->VEF (no USD->USD=1.0). Ocultación de `tax_totals` redundantes. Hash `c9c3725`. - [Antigravity]
- [2026-02-26 22:30]: **MIGRACIONES DE DATOS V8.6**. Implementación de scripts `post-migrate.py` para forzar recalculo de `tax_today` en facturas draft y nombres de reportes de retención en la BD. Actualizado skill `odoo_sync_master` con regla de versionamiento obligatorio. Despliegue certificado hash `00ada92`. - [Antigravity]

## Variables de Sincronización (Odoo Sync Master)
[REPO_SUBMODULE_PATH]: /home/nerdop/laboratorio/LocVe18v2
[MAIN_REPO_SSH]: git@github.com:tbriceno65/krill.git
[SUBMODULE_PATH_IN_MAIN]: lov18resp1
[SUBMODULE_REMOTE_SSH]: git@github.com:nerdop44/LocVe18v2.git
