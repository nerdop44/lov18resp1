
from odoo import models, fields,api

class HRPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    tasa_cambio = fields.Float(store=True, string="Tasa de Cambio",
                               default=lambda self: self._get_default_tasa_cambio(), tracking=True)

    def _get_default_tasa_cambio(self):
        dolar = self.env['res.currency'].search([('name', '=', 'USD')])
        tasa = 1 / dolar.rate
        return tasa

    def write(self, vals):
        res = super(HRPayslipRun, self).write(vals)
        if 'tasa_cambio' in vals:
            for rec in self.slip_ids:
                rec.tasa_cambio = vals['tasa_cambio']
                rec.compute_sheet()
        if 'date_start' in vals or 'date_end' in vals:
            for rec in self.slip_ids:
                if 'date_start' in vals:
                    rec.date_from = vals['date_start']
                if 'date_end' in vals:
                    rec.date_to = vals['date_end']
                rec.compute_sheet()
        return res

    def action_open_report(self):
        return {
                'type': 'ir.actions.client',
                'name': 'Listado Nóminas por Empleados',
                'tag': 'account_report',
                'context': {
                    'report_id': self.env.ref('l10n_ve_payroll.l10n_ve_payroll_report_nomina_empleados').id,
                    'date_from': self.date_start,
                    'date_to': self.date_end,
                    'slip_ids': self.slip_ids.ids,
                    'company_id': self.company_id.id,
                    'previous_options': True,
                }
            }

