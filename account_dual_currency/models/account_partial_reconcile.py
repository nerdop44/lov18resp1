from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from datetime import date


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    company_currency_id_dif = fields.Many2one(
        comodel_name='res.currency',
        string="Moneda Empresa (Dual)",
        related='company_id.currency_id_dif')

    # ==== Amount fields ====
    amount_usd = fields.Monetary(
        currency_field='company_currency_id_dif',
        help="Always positive amount concerned by this matching expressed in the company currency.", default=0)

    def _compute_max_date(self):
        """Override defensivo para Odoo 18.

        En Odoo 18, _compute_max_date hace max(debit_move_id.date, credit_move_id.date).
        Si alguna de las fechas es False (bool), Python lanza TypeError al comparar
        bool > datetime.date. Esto ocurre en flujos bimonetarios de pagos con monto
        base = 0 donde se crean partials manualmente.
        Este override filtra los valores False antes de llamar a max().
        """
        for partial in self:
            dates = [
                d for d in [partial.debit_move_id.date, partial.credit_move_id.date]
                if d and isinstance(d, date)
            ]
            partial.max_date = max(dates) if dates else fields.Date.context_today(partial)
