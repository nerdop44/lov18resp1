
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import time
from base64 import b64encode, b64decode

class HREmployeeWizardIVSS(models.TransientModel):
    _name = 'hr.employee.wizard.ivss'
    _description = 'Generar conmstancia de trabajo de IVSS FORMA: 14-100'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    observaciones = fields.Text(string='Observaciones')

    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)
    representante_legal_ivss = fields.Many2one('res.partner', string='Representante Legal', related='company_id.representante_legal_ivss')
    numero_patronal = fields.Char(string='Nro. Patronal IVSS', related='company_id.numero_patronal')

    def generar_forma(self):
        for rec in self:
            if not rec.representante_legal_ivss:
                raise ValidationError(_('Debe configurar el representante legal del IVSS en la compañia'))
            if not rec.numero_patronal:
                raise ValidationError(_('Debe configurar el número patronal del IVSS en la compañia'))

            anios = []
            #crear un array con los ultimos 6 años en orden ascendente
            for i in range(6):
                anios.append(datetime.now().year - i)
            #ordenar el array
            anios.sort()

            enero = []
            febrero = []
            marzo = []
            abril = []
            mayo = []
            junio = []
            julio = []
            agosto = []
            septiembre = []
            octubre = []
            noviembre = []
            diciembre = []

            for anio in anios:
                #buscar el el modelo hr.employee.prestaciones los registros del empleado para el año
                prestaciones = self.env['hr.employee.prestaciones'].search([('employee_id','=',rec.employee_id.id),('anio','=',anio)])
                #si no hay registros para el año, rellenar con ceros
                if not prestaciones:
                    enero.append("{:.2f}".format(0))
                    febrero.append("{:.2f}".format(0))
                    marzo.append("{:.2f}".format(0))
                    abril.append("{:.2f}".format(0))
                    mayo.append("{:.2f}".format(0))
                    junio.append("{:.2f}".format(0))
                    julio.append("{:.2f}".format(0))
                    agosto.append("{:.2f}".format(0))
                    septiembre.append("{:.2f}".format(0))
                    octubre.append("{:.2f}".format(0))
                    noviembre.append("{:.2f}".format(0))
                    diciembre.append("{:.2f}".format(0))

                else:
                    #si hay registros, buscar los registros de enero a diciembre
                    ene = prestaciones.filtered(lambda x: x.mes_opera == 1).salario_integral or 0
                    #pasar ene a formato 2 decimales
                    enero.append("{:.2f}".format(ene))
                    feb = prestaciones.filtered(lambda x: x.mes_opera == 2).salario_integral or 0
                    febrero.append("{:.2f}".format(feb))
                    mar = prestaciones.filtered(lambda x: x.mes_opera == 3).salario_integral or 0
                    marzo.append("{:.2f}".format(mar))
                    abr = prestaciones.filtered(lambda x: x.mes_opera == 4).salario_integral or 0
                    abril.append("{:.2f}".format(abr))
                    may = prestaciones.filtered(lambda x: x.mes_opera == 5).salario_integral or 0
                    mayo.append("{:.2f}".format(may))
                    jun = prestaciones.filtered(lambda x: x.mes_opera == 6).salario_integral or 0
                    junio.append("{:.2f}".format(jun))
                    jul = prestaciones.filtered(lambda x: x.mes_opera == 7).salario_integral or 0
                    julio.append("{:.2f}".format(jul))
                    ago = prestaciones.filtered(lambda x: x.mes_opera == 8).salario_integral or 0
                    agosto.append("{:.2f}".format(ago))
                    sep = prestaciones.filtered(lambda x: x.mes_opera == 9).salario_integral or 0
                    septiembre.append("{:.2f}".format(sep))
                    oct = prestaciones.filtered(lambda x: x.mes_opera == 10).salario_integral or 0
                    octubre.append("{:.2f}".format(oct))
                    nov = prestaciones.filtered(lambda x: x.mes_opera == 11).salario_integral or 0
                    noviembre.append("{:.2f}".format(nov))
                    dic = prestaciones.filtered(lambda x: x.mes_opera == 12).salario_integral or 0
                    diciembre.append("{:.2f}".format(dic))



            pdf = self.env['ir.actions.report'].sudo()._render_qweb_pdf("l10n_ve_payroll.action_constancia_ivss_report",
                                                                        data={'employee_id': rec.employee_id,
                                                                                'company_id': rec.company_id,
                                                                                'observaciones': rec.observaciones,
                                                                                'vat': rec.company_id.partner_id.rif.replace('-', '').replace('J', ''),
                                                                                'anios': anios,
                                                                                'enero': enero,
                                                                                'febrero': febrero,
                                                                                'marzo': marzo,
                                                                                'abril': abril,
                                                                                'mayo': mayo,
                                                                                'junio': junio,
                                                                                'julio': julio,
                                                                                'agosto': agosto,
                                                                                'septiembre': septiembre,
                                                                                'octubre': octubre,
                                                                                'noviembre': noviembre,
                                                                                'diciembre': diciembre,
                                                                              })
            # retornar el pdf para descargar
            pdf_name = 'ConmstanciaIVSS.pdf'
            attachment_id = self.env['ir.attachment'].create({
                'name': pdf_name,
                'datas': b64encode(pdf[0]),
                'mimetype': 'application/x-pdf'
            })
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % attachment_id.id,
                'target': 'self',
            }
