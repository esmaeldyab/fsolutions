# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResUsers(models.Model):
    _inherit = 'res.users'

    branch_ids = fields.Many2many('res.branch',string="Allowed Branch")
    branch_id = fields.Many2one('res.branch', string= 'Branch')

    def write(self, values):
        if 'branch_id' in values or 'branch_ids' in values:
            self.env['ir.model.access'].call_cache_clearing_methods()
            self.env['ir.rule'].clear_caches()
            #self.has_group.clear_cache(self)
        user = super(ResUsers, self).write(values)
        return user

    def _get_default_warehouse_id(self):
        if self.branch_id:
            branched_warehouse = self.env['stock.warehouse'].search([('branch_id', '=', self.branch_id.id)],limit=1)
            if branched_warehouse:
                return branched_warehouse
        else:
            if self.property_warehouse_id:
                return self.property_warehouse_id
            # !!! Any change to the following search domain should probably
            # be also applied in sale_stock/models/sale_order.py/_init_column.
        return self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)



