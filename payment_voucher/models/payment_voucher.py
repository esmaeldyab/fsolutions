from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, date_utils, email_split, email_re, html_escape, is_html_empty
from odoo.tools.misc import formatLang, format_date, get_lang

from datetime import date, timedelta
from collections import defaultdict
from contextlib import contextmanager
from itertools import zip_longest
from hashlib import sha256
from json import dumps

import ast
import json
import re
import warnings


class PaymentVoucher(models.Model):
    _name = "account.payment.voucher"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'sequence.mixin']
    _description = "Payment Voucher"

    name = fields.Char(string='Number', copy=False, readonly=False, store=True, index=True,
                       tracking=True, default="New")
    date = fields.Date(
        string='Date',
        required=True,
        index=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        copy=False,
        tracking=True,
        default=fields.Date.context_today
    )
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, readonly=True,
                                 states={'draft': [('readonly', False)]},
                                 domain=[('type', 'in', ('bank','cash'))],
                                 check_company=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 store=True, readonly=True, default=lambda x: x.env.company)
    company_currency_id = fields.Many2one(string='Company Currency', readonly=True,
                                          related='company_id.currency_id')
    currency_id = fields.Many2one('res.currency', store=True, readonly=True, tracking=True, required=True,
                                  states={'draft': [('readonly', False)]},
                                  string='Currency',
                                  default=lambda x: x.env.company.currency_id)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account',
                                          index=True, readonly=True, states={'draft': [('readonly', False)]},
                                          check_company=True, copy=True)
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags', readonly=True,
                                        states={'draft': [('readonly', False)]}, check_company=True, copy=True)
    ref = fields.Char(string='Reference', copy=False, tracking=True)
    amount_total = fields.Monetary(string='Total', store=True, readonly=True,
                                   compute='_compute_amount')
    amount_tax = fields.Monetary(string='Total', store=True, readonly=True,
                                 compute='_compute_amount')
    state = fields.Selection(selection=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string='Status', required=True, readonly=True, copy=False, tracking=True,
        default='draft')
    collect_entry = fields.Boolean()
    voucher_type = fields.Selection(selection=[
        ('in_voucher', 'In Voucher'),
        ('out_voucher', 'Out Voucher'),
    ], string='Type', required=True, store=True, index=True, readonly=True, tracking=True)
    move_id = fields.Many2one('account.move')
    voucher_line_ids = fields.One2many('account.payment.voucher.line', 'voucher_id', string='Voucher Items', copy=True,
                                       readonly=True,
                                       states={'draft': [('readonly', False)]})

    @api.depends('voucher_line_ids.amount','voucher_line_ids.tax_amount')
    def _compute_amount(self):
        for rec in self:
            rec.amount_total = sum(rec.voucher_line_ids.mapped('amount'))
            rec.amount_tax = sum(rec.voucher_line_ids.mapped('tax_amount'))

    @api.onchange('analytic_account_id', 'analytic_tag_ids')
    def onchange_analytic(self):
        if self.analytic_tag_ids:
            for line in self.voucher_line_ids:
                line.analytic_tag_ids = self.analytic_tag_ids.ids
        if self.analytic_account_id:
            for line in self.voucher_line_ids:
                line.analytic_account_id = self.analytic_account_id.id

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('You cannot delete this Voucher !'))
        return super(PaymentVoucher, self).unlink()

    def action_draft(self):
        for rec in self:
            rec.move_id.button_draft()
            rec.state = 'draft'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'posted':
                rec.move_id.button_draft()
                rec.move_id.button_cancel()
            rec.state = 'cancel'

    def action_post(self):
        for rec in self:
            move_line_values = []
            if rec.amount_total == 0.0:
                raise ValidationError(_('Posted Voucher entry must have amount'))
            total_payment_amount = 0.0
            total_payment_amount_currency = 0.0
            for line in rec.voucher_line_ids:
                if line.amount <= 0.0:
                    raise ValidationError(_("You can't add Negative or Zero value in Amount!"))
                taxes = line.tax_ids.with_context(round=True).compute_all(line.amount, line.currency_id, 1.0)
                balance = line.currency_id._convert(taxes['total_excluded'], self.env.company.currency_id,
                                                    line.company_id,
                                                    rec.date)
                amount_currency = taxes['total_excluded']
                total_amount = 0.0
                total_amount_currency = 0.0
                move_line_src = {
                    'name': (str(line.name or "") + "/") if line.name else "" + str(line.ref or ""),
                    'account_id': line.account_id.id,
                    'amount_currency': amount_currency,
                    'debit': balance if rec.voucher_type == 'out_voucher' else 0.0,
                    'credit': balance if rec.voucher_type == 'in_voucher' else 0.0,
                    'journal_id': rec.journal_id.id,
                    'partner_id': line.partner_id.id,
                    'currency_id': line.currency_id.id,
                    'analytic_account_id': line.analytic_account_id.id,
                    'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                    'tax_tag_ids': [(6, 0, taxes['base_tags'])],
                }
                move_line_values.append(move_line_src)
                total_amount += balance
                total_amount_currency += move_line_src['amount_currency']
                total_payment_amount += balance
                total_payment_amount_currency += move_line_src['amount_currency']
                # taxes move lines
                for tax in taxes['taxes']:
                    balance = line.currency_id._convert(tax['amount'], self.env.company.currency_id, rec.company_id,
                                                        rec.date)
                    amount_currency = tax['amount']

                    if tax['tax_repartition_line_id']:
                        rep_ln = self.env['account.tax.repartition.line'].browse(tax['tax_repartition_line_id'])
                        base_amount = self.env['account.move']._get_base_amount_to_display(tax['base'], rep_ln)
                        base_amount = line.currency_id._convert(base_amount, self.env.company.currency_id,
                                                                rec.company_id,
                                                                rec.date)
                    else:
                        base_amount = None

                    move_line_tax_values = {
                        'name': tax['name'],
                        'quantity': 1,
                        'debit': balance if rec.voucher_type == 'out_voucher' else 0.0,
                        'credit': balance if rec.voucher_type == 'in_voucher' else 0.0,
                        'amount_currency': amount_currency,
                        'account_id': tax['account_id'] or move_line_src['account_id'],
                        'tax_repartition_line_id': tax['tax_repartition_line_id'],
                        'tax_tag_ids': tax['tag_ids'],
                        'tax_base_amount': base_amount,
                        'partner_id': line.partner_id.id,
                        'currency_id': line.currency_id.id,
                        'analytic_account_id': line.analytic_account_id.id if tax['analytic'] else False,
                        'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)] if tax['analytic'] else False,
                    }
                    total_amount += balance
                    total_amount_currency += move_line_tax_values['amount_currency']
                    total_payment_amount += balance
                    total_payment_amount_currency += move_line_tax_values['amount_currency']
                    move_line_values.append(move_line_tax_values)
                if not rec.collect_entry:
                    move_line_dst = {
                        'name': _("Payment Voucher") + (("/"+str(line.name)) if line.name else "") + " / " + str(rec.date),
                        'debit': total_amount if rec.voucher_type == 'in_voucher' else 0.0,
                        'credit': total_amount if rec.voucher_type == 'out_voucher' else 0.0,
                        'account_id': rec.journal_id.default_account_id.id,
                        'date_maturity': rec.date,
                        'amount_currency': total_amount_currency,
                        'currency_id': line.currency_id.id,
                        'partner_id': line.partner_id.id,
                        'exclude_from_invoice_tab': True,
                    }
                    move_line_values.append(move_line_dst)
            if rec.collect_entry:
                move_line_dst = {
                    'name': _("Payment Voucher") + (("/"+str(line.ref)) if line.ref else "" )+ " / " + str(rec.date),
                    'debit': total_payment_amount if rec.voucher_type == 'in_voucher' else 0.0,
                    'credit': total_payment_amount if rec.voucher_type == 'out_voucher' else 0.0,
                    'account_id': rec.journal_id.default_account_id.id,
                    'date_maturity': rec.date,
                    'amount_currency': total_payment_amount_currency,
                    'currency_id': rec.currency_id.id,
                    'exclude_from_invoice_tab': True,
                }
                move_line_values.append(move_line_dst)
            if not rec.move_id:
                move_vals = {
                    'ref': rec.ref,
                    'date': rec.date,
                    'journal_id': rec.journal_id.id,
                    'line_ids': [(0, 0, line) for line in move_line_values],
                }
                move_id = self.env['account.move'].create(move_vals)
                move_id.action_post()
                self.write({'move_id': move_id.id, 'name': move_id.name, 'state': 'posted'})
            else:
                rec.move_id.line_ids = [(5, 0, 0)]
                rec.move_id.update({
                    'line_ids': [(0, 0, line) for line in move_line_values]})
                rec.move_id.action_post()
                self.write({'name': rec.move_id.name, 'state': 'posted'})


class PaymentVoucherLine(models.Model):
    _name = "account.payment.voucher.line"

    voucher_id = fields.Many2one('account.payment.voucher', index=True, required=True, readonly=True, auto_join=True,
                                 ondelete="cascade",
                                 check_company=True)
    name = fields.Char(string='Label')
    amount = fields.Monetary(string='Amount in Currency', store=True, copy=True,
                             help="The amount expressed in an optional other currency if it is a multi-currency entry.")
    company_id = fields.Many2one(related='voucher_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency',
                                  string='Currency',
                                  default=lambda x: x.env.company.currency_id)
    bank_id = fields.Many2one('res.bank')
    ref = fields.Char(string='Ref')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags')
    account_id = fields.Many2one('account.account', string='Account',
                                 index=True, ondelete="cascade",
                                 required=True,
                                 domain="[('deprecated', '=', False), ('company_id', '=', 'company_id'),('is_off_balance', '=', False)]",
                                 check_company=True,
                                 tracking=True)
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes",
        context={'active_test': False},
        check_company=True,
        help="Taxes that apply on the base amount")
    tax_amount = fields.Monetary(compute="_compute_tax_amount")
    partner_id = fields.Many2one('res.partner', string='Partner', ondelete='restrict')

    @api.depends('tax_ids')
    def _compute_tax_amount(self):
        for rec in self:
            taxes = rec.tax_ids.with_context(round=True).compute_all(rec.amount, rec.currency_id, 1.0)
            amount = 0.0
            for tax in taxes['taxes']:
                amount += tax['amount']
            rec.tax_amount = amount
