{
    'name': '[LocVe] RC Multi-Moneda: Reportes Contables',
    'version': '18.0.1.0.0',
    'category': 'LocVe [Localization]',
    'license': 'Other proprietary',
    'summary': 'Reportes contables en doble moneda (Bs./Divisa) para Venezuela',
    'description': """
        Módulo complementario a account_dual_currency que habilita la visualización
        de reportes contables (Libro Mayor, Balance, P&L, Flujo de Caja, Impuestos,
        Libro Auxiliar, Cuentas por Pagar/Cobrar vencidas) en la moneda secundaria
        configurada (USD/EUR), con selección de tasa histórica o actualizada (BCV).

        - Selector de moneda en la barra de reportes (Bs. / Divisa)
        - Selector de tasa (Histórica al registro / Actualizada BCV)
        - Compatible con todos los reportes de account_reports (Enterprise)
        - Instalable opcionalmente, sin afectar el resto de la localización
    """,
    'author': 'Ing. Nerdo Pulido',
    'company': 'Remake Ing. Nerdo Pulido',
    'maintainer': 'Ing. Nerdo Pulido',
    'website': 'https://github.com/nerdop44',
    'depends': [
        'account_dual_currency',
        'account_reports',
    ],
    'data': [
        'views/search_template_view.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
