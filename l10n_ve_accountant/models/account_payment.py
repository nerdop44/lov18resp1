from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

#     def default_alternate_currency(self):
#         """
#         This method is used to get the foreign currency of the company and set it as the default
#         value of the foreign currency field.
# 
#         Returns
#         -------
#         type = int
#             The id of the foreign currency of the company
#         """
#         return self.env.company.currency_foreign_id.id or False
# 
    foreign_currency_id = fields.Many2one(
        "res.currency", default=default_alternate_currency
    )

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
    )
    is_manually_modified = fields.Boolean(
        string="Modified Manually",
        default=False,
        help="Technical field required by enterprise features",
        compute='_compute_manually_modified',
        store=False  # No almacenar en BD para evitar problemas
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    concept = fields.Char()

#     @api.model_create_multi
#     def create(self, vals_list):
#         """
#         Override the create method to set the rate of the payment to its move.
#         """
#         payments = super().create(vals_list)
#         for payment in payments.with_context(skip_account_move_synchronization=True):
#             payment.move_id.write(
#                 {
#                     "foreign_rate": payment.foreign_rate,
#                     "foreign_inverse_rate": payment.foreign_inverse_rate,
#                 }
#             )
#         return payments
# 
#     def _compute_manually_modified(self):
#         """Siempre retorna False para mantener compatibilidad"""
#         for payment in self:
#             payment.is_manually_modified = False
# 
#     def _synchronize_to_moves(self, changed_fields):
#         """
#         Versión final segura del método de sincronización
#         """
#         # 1. Eliminar el campo problemático si está presente
#         changed_fields = set(changed_fields) - {'is_manually_modified'}
#         
#         # 2. Filtrar solo campos existentes
#         valid_fields = [f for f in changed_fields if f in self._fields]
#         
#         # 3. Contexto seguro para toda la sincronización
#         safe_ctx = {
#             'skip_manually_modified_check': True,
#             'skip_account_move_synchronization': True
#         }
#         
#         try:
#             # 4. Sincronización principal con contexto seguro
#             res = super(AccountPayment, self.with_context(**safe_ctx))._synchronize_to_moves(valid_fields)
#             
#             # 5. Manejo especial para tasas cambiarias
#             if {'foreign_rate', 'foreign_inverse_rate'}.intersection(valid_fields):
#                 payments_with_move = self.filtered(lambda p: p.move_id)
#                 if payments_with_move:
#                     # Actualización masiva optimizada
#                     self.env['account.move'].search([
#                         ('id', 'in', payments_with_move.move_id.ids)
#                     ]).write({
#                         'foreign_rate': payments_with_move.foreign_rate,
#                         'foreign_inverse_rate': payments_with_move.foreign_inverse_rate,
#                     })
#             
#             return res
#             
#         except Exception as e:
#             _logger.error(
#                 "Payment sync error (IDs: %s). Error: %s",
#                 self.ids, str(e), exc_info=True
#             )
#             # Reintento sin modificación de campos
#             return super(AccountPayment, self)._synchronize_to_moves([])
# 
    # def _synchronize_to_moves(self, changed_fields):
    #     """
    #     Override the _synchronize_to_moves method to:
    #     1. Handle the missing 'is_manually_modified' field case
    #     2. Set the rate of the payment to its move
    #     """
    #     # Patch for missing field
    #     if 'is_manually_modified' not in self.env['account.move.line']._fields:
    #         self = self.with_context(skip_manually_modified_check=True)
    
    #     res = super()._synchronize_to_moves(changed_fields)
    
    #     if not ("foreign_rate" in changed_fields or "foreign_inverse_rate" in changed_fields):
    #         return res
        
    #     for payment in self.with_context(skip_account_move_synchronization=True):
    #         payment.move_id.write({
    #             "foreign_rate": payment.foreign_rate,
    #             "foreign_inverse_rate": payment.foreign_inverse_rate,
    #         })
    #     return res

    # def _synchronize_to_moves(self, changed_fields):
    #     """
    #     Override the _syncrhonize_to_moves method to set the rate of the payment to its move.
    #     """
    #     res = super()._synchronize_to_moves(changed_fields)
    #     if not (
    #         "foreign_rate" in changed_fields or "foreign_inverse_rate" in changed_fields
    #     ):
    #         return
    #     for payment in self.with_context(skip_account_move_synchronization=True):
    #         payment.move_id.write(
    #             {
    #                 "foreign_rate": payment.foreign_rate,
    #                 "foreign_inverse_rate": payment.foreign_inverse_rate,
    #             }
    #         )
    #     return res

#     def action_post(self):
#         """Versión segura del método de publicación"""
#         # Contexto seguro para evitar problemas
#         safe_ctx = {
#             'skip_manually_modified_check': True,
#             'skip_account_move_synchronization': True,
#             'tracking_disable': True
#         }
#     
#         try:
#             return super(AccountPayment, self.with_context(**safe_ctx)).action_post()
#         except KeyError as e:
#             if 'is_manually_modified' in str(e):
#                 # Reintento con sincronización mínima
#                 _logger.warning("Reintentando action_post sin sincronización para pagos %s", self.ids)
#                 return super(AccountPayment, self.with_context(
#                     skip_account_move_synchronization=True
#                 )).action_post()
#             raise
# 
    # def action_post(self):
    #     """Override action_post to ensure proper context"""
    #     if 'is_manually_modified' not in self.env['account.move.line']._fields:
    #         self = self.with_context(skip_manually_modified_check=True)
    #     return super().action_post()
#     @api.depends("date")
#     def _compute_rate(self):
#         Rate = self.env["res.currency.rate"]
#         for payment in self:
#             if not payment.foreign_currency_id:
#                 payment.foreign_rate = 0.0
#                 payment.foreign_inverse_rate = 0.0
#                 continue
# 
#             rate_values = Rate.compute_rate(
#                 payment.foreign_currency_id.id, payment.date or fields.Date.context_today(self)
#             )
# 
#             # Validación adicional
#             payment.foreign_rate = rate_values.get("foreign_rate", 0.0)
#             payment.foreign_inverse_rate = rate_values.get("foreign_inverse_rate", 0.0)
# 
    # @api.depends("date")
    # def _compute_rate(self):
    #     """
    #     Compute the rate of the payment using the compute_rate method of the res.currency.rate model.
    #     """
    #     Rate = self.env["res.currency.rate"]
    #     for payment in self:
    #         rate_values = Rate.compute_rate(
    #             payment.foreign_currency_id.id, payment.date or fields.Date.today()
    #         )
    #         payment.update(rate_values)

    # @api.onchange("foreign_rate")
    # def _onchange_foreign_rate(self):
    #     """
    #     Onchange the foreign rate and compute the foreign inverse rate
    #     """
    #     Rate = self.env["res.currency.rate"]
    #     for payment in self:
    #         if not bool(payment.foreign_rate):
    #             return
    #         payment.foreign_inverse_rate = Rate.compute_inverse_rate(
    #             payment.foreign_rate
    #         )

    # @api.model
    # def _get_trigger_fields_to_synchronize(self):
    #     original_fields = super()._get_trigger_fields_to_synchronize()
    #     additional_fields = ("foreign_rate", "foreign_inverse_rate")
    #     return original_fields + additional_fields
