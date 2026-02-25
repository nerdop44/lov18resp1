{
    "name": "Binaural Impuesto",
    "summary": "Modulo para Impuestos Venezolanos",
    "license": "LGPL-3",
    "author": "Binauraldev",
    "website": "https://binauraldev.com/",
    "category": "Accounting/Localizations/Account Chart",
    "version": "18.0.1.0.2",
    # any module necessary for this one to work correctly
    "depends": ["base", "account", "l10n_ve_rate", "l10n_ve_base"],
    # always loaded
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings.xml",
        "views/account_move.xml",
        "wizard/account_fiscal_book_wizard_view.xml",
        "report/report_fiscal_book.xml",
    ],
    "images": ["static/description/icon.png"],
    "application": False,
    "assets": {
        "web.assets_backend": ["l10n_ve_tax/static/src/components/**/*"],
    },
    "binaural": True,
    "installable": True,
    "application": False,
}
