{
    'name': "[LocVe] Venezuela: Account Dual Currency",
    'version': "18.0.1.0.90",
    'category': 'LocVe [Localization]',
    'license': 'Other proprietary',
    'summary': """Esta aplicación permite manejar dualidad de moneda en Contabilidad.""",
    'author': 'Remake Ing Nerdo Pulido',
    'company': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'maintainer': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'website': 'https://github.com/birkot',
    'description': """
    
        - Mantener como moneda principal Bs y $ como secundaria.
        - Facturas en Bs pero manteniendo deuda en $.
        - Tasa individual para cada Factura de Cliente y Proveedor.
        - Tasa individual para Asientos contables.
        - Visualización de Débito y Crédito en ambas monedas en los apuntes contables.
        - Conciliación total o parcial de $ y Bs en facturas.
        - Registro de pagos en facturas con tasa diferente a la factura.
        - Registro de anticipos en el módulo de Pagos de Odoo, manteniendo saldo a favor en $ y Bs.
        - Informe de seguimiento en $ y Bs a la tasa actual.
        - Reportes contables en $ (Vencidas por Pagar, Vencidas por Cobrar y Libro mayor de empresas)
        - Valoración de inventario en $ y Bs a la tasa actual

    """,
    'depends': [
                'base','l10n_ve_base','l10n_ve_rate','account','account_reports','account_followup','web',
                'stock_account','account_accountant','analytic','stock_landed_costs','mail',
                'account_asset','product',
                'sale','purchase',
                # 'account_budget',  # DESHABILITADO: no disponible en todos los entornos Enterprise
                ],
    'data':[
        'security/ir.model.access.csv',
        'security/res_groups.xml',
        'views/res_currency.xml',
        'views/res_config_settings.xml',
        'views/account_move_view.xml',
        'views/account_move_line.xml',
        # 'views/search_template_view.xml',
        'wizard/account_payment_register.xml',
        'views/account_payment.xml',
        'views/product_template.xml',
        'views/stock_landed_cost.xml',
        'views/stock_valuation_layer.xml',
        # 'views/account_journal_dashboard.xml',
        'data/decimal_precision.xml',
        'data/cron.xml',
        'data/channel.xml',
        'views/effective_date_change.xml',
        'views/product_template_attribute_value.xml',
        'views/account_asset.xml',
        # 'views/view_bank_statement_line_tree_bank_rec_widget.xml',
        'wizard/generar_retencion_igtf_wizard.xml',
        'views/account_analytic_account.xml',
        'views/account_analytic_line.xml',
        'views/product_pricelist.xml',
        'views/sale_order_view.xml',
        'views/purchase_order_view.xml',
        # 'views/crossovered_budget_lines.xml',  # Disabled: requires account_budget to be installed first
    ],
    'assets': {
       'web.assets_backend': [
           'account_dual_currency/static/src/xml/trm.xml',
           'account_dual_currency/static/src/js/trm.js',
       ],
    },
    'images': [
        'static/description/thumbnail.png',
    ],
    'live_test_url': 'https://demo16-venezuela.odoo.com/web/login',
    "price": 2990,
    "currency": "USD",
    'installable' : True,
    'application' : False,
}

