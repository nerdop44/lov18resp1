{
    'name': '[LOCVE] Venezuela: POS Fiscal Laboratory',
    'version': '18.0.1.1.0',
    'category': 'LocVe [Localization]',
    'summary': 'Technical diagnostic tool for Fiscal Printers (HKA, Bixolon, PnP)',
    'author': 'Remake Ing Nerdo Pulido',
    'website': 'https://github.com/nerdop44/LocVe18v2',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'point_of_sale', 'pos_fiscal_printer'],
    'data': [
        'security/ir.model.access.csv',
        'data/pos_fiscal_command_data.xml',
        'views/pos_fiscal_lab_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pos_fiscal_lab/static/src/app/**/*',
        ],
    },
    'installable': True,
    'application': False,
}
