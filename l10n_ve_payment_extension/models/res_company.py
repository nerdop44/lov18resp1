from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    tax_authorities_logo = fields.Image(max_width=128, max_height=128)
    tax_authorities_name = fields.Char()
    economic_activity_number = fields.Char()

    iva_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.V.A Retentions",
    )
    iva_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.V.A Retentions",
    )

    islr_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier I.S.L.R Retentions",
    )
    islr_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer I.S.L.R Retentions",
    )

    municipal_supplier_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Supplier Municipal Retentions",
    )
    municipal_customer_retention_journal_id = fields.Many2one(
        "account.journal",
        string="Journal for Customer Municipal Retentions",
    )

    condition_withholding_id = fields.Many2one(
        "account.withholding.type",
        string="The condition of this taxpayer requires the withholding of",
    )
    code_visible=fields.Boolean(string="See payment concept code")

    # ==== Digital Signature and Stamp ====
    signature_image = fields.Binary(string="Firma Digital", help="Imagen de la firma del representante legal.")
    stamp_image = fields.Binary(string="Sello de la Empresa", help="Imagen del sello húmedo de la empresa.")
