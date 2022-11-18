# -*- coding: utf-8 -*-
"""Approval Models"""

import logging

from datetime import date, timedelta, datetime
from pytz import timezone, utc
from werkzeug.urls import url_encode
from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError, AccessError

LOGGER = logging.getLogger(__name__)


class AuthorizationApproval(models.Model):
    """Approval Model.

    This is used to define a specific record approval workflow."""
    _name = 'hr.authorization.approval'

    approval_template_id = fields.Many2one('hr.authorization.approval.template',
                                           "Approval Template",
                                           help="The Approval Mandate",
                                           copy=False)
    approve_user_id = fields.Many2one('res.users')
    approval_template_line_ids = fields.One2many(
        related='approval_template_id.line_ids'
    )
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.user.company_id)
    approval_status = fields.Selection(
        [('pending', 'Pending'),
         ('approved', 'Approved'),
         ('rejected', 'Rejected')],
        "Approval Status",
        default='pending',
        readonly=True,
        Tracking=True,
        copy=False
    )
    approvals_todo = fields.Integer("Remaining Approvals",
                                    compute='_compute_approvals_number')
    approvals_done = fields.Integer("Completed Approvals",
                                    compute='_compute_approvals_number')
    approvals_count = fields.Integer("Total Approvals",
                                     compute='_compute_approvals_number')
    approval_line_ids = fields.One2many('hr.authorization.approval.line',
                                        compute='_compute_approval_line_ids')
    approval_next_line_ids = fields.One2many('hr.authorization.approval.line',
                                             compute='_compute_approval_line_ids')

    def _compute_approvals_number(self):
        """Compute total, remaining, and completed approvals."""
        for record in self:
            approvals = self.env['hr.authorization.approval.line'].search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
            ], order='sequence ASC')
            seqs = set(approvals.mapped('sequence'))
            _todo = set(
                approvals.filtered(lambda r: r.status == 'pending')
                    .mapped('sequence')
            )
            _done = set(
                approvals.filtered(lambda r: r.status != 'pending')
                    .mapped('sequence')
            )
            todo = len(_todo - _done)
            done = len(_done)
            total = len(seqs)
            record.approvals_todo = todo
            record.approvals_done = done
            record.approvals_count = total

    def _compute_approval_line_ids(self):
        """Compute authorization approval lines."""
        for record in self:
            approvals = self.env['hr.authorization.approval.line'].search([
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
            ], order='sequence ASC')
            record.approval_line_ids = approvals
            record.approval_next_line_ids = approvals \
                .filtered(lambda r: r.can_approve)

    def get_allowed_users(self, check_stage_approval=False):
        """Compute allowed approval users to see this request.

        Used by inherited models to adjust access rights."""
        self.ensure_one()
        lines = self.env['hr.authorization.approval.line'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('status', '=', 'pending'),
        ])
        users = self.env['res.users']
        for line in lines:
            if check_stage_approval:
                if line.with_context(no_check_user=True) \
                        .check_stage_approval(line):
                    users |= line.get_eligible_users()
            else:
                users |= line.get_eligible_users()
        return users

    def get_approval_current_user_data(self, user_field='create_uid'):
        """Get current user from the record.

        Overridable by child models to use different fields."""
        self.ensure_one()
        if not user_field:
            user_field = 'create_uid'
        user = self[user_field]
        return {
            'department_id': user.department_id,
            'company_id': user.company_id,
            'user': user,
        }

    def action_approval_create(self, template=None):
        """Create approval lines from template.

        This should be called by children models to kick-off the approval
        mandate process."""
        for record in self:
            # check if there's lines already created
            # NOTE: That won't fix race condition issue (if any)
            lines = self.env['hr.authorization.approval.line'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id),
            ])
            if lines:
                continue

            app_lines = []
            if not template:
                template = self.env['hr.authorization.approval.template'] \
                    .search([
                    ('res_model', '=', record._name),('company_id', '=', record.company_id.id)
                ], limit=1)
            if template:
                record.approval_template_id = template.id
                for line in template.line_ids:
                    # check domain of each stage
                    if line.domain and line.domain != '[]':
                        res = record.search(safe_eval(line.domain))
                        if record not in res:
                            continue
                    app_line = self.env['hr.authorization.approval.line'] \
                        .create({
                        'res_model': record._name,
                        'res_id': record.id,
                        'template_line_id': line.id,
                    })
                    app_lines.append(app_line)
                # send the first notification after creation
                if app_lines:
                    app_lines[0].action_send_mail()
            return app_lines

    def action_open_approvals(self):
        """Open approval lines of the current record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Approvals"),
            'res_model': 'hr.authorization.approval.line',
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('res_model', '=', self._name),
                       ('res_id', '=', self.id)],
        }

    def action_approval_next_approve(self):
        """Approve the next lines by the current user"""
        for record in self:
            record.approval_next_line_ids.action_approve()

    def action_approval_next_reject(self):
        """Reject the next lines by the current user"""
        for record in self:
            record.approval_next_line_ids.action_reject()

    def action_approval_line_approve(self, line):
        """Signal line approval for children models use.

        To be implemented by inherited models."""
        pass

    def action_approval_line_reject(self, line):
        """Signal line rejection for children models use.

        To be implemented by inherited models."""
        pass

    def action_approval_approve(self):
        """Store overall approval status as approved."""
        self.write({'approval_status': 'approved'})

    def action_approval_reject(self):
        """Store overall approval status as rejected."""
        self.write({'approval_status': 'rejected'})

    def action_approval_send_mail(self, action, line):
        """Send email to designated parties to notify them.

        This method provides a way to customize the email for inherited
        models using the following context keys:
        - mail_subject: change the mail subject to a different title.
        - mail_partner_to: add a single partner ID (or multiple separated by
                           commas) to the default partners recipients.
        - mail_cc: add a single email address (or multiple separated by
                   commas) to the default CC recipients.
        - mail_details: add a block of details (HTML) to the email.
        - mail_signature: modify the signature of the email footer.
        - mail_reminder: add "Reminder" string to the subject when set to
                         True."""
        self.ensure_one()
        ctx = dict(self.env.context)
        # pass record and line information using context to the email template
        ctx.update(record=self)
        ctx.update(line=line)
        template = self.env.ref(
            'hr_approval_structure'
            '.mail_template_hr_authorization_approval_done'
        )
        if action == 'waiting':
            template = self.env.ref(
                'hr_approval_structure'
                '.mail_template_hr_authorization_approval_line_waiting'
            )
            mail_to = ','.join(line.get_eligible_users()
                               .mapped('email'))
            # Don't send notifications to no-users!!!
            if not mail_to:
                return False
            ctx.update(mail_to=mail_to)
            # record last notification date for reminders
            line.last_notification_date = fields.Date.today()
        # obtain link for the current record
        if not ctx.get('access_link') \
                and hasattr(self, '_notify_get_action_link'):
            ctx.update(access_link=self._notify_get_action_link('view'))
        return template.sudo().with_context(**ctx) \
            .send_mail(line.id, force_send=False)


class AuthorizationApprovalLine(models.Model):
    """Approval Line Model.

    This is used to define a specific approval on a specific record."""
    _name = 'hr.authorization.approval.line'
    _order = 'sequence'

    res_model = fields.Char("Model Name", required=True)
    res_model_id = fields.Many2one('ir.model', "Model",
                                   compute='_compute_model_id', store=True)
    res_id = fields.Integer("Resource ID", required=True)
    template_line_id = fields.Many2one(
        'hr.authorization.approval.template.line',
        "Approval Stage",
        required=True,
        index=True
    )
    template_id = fields.Many2one(
        related='template_line_id.template_id', readonly=True, store=True,
        index=True
    )
    name = fields.Char(related='template_line_id.name', store=True,
                       readonly=True)
    sequence = fields.Integer(related='template_line_id.sequence',
                              store=True, index=True, readonly=True)
    required = fields.Boolean(related='template_line_id.required',
                              store=True, index=True, readonly=True,
                              help="If not, only one approval per sequence is "
                                   "required.")
    user_id = fields.Many2one('res.users', "Approval User", index=True)
    approval_time = fields.Datetime("Approval Time", index=True)
    status = fields.Selection([('pending', 'Pending'),
                               ('approved', 'Approved'),
                               ('rejected', 'Rejected'),
                               ('na', 'N/A')],
                              "Approval Status",
                              default='pending')
    can_approve = fields.Boolean("Can Approve?",
                                 compute='_compute_can_approve',
                                 default=False)
    eligible_user_ids = fields.Many2many('res.users', string="Eligible Users",
                                         compute='_compute_eligible_user_ids')
    last_notification_date = fields.Date("Last Notification Date")

    @api.depends('res_model')
    def _compute_model_id(self):
        """Compute model object from res_model field."""
        for record in self:
            record.res_model_id = self.env['ir.model'].search([
                ('model', '=', record.res_model)
            ], limit=1)

    def _compute_eligible_user_ids(self):
        """Compute eligible users for this line."""
        for record in self:
            record.eligible_user_ids = record.get_eligible_users()

    def get_eligible_users(self):
        """Get eligible users to approve/reject the current stage."""
        self.ensure_one()
        temp_line = self.template_line_id
        result = []
        if temp_line.user_ids:
            result = temp_line.user_ids
        if temp_line.current_user:
            record = self.env[self.res_model].browse(self.res_id)
            user_data = record.get_approval_current_user_data()
            result = user_data['user']
        return result

    @api.model
    def check_stage_approval(self, line):
        """Check the ability to approve provided stage by current user."""
        # if this line has been already approved/rejected, don't repeat it
        if line.status != 'pending':
            return False

        # if the overall record has been recorded as approved/rejected
        # (this line is optional, and has been passed)
        record = self.env[line.res_model].browse(line.res_id)
        if record.approval_status != 'pending':
            return False

        # if this line is not the current stage, or any previous stage
        # has already decided not in favor of the record
        lines = self.search([('res_id', '=', line.res_id),
                             ('res_model', '=', line.res_model)],
                            order='sequence ASC')
        seq = 1
        seq_approval = False
        for _line in lines:
            # any required stage before the current one will deem the
            # current one not ready
            if line.sequence > _line.sequence \
                    and _line.required \
                    and _line.status != 'approved':
                return False

            # any stage contains all optional lines but no single line
            # has been decided will deem the current stage not ready
            if seq < _line.sequence \
                    and seq < line.sequence \
                    and not seq_approval:
                return False

            # also, current sequence with a single line that has decided
            # will deem current stage irrelevant
            if seq < _line.sequence \
                    and not line.required \
                    and seq == line.sequence \
                    and seq_approval:
                return False

            seq = _line.sequence
            seq_approval = _line.status in ('approved', 'na')

        # check current user is one of eligible approval users
        if not self.env.context.get('no_check_user', False) \
                and self.env.user not in \
                line.get_eligible_users():
            return False

        return True

    @api.model
    def check_last_stage(self, line):
        """Check if the provided line is the last approval in the record."""
        lines = self.search([('res_id', '=', line.res_id),
                             ('res_model', '=', line.res_model),
                             ('sequence', '>=', line.sequence),
                             ('id', '!=', line.id)],
                            order='sequence ASC')
        for _line in lines:
            # if there's a stage in the same sequence but still required and
            # pending, the current one is not the last stage
            if line.sequence == _line.sequence \
                    and _line.required \
                    and _line.status == 'pending':
                return False

            # if there's another sequence after the current one, this isn't
            # the last stage
            if line.sequence < _line.sequence:
                return False

        return True

    def _compute_can_approve(self):
        """Compute the current stage ability to be approved/rejected."""
        for line in self:
            line.can_approve = self.check_stage_approval(line)

    def action_approve(self):
        """Switch this stage to approved status."""
        for line in self:
            if not self.can_approve:
                raise UserError(_("You can't approve the request at this "
                                  "stage."))
            line.status = 'approved'
            line.user_id = self.env.user
            line.approval_time = fields.Datetime.now()
            line.action_na()
            record = self.env[line.res_model].browse(line.res_id)
            record.action_approval_line_approve(line)
            # only approval at the last stage will deem the overall approval
            # for the request as approved
            if self.check_last_stage(line):
                record.action_approval_approve()
            line.action_send_mail()

    def action_reject(self):
        """Switch this stage to rejected status."""
        for line in self:
            if not self.can_approve:
                raise UserError(_("You can't reject the request at this "
                                  "stage."))
            line.status = 'rejected'
            line.user_id = self.env.user
            line.approval_time = fields.Datetime.now()
            line.action_na()
            # any rejection at any stage will deem the request rejected
            record = self.env[line.res_model].browse(line.res_id)
            record.action_approval_line_reject(line)
            record.action_approval_reject()
            line.action_send_mail()

    def action_na(self):
        """Mark not-needed approvals as N/A.

        This method called by the approved/rejected line."""
        for line in self:
            domain = [
                ('res_model', '=', line.res_model),
                ('res_id', '=', line.res_id),
                ('status', '=', 'pending'),
            ]
            if line.status == 'approved':
                domain.append(('required', '=', False))
                domain.append(('sequence', '=', line.sequence))
            elif line.status == 'rejected':
                domain.append(('sequence', '>=', line.sequence))
            lines = self.search(domain)
            lines.write({'status': 'na'})

    def action_send_mail(self):
        """Send email for the current and next stages."""
        self.ensure_one()

        record = self.env[self.res_model].browse(self.res_id)

        if self.status != 'pending':
            record.action_approval_send_mail('done', self)

        # search for lines (including the current line) that are eligible for
        # approval right now
        lines = self.search([('res_id', '=', self.res_id),
                             ('res_model', '=', self.res_model),
                             ('status', '=', 'pending'),
                             ('sequence', '>=', self.sequence)],
                            order='sequence ASC')
        for line in lines:
            if self.with_context(no_check_user=True) \
                    .check_stage_approval(line):
                record.action_approval_send_mail('waiting', line)

    def write(self, vals):
        """Override to prevent overriding sequences from list drag'n'drop."""
        if 'sequence' in vals and len(vals) == 1:
            raise AccessError(_("You can't change sequence of approvals."))
        return super(AuthorizationApprovalLine, self).write(vals)
