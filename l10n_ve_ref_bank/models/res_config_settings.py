from odoo import fields, models, api, _


class ResConfigSetting(models.TransientModel):
    _inherit = "res.config.settings"

    ref_required = fields.Boolean( readonly=False)
