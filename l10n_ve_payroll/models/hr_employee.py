
from odoo import models, fields,api

class HREmpleyee(models.Model):
    _inherit = 'hr.employee'

    name = fields.Char(
        compute="_compute_name",
        required=False,
        store=True,
        readonly=False, related="")

    identification_id = fields.Char(string="Cédula de Identidad", related='work_contact_id.identification_id')
    nationality = fields.Selection([
        ('V', 'Venezolano'),
        ('E', 'Extranjero'),
        ('P', 'Pasaporte')], string="Tipo Documento", related="work_contact_id.nationality")
    rif = fields.Char(string="RIF", related='work_contact_id.rif')
    islr = fields.Float(string="% ISLR", default=0)

    primer_nombre = fields.Char(string="Primer Nombre", required=True)
    segundo_nombre = fields.Char(string="Segundo Nombre")
    primer_apellido = fields.Char(string="Primer Apellido", required=True)
    segundo_apellido = fields.Char(string="Segundo Apellido")

    #   MINTRA
    tipo_trabajador = fields.Selection(
        [('1', 'De Dirección'), ('2', 'De Inspección o Vigilancia'), ('3', 'Aprendiz Ince'), ('4', 'Pasante'),
         ('5', 'Trabajador Calificado'), ('6', 'Trabajador no Calificado')], default='5', string="Tipo de Trabajador")

    ocupacion = fields.Char(string="Ocupación")
    subproceso = fields.Char(string="Subproceso")
    jornada = fields.Selection(
        [('D', 'Diurno'), ('N', 'Nocturno'), ('M', 'Mixta'), ('R2', 'Rotativo 2 Turnos'), ('R3', 'Rotativo 3 turnos'),
         ('TC', 'De trabajo Continuo')], string="Jornada", default='D')
    fecha_ingreso = fields.Date(string="Fecha de Ingreso")
    sindicalizado = fields.Selection([('N', 'No'), ('S', 'Si')], string="Sindicalizado", default='N')
    lab_domingo = fields.Selection([('N', 'No'), ('S', 'Si')], string="Labora Domingos", default='N')
    prom_hora_lab = fields.Integer(string="Promedio de Horas Laboradas")
    prom_hora_extras = fields.Integer(string="Promedio de Horas Extras")

    prom_hora_noc = fields.Integer(string="Promedio de Horas Nocturnas")
    carga_familiar = fields.Integer(string="Carga Familiar", default=0)
    fam_discap = fields.Selection([('N', 'No'), ('S', 'Si')], string="Familiar con Discapacidad", default='N')
    hijo_benf_guard = fields.Integer(string="Hijos Beneficiarios Guardería", default=0)
    monto_bene_guar = fields.Float(string="Monto Beneficiario Guardería")
    mujer_embarazada = fields.Selection([('N', 'No'), ('S', 'Si')], string="Mujer Embarazada", default='N')

    tipo_sangre = fields.Selection(
        [('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'),
         ('O-', 'O-')], string="Tipo de Sangre")
    alergico_descripcion = fields.Char(string="Alergias")
    patologia = fields.Char(string="Patologías")
    tipo_discapacidad = fields.Char(string="Tipo de Discapacidad")

    enfermedad = fields.Selection([('N', 'No'), ('S', 'Si')], string="Enfermedad", default='N')
    indigena = fields.Selection([('N', 'No'), ('S', 'Si')], string="Indígena", default='N')
    discapauditiva = fields.Selection([('N', 'No'), ('S', 'Si')], string="Discapacidad Auditiva", default='N')
    discapvisual = fields.Selection([('N', 'No'), ('S', 'Si')], string="Discapacidad Visual", default='N')
    discapintelectual = fields.Selection([('N', 'No'), ('S', 'Si')], string="Discapacidad Intelectual", default='N')
    discapmental = fields.Selection([('N', 'No'), ('S', 'Si')], string="Discapacidad Mental", default='N')
    discapmusculo = fields.Selection([('N', 'No'), ('S', 'Si')], string="Discapacidad Muscular", default='N')
    discapotra = fields.Selection([('N', 'No'), ('S', 'Si')], string="Discapacidad Otra", default='N')
    accidente = fields.Selection([('N', 'No'), ('S', 'Si')], string="Accidente", default='N')


    #dotaciones

    zapatos = fields.Selection(
        [('30', '30'),('31', '31'),('32', '32'), ('33', '33'), ('34', '34'), ('35', '35'), ('36', '36'), ('37', '37'), ('38', '38'), ('39', '39'),
         ('40', '40'), ('41', '41'), ('42', '42'), ('43', '43'), ('44', '44'), ('45', '45'), ('46', '46')])
    camisas = fields.Selection(
        [('XS', 'XS'), ('S', 'S'), ('M', 'M'), ('M-L', 'M-L'), ('L', 'L'), ('L-XL', 'L-XL'), ('XL', 'XL'),
         ('XL-XXL', 'XL-XXL'), ('XXL', 'XXL')])
    pantalon = fields.Selection(
        [('24', '24'), ('25', '25'), ('26', '26'), ('27', '27'), ('28', '28'), ('29', '29'), ('30', '30'), ('31', '31'),
         ('32', '32'), ('33', '33'), ('34', '34'), ('35', '35'), ('36', '36'), ('37', '37'), ('38', '38'), ('39', '39'),
         ('40', '40'), ('41', '41'), ('42', '42'), ('43', '43'), ('44', '44'), ('45', '45'), ('46', '46')])
    chemise = fields.Selection(
        [('XS', 'XS'), ('S', 'S'), ('M', 'M'), ('M-L', 'M-L'), ('L', 'L'), ('L-XL', 'L-XL'), ('XL', 'XL'),
         ('XL-XXL', 'XL-XXL'), ('XXL', 'XXL')])

    #prestaciones
    acumulado_prestaciones = fields.Monetary(string="Acumulado Prestaciones", compute="_compute_acumulado_prestaciones")
    acumulado_intereses = fields.Monetary(string="Acumulado Intereses", compute="_compute_acumulado_prestaciones")

    loan_request = fields.Integer('Límite de Solicitud de Préstamo', default=1)

    #familiares
    family_ids = fields.One2many('hr.employee.family', 'employee_id', string='Familiares')

    def _compute_acumulado_prestaciones(self):
        for rec in self:
            acumulado = self.env['hr.employee.prestaciones'].search([('employee_id','=',rec.id)], order='monto_acumulado desc', limit=1)
            if acumulado:
                rec.acumulado_prestaciones = acumulado.monto_acumulado
                rec.acumulado_intereses = acumulado.monto_interes_acumulado
            else:
                rec.acumulado_prestaciones = 0
                rec.acumulado_intereses = 0

    @api.depends("primer_nombre", "segundo_nombre", "primer_apellido", "segundo_apellido")
    def _compute_name(self):
        for partner in self:
            # si partner.primer_apellido es minuscula, pasar a mayuscula
            if partner.primer_apellido:
                partner.primer_apellido = partner.primer_apellido.upper()
            if partner.segundo_apellido:
                partner.segundo_apellido = partner.segundo_apellido.upper()
            if partner.primer_nombre:
                partner.primer_nombre = partner.primer_nombre.upper()
            if partner.segundo_nombre:
                partner.segundo_nombre = partner.segundo_nombre.upper()
            partner.name = " ".join(
                p for p in (partner.primer_apellido, partner.segundo_apellido, partner.primer_nombre, partner.segundo_nombre) if p)

    @api.onchange('work_contact_id')
    def _onchange_work_contact_id(self):
        if self.work_contact_id:
            #obtener nombre de work_contact_id.name y desglozar en 4 campos
            if self.work_contact_id.name:
                nombre = self.work_contact_id.name.split(' ')
                if len(nombre) == 4:
                    self.primer_apellido = nombre[0]
                    self.segundo_apellido = nombre[1]
                    self.primer_nombre = nombre[2]
                    self.segundo_nombre = nombre[3]
                if len(nombre) == 3:
                    self.primer_apellido = nombre[0]
                    self.segundo_apellido = nombre[1]
                    self.primer_nombre = nombre[2]
                    self.segundo_nombre = ''
                if len(nombre) == 2:
                    self.primer_apellido = nombre[0]
                    self.primer_nombre = nombre[1]
                    self.segundo_apellido = ''
                    self.segundo_nombre = ''
                if len(nombre) == 1:
                    self.primer_apellido = nombre[0]
                    self.primer_nombre = ''
                    self.segundo_apellido = ''
                    self.segundo_nombre = ''

            else:
                self.primer_apellido = ''
                self.segundo_apellido = ''
                self.primer_nombre = ''
                self.segundo_nombre = ''

    @api.onchange('user_id')
    def _onchange_user(self):
        if self.user_id:
            self.update(self._sync_user(self.user_id, (bool(self.image_1920))))
            if not self.name:
                self.name = self.user_id.name
            self.work_contact_id = self.user_id.partner_id.id
            self._onchange_work_contact_id()