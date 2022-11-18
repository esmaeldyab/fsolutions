# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date, datetime
from odoo.exceptions import ValidationError
import math

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, AccessError
from odoo.exceptions import UserError
from odoo.addons import decimal_precision as dp
import base64
import xlsxwriter
import io
from werkzeug.urls import url_encode

class Location(models.Model):
    _inherit = "stock.location"

    responsible_id = fields.Many2one('res.users', 'Responsible')

class Picking(models.Model):
    _name = "stock.picking"
    _inherit = ['stock.picking', 'hr.authorization.approval']

    rejection_comment = fields.Text(tracking=True)
    location_responsible_id = fields.Many2one(related='location_dest_id.responsible_id')

    def button_validate(self):
        for rec in self.filtered(lambda r: r.approval_template_id):
            if rec.approval_status != 'approved':
                raise UserError(_("You can't validate this transfer without "
                                  "completing the Approval Mandate "
                                  "signatures."))
        return super().button_validate()

    def action_confirm(self):
        for rec in self:
            template = self.env['hr.authorization.approval.template'].sudo().search(
                [('company_id', '=', rec.company_id.id), ('res_model_id', '=', rec._name)], limit=1)
            if template and rec.picking_type_code == 'internal':
                rec.action_approval_create(template)
        return super().action_confirm()

    def action_approval_send_mail(self, action, line):
        """Override to add request details."""
        self.ensure_one()
        partners = [user.partner_id.id for user in line.get_eligible_users()]
        if action != 'waiting':
            partners=[self.user_id.partner_id.id]
        subject = _('Source Document: %s') % (self.name)
        url = url_encode({'id':self.id,'view_type':'form','action': 'stock.action_picking_tree_all', 'active_model': 'stock.picking'})

        action_url = '/web#' + url
        body = ("<a class='o_document_link' href=%s>%s</a><br> This is request is %s") % (action_url, subject,action)
        odoobot = self.env.ref('base.partner_root')
        self.env['mail.thread'].sudo().message_notify(
            subject=subject,
            body=body,
            author_id=odoobot.id,
            partner_ids=partners,
            email_layout_xmlid='mail.mail_notification_light',
        )


    def action_approval_next_reject(self):
        """Override to go to next request after rejection."""
        super(Picking, self).action_approval_next_reject()
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.reject.wizard',
            'views': [[False, 'form']],
            'target': 'new',

        }


    def get_approval_current_user_data(self, user_field='location_responsible_id'):
        """
        :param user_field: string representing a `Many2one` field pointing at
        `res.users` model to be used to get all the user specific approvals.
        If the owner partner of the request has no user or is a non-it employee,
        we compute the user representing a user in the same division and is
        stored in field `responsible_division_member_user_id` to be sent off to meth
        `get_approval_current_user_data`.
        NOTE: This field is only populated if it needs to be to prevent
        performance degradation.
        :return: call super method
        """
        self.ensure_one()
        if not user_field:
            user_field = 'create_uid'
        return super(Picking, self) \
            .get_approval_current_user_data(user_field)
