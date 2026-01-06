# -*- encoding: utf-8 -*-

from odoo import models, fields, api

class ResCompany(models.Model):
    _inherit = 'res.company'

    cesta_ticket = fields.Float(string = 'Cesta ticket Socialista', default=1000)
    por_riesgo = fields.Float(string='% Riesgo Empresa SSO', default=10)
    por_aporte_sso = fields.Float(string='% Aporte Empleado SSO', default=4)

    por_empresa_lph = fields.Float(string='% Aporte Empresa FAOV', default=2)
    nro_cuenta_faov = fields.Char(string='Nro. Cuenta FAOV')
    por_empleado_lph = fields.Float(string='% Aporte Empleado FAOV', default=1)

    por_empresa_rpe = fields.Float(string='% Aporte Empresa RPE', default=2)
    por_empleado_rpe = fields.Float(string='% Aporte Empleado RPE', default=0.5)

    ivss_id = fields.Many2one('res.partner', 'IVSS')
    numero_patronal = fields.Char(string='Nro. Patronal IVSS')
    banavih_id = fields.Many2one('res.partner', 'BANAVIH')

    salario_minimo = fields.Float(string='Salario Mínimo', default=130)

    por_empresa_inces = fields.Float(string='% Aporte Empresa INCES', default=2)
    por_empleado_inces = fields.Float(string='% Aporte Empleado INCES', default=0.5)

    dias_utilidades = fields.Integer(string='Días Utilidades', default=30)

    periodo_prestaciones = fields.Selection([('mensual', 'Mensual'),('trimetral','Trimestral')], string='Periodo Prestaciones', default='mensual')

    representante_legal_ivss = fields.Many2one('res.partner', string='Representante Legal')

    def write(self, vals):
        res = super(ResCompany, self).write(vals)
        if 'dias_utilidades' in vals:
            self.env['hr.contract'].search([('company_id','=',self.id)]).write({'dias_utilidades': vals['dias_utilidades']})
        return res



