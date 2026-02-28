{
    'name': "Vendedor en POS",
    'summary': """
        Agrega un campo vendedor en POS
        """,
    'author': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'company': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'maintainer': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'website': 'https://github.com/birkot',
    'category': 'Point of Sale',
    "version": "18.0.1.0.0",
    "application": False,
    'depends': ['base', 'point_of_sale', 'hr'],
    'data': [
        'views/pos_config.xml',
        'views/pos_order_view.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_salesman/static/src/app/**/*',
        ],
    },
    "license": "OPL-1",
    "auto_install": False,
    "installable": True,
}
