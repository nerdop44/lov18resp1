from odoo import api, fields, models, _


class KrillSignatureStampWizard(models.TransientModel):
    _name = "krill.signature.stamp.wizard"
    _description = "Asistente de Firma y Sello de la Empresa"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    signature = fields.Binary(
        string="Firma de la Empresa (Rúbrica)",
    )
    stamp = fields.Binary(
        string="Sello de la Empresa (Sello Húmedo)",
    )

    @api.model
    def default_get(self, fields_list):
        res = super(KrillSignatureStampWizard, self).default_get(fields_list)
        company = self.env.company
        if "signature" in fields_list or not fields_list:
            res["signature"] = company.signature_stamp_signature
        if "stamp" in fields_list or not fields_list:
            res["stamp"] = company.signature_stamp_stamp
        if "company_id" in fields_list or not fields_list:
            res["company_id"] = company.id
        return res

    def action_save(self):
        self.ensure_one()
        self.company_id.write({
            "signature_stamp_signature": self.signature,
            "signature_stamp_stamp": self.stamp,
        })
        return {"type": "ir.actions.act_window_close"}
