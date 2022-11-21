# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class UniqueOpportunity(models.Model):
    _inherit = ['crm.lead']

    @api.constrains('name')
    def unique_crm_opportunity(self):
        for rec in self:
            name = self.env['crm.lead'].sudo().search(
                [('id', '!=', rec.id), ('name', '=', rec.name)])
            if name:
                raise ValidationError(_('The Opportunity  must be unique !'))
