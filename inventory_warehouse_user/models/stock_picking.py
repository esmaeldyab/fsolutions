from odoo import models, fields, api, exceptions, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare
import datetime


class StockPickingTypeInheritWarhouseUser(models.Model):
    _inherit = 'stock.picking.type'

    def get_user_id(self):
        return self.env.user.id

    user_id = fields.Many2one('res.users', default=get_user_id)
    user_ids = fields.Many2many('res.users')

    def create(self, vals):
        if 'sequence_id' not in vals or not vals['sequence_id']:
            if vals['warehouse_id']:
                wh = self.env['stock.warehouse'].browse(vals['warehouse_id'])
                vals['sequence_id'] = self.env['ir.sequence'].sudo().create({
                    'name': wh.name + ' ' + _('Sequence') + ' ' + vals['sequence_code'],
                    'prefix': wh.code + '/' + vals['sequence_code'] + '/', 'padding': 5,
                    'company_id': wh.company_id.id,
                }).id
            else:
                vals['sequence_id'] = self.env['ir.sequence'].sudo().create({
                    'name': _('Sequence') + ' ' + vals['sequence_code'],
                    'prefix': vals['sequence_code'], 'padding': 5,
                    'company_id': vals.get('company_id') or self.env.company.id,
                }).id

        picking_type = super(StockPickingTypeInheritWarhouseUser, self).create(vals)
        self.clear_caches()
        return picking_type

    def write(self, vals):
        if 'company_id' in vals:
            for picking_type in self:
                if picking_type.company_id.id != vals['company_id']:
                    raise UserError(
                        _(
                            "Changing the company of this record is forbidden at this point, you should rather archive it and create a new one."))
        if 'sequence_code' in vals:
            for picking_type in self:
                if picking_type.warehouse_id:
                    picking_type.sequence_id.sudo().write({
                        'name': picking_type.warehouse_id.name + ' ' + _('Sequence') + ' ' + vals['sequence_code'],
                        'prefix': picking_type.warehouse_id.code + '/' + vals['sequence_code'] + '/', 'padding': 5,
                        'company_id': picking_type.warehouse_id.company_id.id,
                    })
                else:
                    picking_type.sequence_id.sudo().write({
                        'name': _('Sequence') + ' ' + vals['sequence_code'],
                        'prefix': vals['sequence_code'], 'padding': 5,
                        'company_id': picking_type.env.company.id,
                    })
        self.clear_caches()
        return super(StockPickingTypeInheritWarhouseUser, self).write(vals)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _get_picking_type_domain(self):
        return [('warehouse_id', 'in', self.env.user.warehouse_id.ids)]

    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        domain=_get_picking_type_domain,
        required=True, readonly=True,
        states={'draft': [('readonly', False)]})
