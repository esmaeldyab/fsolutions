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


class Lead(models.Model):
    _name = "crm.lead"
    _inherit = ['crm.lead', 'hr.authorization.approval']

    sales_manager_id = fields.Many2one('res.users',related='team_id.user_id')

    def action_set_won(self):
        for rec in self.filtered(lambda r: r.approval_template_id):
            if rec.approval_status == 'pending':
                raise UserError(_("You can't validate this Lead without "
                                  "completing the Approval Mandate "
                                  "signatures."))
        return super().action_set_won()

    @api.model
    def create(self, vals):
        res = super(Lead, self).create(vals)
        template = self.env['hr.authorization.approval.template'].sudo().search(
            [('company_id', '=', res.company_id.id), ('res_model_id', '=', res._name)], limit=1)
        if template:
            lines = res.action_approval_create(template)
        return res

    def action_approval_send_mail(self, action, line):
        """Override to add request details."""
        self.ensure_one()
        ctx = dict(self.env.context)
        if action != 'waiting':
            ctx.update(mail_subject=("%s , %s has been %s") %
                                    (self._description, self.name, line.status))
            ctx.update(line=self.user_id)
            ctx.update(mail_to=self.user_id.login)
        if action == 'waiting':
            ctx.update(mail_subject=("%s , %s is waiting for your "
                                     "approval") % (self._description, self.name))
        ctx.update(mail_cc=self.user_id.login)
        ctx.update(mail_signature="IT Management Team")
        return super(Lead, self.with_context(**ctx)) \
            .action_approval_send_mail(action, line)


    def get_approval_current_user_data(self, user_field='sales_manager_id'):
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
        return super(Lead, self) \
            .get_approval_current_user_data(user_field)
