# Guía de Instalación: Localización Venezolana (LocVe18v2) en Odoo.sh

Esta guía detalla el proceso técnico para desplegar la localización venezolana en un proyecto de Odoo.sh para su cliente.

## 1. Requisitos Previos
*   **Proyecto Odoo.sh**: Acceso como administrador o desarrollador al proyecto.
*   **Repositorio GitHub**: Acceso al repositorio de Odoo.sh (`user/repo`).
*   **Repositorio de la Localización**: Acceso al repositorio donde se alojan los módulos (`LocVe18v2`).
*   **Clave de Despliegue (Deploy Key)**: Si el repositorio de la localización es privado, necesitarás configurar una clave SSH.

## 2. Estructura de Repositorio (Submódulo)
La mejor práctica para mantener la localización actualizada y separada del código custom del cliente es usar **Submódulos de Git**.

### Paso 1: Agregar el Submódulo
En su máquina local, dentro de la carpeta raíz del repositorio del cliente:

```bash
# Agregar el repositorio de la localización como submódulo en la carpeta 'localizacion'
git submodule add -b 18.0 <URL_DEL_REPO_DE_LOCALIZACION> localizacion

# Ejemplo:
# git submodule add -b 18.0 git@github.com:SuEmpresa/LocVe18v2.git localizacion
```

### Paso 2: Configurar Odoo.sh (Deploy Key)
Si el repositorio es privado:
1.  Valle al proyecto en Odoo.sh -> **Settings** -> **Submodules**.
2.  Copie la **Public Key** que muestra Odoo.sh.
3.  Vaya al repositorio de la localización en GitHub -> **Settings** -> **Deploy Keys**.
4.  Agregue la clave copiada (Título: "Odoo.sh Project X").

### Paso 3: Commit y Push
Suba los cambios al repositorio del cliente para que Odoo.sh detecte los nuevos módulos.

```bash
git add .gitmodules localizacion
git commit -m "[ADD] Localización Venezuela como submódulo"
git push origin master  # o la rama de desarrollo
```

## 3. Instalación de Módulos (Orden Crítico)
Una vez que el build en Odoo.sh esté verde, conéctese a la base de datos e instale los módulos en el siguiente orden estricto para evitar errores de dependencias:

### Fase 1: Núcleo y Datos Maestros
1.  `l10n_ve_binaural` (Base técnica)
2.  `l10n_ve_base`
3.  `l10n_ve_rate` (Tasas de cambio)
4.  `l10n_ve_tax` (Impuestos)
5.  `l10n_ve_contact` (Contactos/RIF)
6.  `l10n_ve_invoice` (Facturación)

### Fase 2: Configuración Fiscal y Contable
7.  `l10n_ve_ref_bank` (Referencias Bancarias)
8.  `l10n_ve_location` (Ubicaciones geográficas)
9.  `l10n_ve_tax_payer` (Contribuyentes)
10. `l10n_ve_igtf` (Impuesto a Grandes Transacciones)
11. `l10n_ve_accountant` (Reportes y asientos)

### Fase 3: Cierre Fiscal (Opcional pero recomendado)
12. `account_fiscal_year_closing`
13. `l10n_ve_account_fiscalyear_closing`

### Fase 4: Punto de Venta (POS) y Dualidad
**Nota:** Asegúrese de tener instalados los módulos base de Odoo (`point_of_sale`, `account_accountant`).

14. `l10n_ve_payment_extension`
15. `account_dual_currency` (**Crítico**: Maneja la contabilidad bimonetaria)
16. `pos_show_dual_currency` (Muestra $ en POS)
17. `pos_igtf_tax` (Cálculo IGTF en POS)
18. `pos_fiscal_printer` (Integración Impresora Fiscal)

### Fase 5: Nómina (RRHH)
**Requisito:** Debe tener instalado Odoo Enterprise Payroll (`hr_payroll`).

19. `l10n_ve_payroll`

## 4. Configuración Post-Instalación

1.  **Compañía:**
    *   Ir a *Ajustes -> Compañía*.
    *   Configurar RIF, NIT y Tipo de Contribuyente.
    *   **Moneda:** Configurar la moneda principal (VEF/VES) y la moneda secundaria (USD).

2.  **Contabilidad Dual:**
    *   Ir a *Contabilidad -> Configuración -> Ajustes*.
    *   Activar "Doble Moneda".
    *   Definir la "Moneda de Referencia" (USD).

3.  **Tasa de Cambio:**
    *   Cargar la tasa inicial en *Contabilidad -> Monedas -> Tasas*.

4.  **Diarios Fiscales:**
    *   Configurar los diarios de Ventas/Compras para usar las secuencias fiscales correctas (Nro de Control).

## 5. Actualizaciones Futuras
Para actualizar la localización en el futuro:

```bash
# En su máquina local
cd localizacion
git pull origin 18.0
cd ..
git add localizacion
git commit -m "[UPD] Actualizar localización"
git push
```
Esto disparará un nuevo build en Odoo.sh con el código actualizado.
