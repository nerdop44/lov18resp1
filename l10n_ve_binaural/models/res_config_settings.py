from odoo import api,fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    exempt_aliquot_sale = fields.Many2one("account.tax",  readonly=False)
    general_aliquot_sale = fields.Many2one("account.tax",  readonly=False)
    reduced_aliquot_sale = fields.Many2one("account.tax",  readonly=False)
    extend_aliquot_sale = fields.Many2one("account.tax",  readonly=False)
    exempt_aliquot_purchase = fields.Many2one("account.tax",  readonly=False)
    general_aliquot_purchase = fields.Many2one("account.tax",  readonly=False)
    reduced_aliquot_purchase = fields.Many2one("account.tax",  readonly=False)
    extend_aliquot_purchase = fields.Many2one("account.tax",  readonly=False)

    group_sales_invoicing_series = fields.Boolean(
        related="company_id.group_sales_invoicing_series",
        readonly=False,
        implied_group="l10n_ve_binaural.group_sales_invoicing_series",
    )

#     @api.onchange("group_sales_invoicing_series")
#     def _onchange_group_sales_invoicing_series(self):
#         ir_sequence = self.env["ir.sequence"].sudo()
# 
#         series_sequence = ir_sequence.search(
#             ["|", ("code", "=", "series.invoice.correlative"), ("active", "=", False)]
#         )
#         series_sequence.active = self.group_sales_invoicing_series
