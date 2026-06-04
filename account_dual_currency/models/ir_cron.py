from odoo import models, api

class IrCron(models.Model):
    _inherit = 'ir.cron'

    def action_recuperar_tasas_historicas(self):
        # Ejecuta la recuperación únicamente para las monedas configuradas para sincronizar
        monedas = self.env['res.currency'].search([
            ('active', '=', True),
            ('sincronizar', '=', True)
        ])
        for m in monedas:
            m.recuperar_tasas_historicas()
