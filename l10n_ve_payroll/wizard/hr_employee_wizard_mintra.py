
from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import time
from base64 import b64encode, b64decode

class HrEmployeeWizardMintra(models.TransientModel):
    _name = 'hr.employee.wizard.mintra'
    _description = 'Generar archivo TXT de MINTRA'

    date_from = fields.Date(string='Fecha de Llegada', default=lambda *a: datetime.now().strftime('%Y-%m-%d'))
    date_to = fields.Date(string='Fecha de Salida',
                          default=lambda *a: (datetime.now() + timedelta(days=(1))).strftime('%Y-%m-%d'))
    tipo_txt = fields.Selection([('fijo','Datos Fijos'),('variable','Datos Variables')],string='Tipo de TXT',default='variable')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company.id)

    def generar_txt(self):
        if self:
            employee_ids = self.env['hr.employee'].search(
                [('active', '=', True), ('company_id', '=', self.company_id.id)])
            if not employee_ids:
                raise UserError(_('No hay empleados activos para generar el archivo'))
            if not self.date_from or not self.date_to:
                raise UserError(_('Debe ingresar las fechas de inicio y fin'))

            # Generar el archivo TXT

            #cabecera
            if self.tipo_txt=='variable':
                txt="cedula;tipo_trabajador;tipo_contrato;fecha_ingreso;cargo;ocupacion;epecializacion;subproceso;salario;jornada;esta_sindicalizado;labora_dia_domingo;promedio_horas_laboradas_sem;promedio_horas_extras_sem;promedio_horas_nocturnas_sem;carga_familiar;posee_familiar_con_discapacidad;hijos_beneficio_guarderia;monto_beneficio_guarderia;es_una_mujer_embarazada\n"
            else:
                txt="nacionalidad;cedula;enfermedad;indigena;discapauditiva;discapacidadvisual;discapintelectual;discapmental;discapmusculo;discapotra;accidente\n"

            #lineas
            for employee in employee_ids:
                valido = self.validar_campos_empleados(employee)
                if self.tipo_txt=='variable':
                    txt=txt+str(employee.identification_id)+";"
                    txt=txt+str(employee.tipo_trabajador)+";"
                    txt=txt+str(employee.contract_id.contract_type_id.code)+";"
                    txt=txt+str(employee.fecha_ingreso)+";"
                    txt=txt+str(employee.job_id.name)+";"
                    txt=txt+str(employee.ocupacion)+";"
                    txt=txt+str(employee.study_field)+";"
                    txt=txt+str(employee.subproceso)+";"
                    txt=txt+str(employee.contract_id.wage).replace('.',',')+";"
                    txt=txt+str(employee.jornada)+";"
                    txt=txt+str(employee.sindicalizado)+";"
                    txt=txt+str(employee.lab_domingo)+";"
                    txt=txt+str(employee.prom_hora_lab or '')+";"
                    txt=txt+str(employee.prom_hora_extras or '')+";"
                    txt=txt+str(employee.prom_hora_noc or '')+";"
                    txt=txt+str(employee.carga_familiar or '')+";"
                    txt=txt+str(employee.fam_discap)+";"
                    txt=txt+str(employee.hijo_benf_guard)+";"
                    txt=txt+str(employee.monto_bene_guar).replace('.',',')+";"
                    txt=txt+str(employee.mujer_embarazada)+"\n"
                else:
                    txt=txt+str(employee.nationality)+";"
                    txt=txt+str(employee.identification_id)+";"
                    txt=txt+str(employee.enfermedad)+";"
                    txt=txt+str(employee.indigena)+";"
                    txt=txt+str(employee.discapauditiva)+";"
                    txt=txt+str(employee.discapvisual)+";"
                    txt=txt+str(employee.discapintelectual)+";"
                    txt=txt+str(employee.discapmental)+";"
                    txt=txt+str(employee.discapmusculo)+";"
                    txt=txt+str(employee.discapotra)+";"
                    txt=txt+str(employee.accidente)+"\n"


            #Guardar el archivo TXT en un attachment y descargarlo
            file_txt = b64encode(txt.encode('utf-8')).decode("utf-8", "ignore")
            file_txt_name = 'MINTRA_%s_%s_%s.txt' % (self.tipo_txt, self.date_from, self.date_to)

            file_base64 = b64encode(txt.encode('utf-8'))
            attachment_id = self.env['ir.attachment'].sudo().create({
                'name': file_txt_name,
                'datas': file_base64
            })
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/{}?download=true'.format(attachment_id.id, ),
                'target': 'current',
            }

    def validar_campos_empleados(self, empleado):
        for e in empleado:
            if not e.ocupacion:
                raise UserError(_('El empleado %s no tiene definido la ocupación') % e.name)
            if not e.subproceso:
                raise UserError(_('El empleado %s no tiene definida el subproceso') % e.name)
            if not e.tipo_sangre:
                raise UserError(_('El empleado %s no tiene definido el tipo de sangre') % e.name)
            if not e.identification_id:
                raise UserError(_('El empleado %s no tiene definido la cédula de identidad') % e.name)
            if not e.fecha_ingreso:
                raise UserError(_('El empleado %s no tiene definida la fecha de ingreso') % e.name)
            if not e.study_field:
                raise UserError(_('El empleado %s no tiene definida una profesión') % e.name)

            return True
