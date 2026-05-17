from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    iva_supplier_retention_journal_id = fields.Many2one(
        related="company_id.iva_supplier_retention_journal_id", readonly=False
    )
    iva_customer_retention_journal_id = fields.Many2one(
        related="company_id.iva_customer_retention_journal_id", readonly=False
    )

    islr_supplier_retention_journal_id = fields.Many2one(
        related="company_id.islr_supplier_retention_journal_id", readonly=False
    )
    islr_customer_retention_journal_id = fields.Many2one(
        related="company_id.islr_customer_retention_journal_id", readonly=False
    )

    municipal_supplier_retention_journal_id = fields.Many2one(
        related="company_id.municipal_supplier_retention_journal_id", readonly=False
    )
    municipal_customer_retention_journal_id = fields.Many2one(
        related="company_id.municipal_customer_retention_journal_id", readonly=False
    )
    
    condition_withholding_id = fields.Many2one(
        related='company_id.condition_withholding_id', readonly=False
    )
    code_visible=fields.Boolean(related='company_id.code_visible',readonly=False)
    signature_stamp_signature = fields.Binary(
        related="company_id.signature_stamp_signature",
        string="Firma de la Empresa",
        readonly=False,
    )
    signature_stamp_stamp = fields.Binary(
        related="company_id.signature_stamp_stamp",
        string="Sello de la Empresa",
        readonly=False,
    )
