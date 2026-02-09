
{
    "name": """[LocVe] Venezuela: POS show dual currency""",
    "summary": """Adds price  of other currency at products in POS""",
    "category": "LocVe [Localization]",
    "version": "18.0.1.0.1",
    "application": False,
    'author': 'Remake Ing Nerdo Pulido',
    'company': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'maintainer': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'website': 'https://github.com/birkot',
    "depends": ["point_of_sale", "stock"],
    "data": [
        "views/pos_payment_method.xml",
        "views/pos_session.xml",
        "views/pos_payment.xml",
        "views/pos_config.xml",
        "views/res_config_settings.xml",
        'views/pos_order.xml',
        'views/report_saledetails.xml',
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'pos_show_dual_currency/static/src/css/pos.css',
            # Legacy assets (commented out for migration)
            # 'pos_show_dual_currency/static/src/js/**/*',
            # 'pos_show_dual_currency/static/src/xml/**/*.xml',
            
            # New Odoo 18 Assets
            'pos_show_dual_currency/static/src/app/**/*',
        ],
    },
    "license": "OPL-1",
    'images': [
        'static/description/thumbnail.png',
    ],
    "price": 100,
    "currency": "USD",
    "auto_install": False,
    "installable": True,
}
