from odoo import models, fields, api, exceptions, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare
import datetime


class ResUsersInheritWarhouseUser(models.Model):
    _inherit = 'res.users'

    warehouse_id = fields.Many2many('stock.warehouse', store=True, string='Warehouse')

    # @api.model
    def create(self, vals):
        self.clear_caches()
        return super(ResUsersInheritWarhouseUser, self).create(vals)

    # @api.model
    def write(self, vals):
        self.clear_caches()
        return super(ResUsersInheritWarhouseUser, self).write(vals)