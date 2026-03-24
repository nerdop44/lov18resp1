from odoo import api, fields, models, Command
from odoo.tools.float_utils import float_round


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_retention = fields.Boolean(
        string="Is retention",
        help="Check this box if this payment is a retention",
        default=False,
        copy=False,
    )

    payment_type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        copy=False,
    )

#    # === AÑADIR ESTE BLOQUE / CAMPO FALTANTE ===
#    payment_concept_id = fields.Many2one(
#        'payment.concept',
#        string='Concepto de Pago (ISLR)',
#        help="Concepto de pago de ISLR asociado a este pago de retención.",
#        copy=False,
#    )
    # === FIN DEL BLOQUE A AÑADIR ===
    
#    retention_id = fields.Many2one("account.retention", ondelete="cascade")

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "payment_id",
        string="Retention Lines",
        store=True,
        copy=False,
    )

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        domain="[('tax_ids', '!=', False)]",
        string="Invoice Lines",
        store=True,
        copy=False,
    )

    retention_ref = fields.Char(
        string="Retention reference",
        related="retention_id.number",
        store=True,
        copy=False,
    )

    retention_foreign_amount = fields.Float(
        compute="_compute_retention_foreign_amount", store=True, copy=False
    )

       # === AÑADIR ESTE CAMPO ===
    payment_concept_id = fields.Many2one(
        'payment.concept',
        string='Concepto de Pago (ISLR)',
        help="Concepto de pago de ISLR asociado a este pago de retención.",
        copy=False,
    )
    # ==========================

    retention_id = fields.Many2one("account.retention", ondelete="cascade")


    @api.depends("date")
    def _compute_rate(self):
        for payment in self:
            if payment.is_retention and payment.foreign_rate:
                continue
            return super()._compute_rate()

    def _synchronize_to_moves(self, changed_fields):
        """
        Override the original method to:
        1. Change the name of the move based on the retention type
        2. Ensure proper accounting entries for ISLR retentions
        """
        res = super()._synchronize_to_moves(changed_fields)
    
        # Naming logic (existing functionality)
        account_move_name_by_retention_type = {
            "iva": "RIV",
            "islr": "RIS",
            "municipal": "RM",
        }
    
        for payment in self.filtered("is_retention").with_context(
            skip_account_move_synchronization=True
        ):
            if not all((payment.retention_line_ids, payment.retention_id.number)):
                continue
            
            move = payment.move_id
            if not move:
                continue
            
            # 1. Maintain existing naming convention
            move_name = (
                account_move_name_by_retention_type[payment.retention_id.type_retention]
                + f"-{payment.retention_id.number}"
                + f"-{payment.retention_line_ids[0].move_id.name}"
            )
            if payment.retention_id.type_retention == "islr":
                move_name += f"-{payment.retention_line_ids[0].payment_concept_id.name[:5]}"

            vals_to_change = {"name": move_name}
            move.write(vals_to_change)
            move.line_ids.write(vals_to_change)
        
            # 2. Add specific accounting handling for ISLR
            if payment.payment_type_retention == "islr" and move.state == "draft":
                # Get accounts based on payment type and concept
                if payment.partner_type == 'supplier':
                    debit_account = payment.company_id.islr_supplier_retention_account_id
                    credit_account = payment.payment_concept_id.supplier_account_id
                else:
                    debit_account = payment.payment_concept_id.customer_account_id
                    credit_account = payment.company_id.islr_customer_retention_account_id

                if not debit_account or not credit_account:
                    raise UserError(_("Faltan cuentas contables configuradas para ISLR"))

                # Update move lines
                for line in move.line_ids:
                    if line.account_id == debit_account:
                        line.write({
                            'debit': payment.amount if payment.payment_type == 'outbound' else 0,
                            'credit': payment.amount if payment.payment_type == 'inbound' else 0,
                        })
                    elif line.account_id == credit_account:
                        line.write({
                            'debit': payment.amount if payment.payment_type == 'inbound' else 0,
                            'credit': payment.amount if payment.payment_type == 'outbound' else 0,
                        })
    
        return res

    # def _synchronize_to_moves(self, changed_fields):
    #     """
    #     Override the original method to change the name of the move based on the retention type
    #     using the retention's number and the invoice's name of the retention.
    #     """
    #     res = super()._synchronize_to_moves(changed_fields)
    #     account_move_name_by_retention_type = {
    #         "iva": "RIV",
    #         "islr": "RIS",
    #         "municipal": "RM",
    #     }
    #     for payment in self.filtered("is_retention").with_context(
    #         skip_account_move_synchronization=True
    #     ):
    #         if not all((payment.retention_line_ids, payment.retention_id.number)):
    #             continue
    #         move = payment.move_id
    #         move_name = (
    #             account_move_name_by_retention_type[payment.retention_id.type_retention]
    #             + f"-{payment.retention_id.number}"
    #             + f"-{payment.retention_line_ids[0].move_id.name}"
    #         )
    #         if payment.retention_id.type_retention == "islr":
    #             move_name += f"-{payment.retention_line_ids[0].payment_concept_id.name[:5]}"

    #         vals_to_change = {"name": move_name}
    #         move.write(vals_to_change)
    #         move.line_ids.write(vals_to_change)
    #     return res

    def unlink(self):
        for payment in self:
            if payment.retention_line_ids:
                payment.retention_line_ids.write({'payment_id': False})
        return super().unlink()

    def compute_retention_amount_from_retention_lines(self):
        """
        Compute the amount from the retention lines.
        """
        for payment in self:
            payment.amount = sum(payment.retention_line_ids.mapped("retention_amount"))

    @api.depends("retention_line_ids")
    def _compute_retention_foreign_amount(self):
        for payment in self:
            payment.retention_foreign_amount = abs(
                sum(
                    payment.retention_line_ids.mapped(
                        lambda l: float_round(
                            l.foreign_retention_amount,
                            precision_digits=l.retention_id.foreign_currency_id.decimal_places,
                        )
                    )
                )
            )
    @api.onchange("retention_id")
    def onchange_retention_id(self):
        if self.retention_id:
            self.partner_id = self.retention_id.partner_id
            self.partner_type = "supplier" if self.retention_id.type in ("in_invoice", "in_refund") else "customer"
            self.amount = self.retention_id.foreign_total_retention_amount
            self.currency_id = self.retention_id.foreign_currency_id
            self.is_retention = True
            self.payment_type_retention = self.retention_id.type_retention
            
            # Para ISLR, intentar asignar el primer concepto de las líneas
            if self.retention_id.type_retention == 'islr' and self.retention_id.retention_line_ids:
                concept = self.retention_id.retention_line_ids.filtered('payment_concept_id')[:1].payment_concept_id
                if concept:
                    self.payment_concept_id = concept

            # Intentar pre-cargar el diario (Inluyendo Municipal)
            journals = {
                ("iva", "in_invoice"): self.env.company.iva_supplier_retention_journal_id,
                ("iva", "out_invoice"): self.env.company.iva_customer_retention_journal_id,
                ("islr", "in_invoice"): self.env.company.islr_supplier_retention_journal_id,
                ("islr", "out_invoice"): self.env.company.islr_customer_retention_journal_id,
                ("municipal", "in_invoice"): self.env.company.municipal_supplier_retention_journal_id,
                ("municipal", "out_invoice"): self.env.company.municipal_customer_retention_journal_id,
            }
            journal = journals.get((self.retention_id.type_retention, self.retention_id.type))
            if journal:
                self.journal_id = journal
