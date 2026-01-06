
from odoo import models, fields,api

class HRPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    @api.depends('amount','payslip_id.tasa_cambio')
    def _amount_usd(self):
        #tax_today_id = self.env['res.currency'].search([('name', '=', 'USD')])
        for record in self:
            if record.payslip_id:
                if record.payslip_id.tasa_cambio>0:
                    record.amount_usd = record.amount / record.payslip_id.tasa_cambio
                else:
                    record.amount_usd = record.amount
            else:
                record.amount_usd = record.amount


    amount_usd = fields.Float(string="Importe (USD)", compute="_amount_usd")
