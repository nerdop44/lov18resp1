from odoo import api, fields, exceptions, http, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError


class PaymentReport(models.TransientModel):
    _name = "payment.report"
    _description = "Payment Report"

    payment_type = fields.Selection(
        [("outbound", "Outbound"), ("inbound", "Inbound")],
        string="Payment Type",
        default="outbound",
    )
    journal_id = fields.Many2one(
        "account.journal", required=True, domain=[("type", "in", ("bank", "cash"))]
    )
    start_date = fields.Date(string="Start Date", default=fields.Date.context_today, required=True)
    end_date = fields.Date(string="End Date", default=fields.Date.context_today, required=True)
    currency_report_id = fields.Many2one(
        "res.currency",
        string="Ver en Moneda",
        default=lambda self: self.env.company.currency_id_dif,
    )

    def generate_report_payment(self):
        data = {
            "form": {
                "payment_type": self.payment_type,
                "journal_id": self.journal_id.id,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "currency_report_id": self.currency_report_id.id,
                "currency_report_name": self.currency_report_id.name or "",
            }
        }
        return self.env.ref("l10n_ve_accountant.action_report_all_payments").report_action(
            self, data=data
        )
