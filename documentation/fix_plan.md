# Plan de Corrección - Errores de Instalación en Prueba2

## Errores Identificados

### 1. Error: `crossovered.budget.lines` no existe
**Causa**: El módulo `account_budget` no está instalado en Odoo.sh
**Solución**: Agregar `account_budget` como dependencia en `account_dual_currency/__manifest__.py`

### 2. Error: XPath en `report_saledetails.xml`
**Causa**: El XPath `//span[@t-out='total_paid']` no existe en la vista padre de Odoo 18
**Solución**: Necesitamos verificar la estructura real de la vista en Odoo 18 y actualizar los XPaths

## Acciones a Realizar

### Paso 1: Agregar dependencia de `account_budget`
- Archivo: `account_dual_currency/__manifest__.py`
- Cambio: Agregar `'account_budget'` a la lista de `depends`

### Paso 2: Verificar y corregir XPaths en POS report
- Archivo: `pos_show_dual_currency/views/report_saledetails.xml`
- Necesitamos ver la estructura real de `point_of_sale.pos_session_sales_details` en Odoo 18
- Actualizar los XPaths para que coincidan con la estructura real

### Paso 3: Testing
- Hacer commit y push
- Disparar rebuild en Prueba2
- Verificar instalación
