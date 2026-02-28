# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class PosOrderReport(models.Model):
    _inherit = "report.pos.order"

    salesman_id = fields.Many2one('hr.employee', string='Vendedor')

    def _select(self):
        return super(PosOrderReport, self)._select() + ", s.salesman_id as salesman_id"

    def _group_by(self):
        return super(PosOrderReport, self)._group_by() + ", s.salesman_id"