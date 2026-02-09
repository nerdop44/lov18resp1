{
    "name": "[LocVe] Binaural Cierre Fiscal",
    "summary": """
       Modulo para Cierre Fiscal """,
    "license": "LGPL-3",
    "author": "Remake Ing Nerdo Pulido",
    "website": "https://binauraldev.com/",
    "category": "LocVe [Localization]",
    "version": "18.0.1.0.0",
    # any module necessary for this one to work correctly
    "depends": [
        "account_fiscal_year_closing",
        "l10n_ve_contact",
        "l10n_ve_rate",
    ],
    # always loaded
    "data": [
        "views/account_fiscalyear_closing.xml",
        "views/account_fiscalyear_closing_template.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": True,
    "binaural": True,
    'installable': True,
}