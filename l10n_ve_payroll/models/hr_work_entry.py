from odoo import api, Command, fields, models, tools
class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    #reemplazar el metodo create
    @api.model_create_multi
    def create(self, vals_list):
        print("vals_list: ", vals_list)
        for vals in vals_list:
            if vals.get('work_entry_type_id', False):
                if vals['work_entry_type_id'] == self.env.ref('l10n_ve_payroll.work_entry_type_VACA').id:
                    #si la fecha es fin de semana se le cambia el tipo de entrada
                    if fields.Date.from_string(vals.get('date_start')).weekday() in [5,6]:
                        vals['work_entry_type_id'] = self.env.ref('l10n_ve_payroll.work_entry_type_VACA_des_fer').id

        return super(HrWorkEntry, self).create(vals_list)