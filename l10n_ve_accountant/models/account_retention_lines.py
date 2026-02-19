# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class AccountRetentionIvaLine(models.Model):
    _name = "account.retention.iva.line"
    _description = "Account Retention IVA Line"

    def _valid_field_parameter(self, field_name, parameter):
        return parameter == 'digits' or super()._valid_field_parameter(field_name, parameter)


    # ...
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        # ... otros estados que necesites
    ], string='Status', default='draft', readonly=True, copy=False)
    # ...

    # Campo 'name' añadido
    name = fields.Char(
        string="Descripción de Retención IVA",
        compute="_compute_name",
        store=True, # Almacenar el campo para que sea consultable/filtrable
    )

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
        index=True,
    )
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id",
        string="Moneda Extranjera",
        store=True,
        readonly=True,
    )
    # --- CAMBIO: AHORA SE LLAMA foreign_invoice_total ---
    foreign_invoice_total = fields.Monetary( # ¡RENOMBRADO AQUÍ!
        string="Monto de Factura (ME)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    foreign_currency_rate = fields.Float(
        string="Tasa de Cambio (ME)",
        related="move_id.foreign_rate", # ¡Ajusta este campo si tu move_id lo tiene con otro nombre o si no existe!
        digits=(12, 6), # Formato común para tasas de cambio
        readonly=True,
        store=True,
    )
    # ---------------------------------------------------
    # Este es el campo que la vista XML está buscando
    foreign_iva_amount = fields.Monetary(
        string="Monto IVA (ME)",
        currency_field='foreign_currency_id', # Debe apuntar al campo de la moneda
        compute='_compute_foreign_iva_amount',
        store=True,
        readonly=True,
    )
    foreign_rate = fields.Float(
        related="move_id.foreign_rate", string="Tasa Extranjera", store=True, readonly=True
    )
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera",
        store=True,
        readonly=True,
    )
    base_amount = fields.Monetary(
        string="Base Imponible",
        currency_field="company_currency_id",
        digits="Account",
    )
    retention_amount = fields.Monetary(
        string="Monto Retenido",
        currency_field="company_currency_id",
        digits="Account",
    )
    foreign_base_amount = fields.Monetary(
        string="Base Imponible (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    foreign_retention_amount = fields.Monetary(
        string="Monto Retenido (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    # Faltante
    iva_amount = fields.Monetary(
        string="Monto IVA",
        related="move_id.amount_tax", # Ajusta si `amount_tax` no es el IVA puro en tu move_id
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # Faltante
    foreign_iva_amount = fields.Monetary(
        string="Monto IVA (ME)",
        currency_field='foreign_currency_id',
        compute='_compute_foreign_iva_amount',
        store=True,
        readonly=True,
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    invoice_amount = fields.Monetary(
        string="Monto de Factura",
        related="move_id.amount_total", # O podrías ser 'move_id.amount_untaxed', 'move_id.amount_tax', dependiendo de lo que 'invoice_amount' deba representar.
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    iva_amount = fields.Monetary(
        string="Monto IVA",
        related="move_id.amount_tax", # O podrías ser 'move_id.amount_total' si el IVA es el total en algún contexto específico.
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    foreign_invoice_amount = fields.Monetary(
        string="Monto de Factura (ME)",
        related="move_id.foreign_total_billed",  # ¡IMPORTANTE! Verifica que este sea el campo correcto en account.move
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    invoice_total = fields.Monetary(
        string="Total Factura",
        related="move_id.amount_total", # Asumiendo que es el total de la factura relacionada
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto",
        domain="[('type_tax_use', '=', 'purchase'), ('tax_group_id.name', '=', 'IVA')]",
        ondelete="restrict",
    )
    company_currency_id = fields.Many2one(
        related="move_id.company_id.currency_id",
        string="Moneda de la Compañía",
        store=True,
        readonly=True,
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Tipo de Movimiento",
        store=True,
        readonly=True,
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    related_percentage_tax_base = fields.Float(
        string="Porcentaje de Base Imponible Relacionado",
        digits="Account",
        default=0.0,
    )
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )
    # CAMBIO: Añadido el campo 'l10n_ve_tax_type' como related field.
    # Esto permite que el dominio del campo 'tax_id' acceda a 'tax_group_id.l10n_ve_tax_type'
    # sin que Odoo piense que es un campo desconocido en este modelo.
 #   l10n_ve_tax_type = fields.Selection(related='tax_id.tax_group_id.l10n_ve_tax_type', store=True, readonly=True)

    # Método compute para foreign_iva_amount (asegúrate de que iva_amount esté en la moneda de la compañía)
    @api.depends('iva_amount', 'foreign_currency_rate', 'foreign_currency_id', 'company_currency_id')
    def _compute_foreign_iva_amount(self):
        for rec in self:
            if rec.foreign_currency_id and rec.foreign_currency_id != rec.company_currency_id and rec.foreign_currency_rate:
                rec.foreign_iva_amount = rec.iva_amount / rec.foreign_currency_rate
            else:
                rec.foreign_iva_amount = rec.iva_amount # Si no hay ME o tasa, es igual
    @api.constrains("aliquot")
    def _check_aliquot(self):
        for rec in self:
            if rec.aliquot < 0 or rec.aliquot > 100:
                raise ValidationError(
                    _("The aliquot percentage must be between 0 and 100.")
                )

    @api.onchange("aliquot", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.aliquot / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (
                rec.aliquot / 100
            )

class AccountRetentionIslrLine(models.Model):
    _name = "account.retention.islr.line"
    _description = "Account Retention ISLR Line"

    def _valid_field_parameter(self, field_name, parameter):
        return parameter == 'digits' or super()._valid_field_parameter(field_name, parameter)


    # ...
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        # ... otros estados que necesites
    ], string='Status', default='draft', readonly=True, copy=False)
    # ...

    # Campo 'name' añadido
    name = fields.Char(
        string="Descripción de Retención ISLR",
        compute="_compute_name",
        store=True,
    )

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
        index=True,
    )
    related_pay_from = fields.Many2one(
        'res.partner', # O el tipo de modelo del campo relacionado
        string='Pagado Desde',
        related='move_id.partner_id', # <--- Reemplaza 'partner_id' con el campo real de account.move
        readonly=True,
        store=True # Opcional, para que se guarde en la DB
    )
    # **Añade esta línea (o similar, según tu necesidad):**
    payment_concept_id = fields.Many2one(
        'payment.concept',
        string='Concepto de Pago',
        required=True
    )
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id",
        string="Moneda Extranjera",
        store=True,
        readonly=True,
    )
    # --- CAMBIO: AHORA SE LLAMA foreign_invoice_total ---
    foreign_invoice_total = fields.Monetary( # ¡RENOMBRADO AQUÍ!
        string="Monto de Factura (ME)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    foreign_currency_rate = fields.Float(
        string="Tasa de Cambio (ME)",
        related="move_id.foreign_rate", # ¡Ajusta este campo si tu move_id lo tiene con otro nombre o si no existe!
        digits=(12, 6), # Formato común para tasas de cambio
        readonly=True,
        store=True,
    )
    # ---------------------------------------------------
    # Este es el campo que la vista XML está buscando
    foreign_iva_amount = fields.Monetary(
        string="Monto IVA (ME)",
        currency_field='foreign_currency_id', # Debe apuntar al campo de la moneda
        compute='_compute_foreign_iva_amount',
        store=True,
        readonly=True,
    )
    foreign_rate = fields.Float(
        related="move_id.foreign_rate", string="Tasa Extranjera", store=True, readonly=True
    )
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera",
        store=True,
        readonly=True,
    )
    base_amount = fields.Monetary(
        string="Base Imponible",
        currency_field="company_currency_id",
        digits="Account",
    )
    retention_amount = fields.Monetary(
        string="Monto Retenido",
        currency_field="company_currency_id",
        digits="Account",
    )
    # Faltante
    related_percentage_fees = fields.Float(
        string="Porcentaje de Honorarios Relacionados",
        digits="Account",
        default=0.0,
    )
    # Faltante
    related_amount_subtract_fees = fields.Monetary(
        string="Monto a Restar de Honorarios",
        currency_field="company_currency_id",
        digits="Account",
        default=0.0,
    )
    foreign_base_amount = fields.Monetary(
        string="Base Imponible (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    foreign_retention_amount = fields.Monetary(
        string="Monto Retenido (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    invoice_amount = fields.Monetary(
        string="Monto de Factura",
        related="move_id.amount_total", # O podrías ser 'move_id.amount_untaxed', 'move_id.amount_tax', dependiendo de lo que 'invoice_amount' deba representar.
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    iva_amount = fields.Monetary(
        string="Monto IVA",
        related="move_id.amount_tax", # O podrías ser 'move_id.amount_total' si el IVA es el total en algún contexto específico.
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    foreign_invoice_amount = fields.Monetary(
        string="Monto de Factura (ME)",
        related="move_id.foreign_total_billed",  # ¡IMPORTANTE! Verifica que este sea el campo correcto en account.move
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    invoice_total = fields.Monetary(
        string="Total Factura",
        related="move_id.amount_total", # Asumiendo que es el total de la factura relacionada
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto",
        domain="[('type_tax_use', '=', 'purchase'), ('tax_group_id.name', '=', 'ISLR')]",
        ondelete="restrict",
    )
    company_currency_id = fields.Many2one(
        related="move_id.company_id.currency_id",
        string="Moneda de la Compañía",
        store=True,
        readonly=True,
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Tipo de Movimiento",
        store=True,
        readonly=True,
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    related_percentage_tax_base = fields.Float(
        string="Porcentaje de Base Imponible Relacionado",
        digits="Account",
        default=0.0,
    )
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )
    # CAMBIO: Añadido el campo 'l10n_ve_tax_type' como related field.
#    l10n_ve_tax_type = fields.Selection(related='tax_id.tax_group_id.l10n_ve_tax_type', store=True, readonly=True)


    @api.constrains("aliquot")
    def _check_alicuot_percentage(self):
        for rec in self:
            if rec.aliquot < 0 or rec.aliquot > 100:
                raise ValidationError(
                    _("The aliquot percentage must be between 0 and 100.")
                )

    @api.onchange("aliquot", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.aliquot / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (
                rec.aliquot / 100
            )

class AccountRetentionMunicipalLine(models.Model):
    _name = "account.retention.municipal.line"
    _description = "Account Retention Municipal Line"

    def _valid_field_parameter(self, field_name, parameter):
        return parameter == 'digits' or super()._valid_field_parameter(field_name, parameter)


    # ...
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        # ... otros estados que necesites
    ], string='Status', default='draft', readonly=True, copy=False)
    # ...

    # Campo 'name' añadido
    name = fields.Char(
        string="Descripción de Retención Municipal",
        compute="_compute_name",
        store=True,
    )

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
        index=True,
    )
    foreign_currency_id = fields.Many2one(
        related="move_id.foreign_currency_id",
        string="Moneda Extranjera",
        store=True,
        readonly=True,
    )
    # --- CAMBIO: AHORA SE LLAMA foreign_invoice_total ---
    foreign_invoice_total = fields.Monetary( # ¡RENOMBRADO AQUÍ!
        string="Monto de Factura (ME)",
        related="move_id.foreign_total_billed",
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    foreign_currency_rate = fields.Float(
        string="Tasa de Cambio (ME)",
        related="move_id.foreign_rate", # ¡Ajusta este campo si tu move_id lo tiene con otro nombre o si no existe!
        digits=(12, 6), # Formato común para tasas de cambio
        readonly=True,
        store=True,
    )
    # ---------------------------------------------------
    # Este es el campo que la vista XML está buscando
    foreign_iva_amount = fields.Monetary(
        string="Monto IVA (ME)",
        currency_field='foreign_currency_id', # Debe apuntar al campo de la moneda
        compute='_compute_foreign_iva_amount',
        store=True,
        readonly=True,
    )
    foreign_rate = fields.Float(
        related="move_id.foreign_rate", string="Tasa Extranjera", store=True, readonly=True
    )
    foreign_inverse_rate = fields.Float(
        related="move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera",
        store=True,
        readonly=True,
    )
    base_amount = fields.Monetary(
        string="Base Imponible",
        currency_field="company_currency_id",
        digits="Account",
    )
    retention_amount = fields.Monetary(
        string="Monto Retenido",
        currency_field="company_currency_id",
        digits="Account",
    )
    foreign_base_amount = fields.Monetary(
        string="Base Imponible (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    foreign_retention_amount = fields.Monetary(
        string="Monto Retenido (ME)",
        currency_field="foreign_currency_id",
        digits="Account",
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    invoice_amount = fields.Monetary(
        string="Monto de Factura",
        related="move_id.amount_total", # O podrías ser 'move_id.amount_untaxed', 'move_id.amount_tax', dependiendo de lo que 'invoice_amount' deba representar.
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    iva_amount = fields.Monetary(
        string="Monto IVA",
        related="move_id.amount_tax", # O podrías ser 'move_id.amount_total' si el IVA es el total en algún contexto específico.
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    foreign_invoice_amount = fields.Monetary(
        string="Monto de Factura (ME)",
        related="move_id.foreign_total_billed",  # ¡IMPORTANTE! Verifica que este sea el campo correcto en account.move
        currency_field="foreign_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    aliquot = fields.Float(
        string="Alicuota (%)", digits="Account", default=0.0
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    invoice_total = fields.Monetary(
        string="Total Factura",
        related="move_id.amount_total", # Asumiendo que es el total de la factura relacionada
        currency_field="company_currency_id",
        store=True,
        readonly=True,
    )
    # ---------------------------------
    tax_id = fields.Many2one(
        "account.tax",
        string="Impuesto",
        domain="[('type_tax_use', '=', 'purchase'), ('tax_group_id.name', '=', 'Municipal')]",
        ondelete="restrict",
    )
    company_currency_id = fields.Many2one(
        related="move_id.company_id.currency_id",
        string="Moneda de la Compañía",
        store=True,
        readonly=True,
    )
    move_type = fields.Selection(
        related="move_id.move_type",
        string="Tipo de Movimiento",
        store=True,
        readonly=True,
    )
    # --- CAMBIO: AÑADIDO ESTE CAMPO ---
    related_percentage_tax_base = fields.Float(
        string="Porcentaje de Base Imponible Relacionado",
        digits="Account",
        default=0.0,
    )
    date = fields.Date(
        related="move_id.date", string="Fecha de Factura", store=True
    )
    # Faltante
    economic_activity_id = fields.Many2one(
        'economic.activity',
        string='Actividad Económica',
        required=True
    )
    # CAMBIO: Añadido el campo 'l10n_ve_tax_type' como related field.
#    l10n_ve_tax_type = fields.Selection(related='tax_id.tax_group_id.l10n_ve_tax_type', store=True, readonly=True)


    @api.constrains("aliquot")
    def _check_alicuot_percentage(self):
        for rec in self:
            if rec.aliquot < 0 or rec.aliquot > 100:
                raise ValidationError(
                    _("The aliquot percentage must be between 0 and 100.")
                )

    @api.onchange("aliquot", "base_amount", "foreign_base_amount")
    def _onchange_retention_amounts(self):
        for rec in self:
            rec.retention_amount = rec.base_amount * (rec.aliquot / 100)
            rec.foreign_retention_amount = rec.foreign_base_amount * (
                rec.aliquot / 100
            )
