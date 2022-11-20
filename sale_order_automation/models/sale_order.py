from odoo import api, fields, models, exceptions


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sale_date = fields.Datetime('Actual Date', readonly=True, default=fields.Datetime.now,
                                states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            order.date_order = order.sale_date
            warehouse = order.warehouse_id
            if warehouse.is_delivery_set_to_done and order.picking_ids:
                for picking in order.picking_ids:
                    picking.update({'date_done':order.sale_date,'scheduled_date': order.sale_date})
                    picking.sudo().action_assign()
                    picking.sudo().action_confirm()
                    for mv in picking.move_ids_without_package:
                        mv.quantity_done = mv.product_uom_qty
                    picking.button_validate()
                    picking.update({'date_done':order.sale_date})
            if warehouse.create_invoice and not order.invoice_ids:
                order._create_invoices(grouped=False, final=False, date=order.sale_date)
            if warehouse.validate_invoice and order.invoice_ids:
                for invoice in order.invoice_ids:
                    invoice.update({'date': order.sale_date, 'invoice_date': order.sale_date,
                                    'invoice_date_due': order.sale_date,
                                    'l10n_sa_delivery_date': order.sale_date})
                    invoice.action_post()

        return res

    def action_multi_confirm(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        orders = self.env['sale.order'].browse(active_ids)
        for order in orders:
            order.action_confirm()
