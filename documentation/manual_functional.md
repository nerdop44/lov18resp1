# Manual Funcional: Localización Venezuela Odoo 18

Este manual guía a los usuarios en las operaciones diarias utilizando la localización venezolana.

## 1. Configuración Inicial de Compañía
**Ruta:** *Ajustes -> Usuarios y Compañías -> Compañías*

Para que la facturación y los reportes fiscales funcionen, asegúrese de llenar:
*   **Identificación Fiscal (RIF):** Formato correcto (e.g., J-12345678-0).
*   **Tipo de Contribuyente:** Ordinario, Especial, etc. (Esto define las retenciones automáticas).
*   **Dirección Fiscal:** Completa, incluyendo Estado y Municipio (Módulos de localización geográfica).

## 2. Gestión de Tasa de Cambio (Bimonetario)
**Ruta:** *Contabilidad -> Configuración -> Monedas* o Acceso Directo si está configurado.

El sistema opera con dos monedas: Bolívares (Principal) y Dólares (Referencia).
*   **Actualizar Tasa:** Debe actualizar la tasa diariamente para que:
    1.  Los precios en el POS se muestren correctamente en $.
    2.  El IGTF (3%) se calcule sobre la base correcta.
    3.  La nómina calcule los salarios dolarizados al cambio del día.

## 3. Punto de Venta (POS)
### 3.1. Apertura de Sesión
Al abrir la sesión, verá los montos en Caja tanto en Bolívares como en Dólares (Ref).
*   El sistema carga automáticamente la tasa de cambio del día configurada en Contabilidad.

### 3.2. Realizar una Venta
1.  **Selección de Productos:** Verá el precio en Bs y, en pequeño o referencia, el precio en $.
2.  **Pago:**
    *   Haga clic en *Pago*.
    *   Seleccione el método (e.g., "Efectivo USD", "Zelle", "Tarjeta Bs").
    *   **Pago en Divisas:** Si selecciona un método en divisa (configurado como moneda extranjera), el sistema calculará automáticamente el monto en Bs al cambio.
    *   **IGTF (3%):** Si el método de pago está configurado para aplicar IGTF (Divisa Efectivo/Zelle), el sistema agregará automáticamente una línea de impuesto (IGTF) del 3% sobre el monto pagado en esa divisa.

### 3.3. Facturación (Impresora Fiscal)
Al validar el pago:
*   Si tiene impresora fiscal conectada, el ticket saldrá automáticamente.
*   El ticket mostrará los montos en **Bolívares** (Moneda legal).
*   El número de factura fiscal se guardará en el pedido de Odoo para referencia futura.

## 4. Nómina (RRHH)
**Ruta:** *Nómina*

### 4.1. Ficha del Empleado
En la pestaña *Configuración de Nómina* del empleado:
*   **Salario:** Puede definirlo en Bs o en USD (si usa el módulo de salario dual).
*   **Retenciones:** Verifique que el empleado tenga configurado su porcentaje de ISLR si aplica.

### 4.2. Generar Nómina
1.  Ir a *Nómina -> Recibos de Nómina -> Crear*.
2.  Seleccione el empleado y el periodo.
3.  Haga clic en *Calcular Hoja*.
4.  **Verificación:**
    *   Revise la pestaña *Líneas de Nómina*.
    *   Verá conceptos como `Sueldo Base`, `Bono de Alimentación`, `Retención SSO`, `Retención FAOV`, `ISLR`.
    *   Si el salario está en USD, el sistema lo convertirá a Bs a la tasa del día de pago (o la tasa configurada en el lote de nómina).

### 4.3. Recibos y Reportes
*   Puede imprimir el recibo de pago estándar.
*   Para declaraciones (ISLR, FAOV): Use los asistentes en *Informes* para generar los archivos TXT o reportes PDF requeridos por las instituciones.

## 5. Retenciones (Proveedores/Clientes)
El sistema calcula retenciones automáticamente al validar facturas si el Tipo de Contribuyente (Suyo y del Partner) lo amerita.

*   **Facturas de Proveedor:** Al confirmar, se genera el comprobante de retención de IVA/ISLR. Puede imprimirlo desde el botón inteligente "Retenciones" en la factura.
*   **Facturas de Cliente:** Si el cliente es agente de retención, puede registrar la retención recibida para descontarla del saldo a cobrar.
