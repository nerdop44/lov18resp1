
from odoo import models, fields, _
from odoo.exceptions import UserError

class WizStructureCopy(models.TransientModel):
    _name = 'hr.payslip.structure.copy'
    _description = "Wizard para copiar las reglas desde otra estructura"

    structure_id = fields.Many2one('hr.payroll.structure', string="Estructura")

    rule_ids = fields.Many2many('hr.salary.rule', string="Reglas disponibles")

    def copiar_reglas(self):
        for rec in self:
            struct_ids = self.env.context.get('active_ids', [])
            struct_id = self.env['hr.payroll.structure'].browse(struct_ids)
            for l in rec.rule_ids:
                nueva_regla = l.copy()
                nueva_regla.struct_id = struct_id

            #buscar otras entradas
            struct_id.input_line_type_ids = rec.structure_id.input_line_type_ids


