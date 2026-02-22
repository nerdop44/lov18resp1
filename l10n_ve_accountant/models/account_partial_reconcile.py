from odoo import fields, models


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    debit_move_foreign_inverse_rate = fields.Float(
        related="debit_move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera (Débito)",
        store=True,
        index=True,
    )
    credit_move_foreign_inverse_rate = fields.Float(
        related="credit_move_id.foreign_inverse_rate",
        string="Tasa Inversa Extranjera (Crédito)",
        store=True,
        index=True,
    )
# from odoo import fields, models

# class AccountPartialReconcile(models.Model):
#     _inherit = "account.partial.reconcile"

#     debit_move_foreign_inverse_rate = fields.Float(
#         related="debit_move_id.move_id.foreign_inverse_rate", # ¡Ruta corregida!
#         store=True,
#         index=True,
#     )
#     credit_move_foreign_inverse_rate = fields.Float(
#         related="credit_move_id.move_id.foreign_inverse_rate", # ¡Ruta corregida!
#         store=True,
#         index=True,
#     )
