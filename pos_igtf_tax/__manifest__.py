{
    'name': '[LocVe] Venezuela: POS IGTF',
    'version': "18.0.1.0.0",
    'author': 'Remake Ing Nerdo Pulido',
    'company': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'maintainer': 'José Luis Vizcaya López remake Ing Nerdo Pulido',
    'website': 'https://github.com/birkot',
    'category': 'LocVe [Localization]',
    'summary': 'IGTF en el POS',
    'depends': ['point_of_sale','pos_show_dual_currency'],
    'data': [
        'views/inherited_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_igtf_tax/static/src/scss/**/*',
            'pos_igtf_tax/static/src/xml/**/*',
            'pos_igtf_tax/static/src/app/**/*.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
}
