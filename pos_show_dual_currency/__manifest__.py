
{
    "name": """[LocVe] Venezuela: POS show dual currency""",
    "summary": """Adds price  of other currency at products in POS""",
    "category": "LocVe [Localization]",
    "version": "18.0.1.0.0",
    "application": False,
    'author': 'Remake Ing Nerdo Pulido',
    'company': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'maintainer': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'website': 'https://github.com/birkot',
    "depends": ["point_of_sale", "stock"],
    "data": [
        "views/pos_payment_method.xml",
        "views/pos_session.xml",
        "views/pos_config.xml",
        "views/res_config_settings.xml",
    ],

    'assets': {
        'point_of_sale.assets': [
            'pos_show_dual_currency/static/src/css/pos.css',
            'pos_show_dual_currency/static/src/js/navbar_patch.js',
            'pos_show_dual_currency/static/src/js/Popups/ClosePosPopup.js',
            'pos_show_dual_currency/static/src/js/**/*.js',
            # New V18 Structure
            'pos_show_dual_currency/static/src/app/**/*.js',
            'pos_show_dual_currency/static/src/app/**/*.xml',
        ],
        'point_of_sale.assets_prod': [
            'pos_show_dual_currency/static/src/css/pos.css',
            'pos_show_dual_currency/static/src/js/Popups/ClosePosPopup.js',
            'pos_show_dual_currency/static/src/app/**/*.js',
            'pos_show_dual_currency/static/src/app/**/*.xml',
        ],
        'point_of_sale._assets_pos': [
            'pos_show_dual_currency/static/src/css/pos.css',
            'pos_show_dual_currency/static/src/js/Popups/ClosePosPopup.js',
            'pos_show_dual_currency/static/src/app/**/*.js',
            'pos_show_dual_currency/static/src/app/**/*.xml',
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
