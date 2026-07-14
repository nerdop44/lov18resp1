# -*- coding: utf-8 -*-
{
    'name': '[LocVe] Retenciones por Intermediación',
    'version': '18.0.1.0.12',
    'summary': 'Manejo dinámico y parametrizable del caso especial de retenciones de IVA e ISLR sobre intermediación comercial.',
    'description': """
Módulo oficial de la localización para gestionar el flujo contable y fiscal de la Retención por Intermediación en Venezuela:
- Gestión dinámica de Casos de Intermediación (Agencias de viaje, corredores de seguros, publicidad, etc.) editables, archivables y duplicables.
- Identificación de líneas de facturas como comisión o fondos de terceros/reembolsos.
- Emisión automática de comprobantes de retención para múltiples beneficiarios (Intermediario y prestador real de servicio) dentro de una misma factura mixta.
- Cumplimiento de cuadratura en Libros de Compra, archivos TXT de IVA y XML de ISLR del SENIAT.
""",
    'author': 'Ing. Nerdo Jose Pulido Aguirre',
    'category': 'Accounting/Localizations/Accountant',
    'depends': [
        'l10n_ve_payment_extension',
        'account_dual_currency',
        'l10n_ve_tax',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/intermediation_case_data.xml',
        'views/intermediation_case_views.xml',
        'views/res_partner_views.xml',
        'views/product_views.xml',
        'views/account_move_views.xml',
        'views/account_retention_views.xml',
        'views/report_retention_templates.xml',
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
    'license': 'LGPL-3',
}


