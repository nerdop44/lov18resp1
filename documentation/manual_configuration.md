# Manual de Configuración: Localización Venezuela Odoo 18

Guía técnica para administradores y consultores encargados de configurar la localización.

## 1. Módulos Base y Compañía
### 1.1. Plan de Cuentas
Asegúrese de instalar un plan de cuentas base compatible o configurar uno personalizado que incluya cuentas para:
*   IVA Débito/Crédito Fiscal.
*   Retenciones de IVA por Pagar/Cobrar.
*   Retenciones de ISLR por Pagar.
*   IGTF por Pagar (Pasivo).
*   Diferencia en Cambio (Ganancia/Pérdida).

### 1.2. Configuración de Impuestos
**Ruta:** *Contabilidad -> Configuración -> Impuestos*
*   Los impuestos de IVA (16%, 8%, 0%) se crean automáticamente.
*   **IGTF:** Verifique que exista el impuesto "IGTF 3%" (o créelo):
    *   Cálculo: Porcentaje del importe.
    *   Monto: 3.00%.
    *   Etiqueta en Factura: IGTF.
    *   Cuenta de Impuestos: Cuenta de Pasivo IGTF por Pagar.

## 2. Contabilidad Bimonetaria (Dual Currency)
### 2.1. Ajustes Generales
**Ruta:** *Contabilidad -> Configuración -> Ajustes*
*   Sección *Currencies*:
    *   Activar *Multi-Currencies*.
    *   Activar *Dual Currency*.
    *   **Currency Reference:** Seleccionar USD.

### 2.2. Diarios
Para cada diario (Banco/Caja) que maneje moneda extranjera:
*   Campo *Moneda*: Establecer en USD.
*   Campo *Cuenta de Beneficio/Pérdida*: Configurar cuentas de Diferencial Cambiario.

## 3. Punto de Venta (POS)
### 3.1. Métodos de Pago
**Ruta:** *Punto de Venta -> Configuración -> Métodos de Pago*
Para métodos en Divisas (e.g., Zelle, Efectivo USD):
1.  **Diario:** Seleccionar un diario con moneda USD.
2.  **Moneda:** USD.
3.  **Integración IGTF:**
    *   Marcar casillas relacionadas con "Aplicar IGTF" o "Foreign Exchange" (según versión específica instalada: `x_is_foreign_exchange`).
    *   Esto activa el motor de cálculo del 3% en `pos_igtf_tax`.

### 3.2. Impresora Fiscal
Si usa `pos_fiscal_printer`:
1.  Conecte la impresora física al equipo donde corre el navegador (si usa Proxy/IoT) o al servidor.
2.  En la configuración del POS (*Punto de Venta -> Configuración -> Ajustes -> Hardware*):
    *   Activar *Impresora Fiscal*.
    *   Seleccionar driver (HKA, Vmax, etc.).
    *   **Puerto:** Configurar puerto serial (e.g., `/dev/ttyUSB0` o `COM3`).
    *   **Baudrate:** Generalmente 9600.

## 4. Nómina (Payroll)
### 4.1. Reglas Salariales y Contabilidad
**Crítico:** Las reglas salariales NO traen cuentas contables por defecto.
**Ruta:** *Nómina -> Configuración -> Reglas*
Debe editar regla por regla para asignar la cuenta de Débito/Crédito:
*   **Sueldos y Salarios (SQUIN/SMENS):** Débito: Gasto Nomina, Crédito: Nómina por Pagar.
*   **Retención SSO/FAOV/RPE (Empleado):** Crédito: Cuentas de Pasivo (Retenciones por Pagar).
*   **Aportes Patronales:** Débito: Gasto Aporte, Crédito: Pasivo Aporte.

### 4.2. Estructuras
Verifique que las estructuras (Semanal, Quincenal, Mensual) tengan las reglas correctas asociadas.

## 5. Contactos y Retenciones Automatizadas
**Ruta:** *Contactos*
Para cada Partner (Proveedor/Cliente):
*   Pestaña *Fiscal/Contabilidad*:
    *   **Tipo de Contribuyente:** Define si retiene o no.
    *   **Porcentaje de Retención:** (Si aplica especial).
    *   Verificar que `l10n_ve_tax_payer` esté activo para ver estos campos.
