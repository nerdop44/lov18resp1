# -*- encoding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cesta_ticket = fields.Float(string = 'Cesta ticket Socialista', related='company_id.cesta_ticket', readonly=False)
    por_riesgo = fields.Float(string='% Riesgo Empresa SSO', related='company_id.por_riesgo' , readonly=False)
    por_aporte_sso = fields.Float(string='% Aporte Empleado SSO', related='company_id.por_aporte_sso', readonly=False)

    por_empresa_lph = fields.Float(string='% Aporte Empresa FAOV', related='company_id.por_empresa_lph', readonly=False)
    nro_cuenta_faov = fields.Char(string='Nro. Cuenta FAOV', related='company_id.nro_cuenta_faov', readonly=False)
    por_empleado_lph = fields.Float(string='% Aporte Empleado FAOV', related='company_id.por_empleado_lph', readonly=False)

    por_empresa_rpe = fields.Float(string='% Aporte Empresa RPE', related='company_id.por_empresa_rpe', readonly=False)
    por_empleado_rpe = fields.Float(string='% Aporte Empleado RPE', related='company_id.por_empleado_rpe', readonly=False)

    ivss_id = fields.Many2one('res.partner', 'IVSS', related='company_id.ivss_id', readonly=False)
    banavih_id = fields.Many2one('res.partner', 'BANAVIH', related='company_id.banavih_id', readonly=False)

    salario_minimo = fields.Float(string='Salario Mínimo', related='company_id.salario_minimo', readonly=False)

    periodo_prestaciones = fields.Selection([('mensual', 'Mensual'),('trimetral','Trimestral')], string='Periodo Prestaciones', related='company_id.periodo_prestaciones', readonly=False)
