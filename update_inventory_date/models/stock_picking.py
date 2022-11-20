import json
import time
from ast import literal_eval
from collections import defaultdict
from datetime import date
from itertools import groupby
from operator import itemgetter

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, format_datetime
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import format_date


class StockPicking(models.Model):
    _inherit = "stock.picking"

    effective_date = fields.Datetime('Effective Date', copy=False, readonly=False,
                                     help="Date at which the transfer has been processed or cancelled.")

    @api.constrains('scheduled_date')
    def change_effective_date(self):
        for rec in self:
            if rec.scheduled_date:
                rec.effective_date = rec.scheduled_date

    def _set_scheduled_date(self):
        for picking in self:
            if picking.state in ('cancel'):
                raise UserError(_("You cannot change the Scheduled Date on a done or cancelled transfer."))
            picking.move_lines.write({'date': picking.scheduled_date})

    def action_revalidate(self):
        self.ensure_one()
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        pickings = self.env['stock.picking'].browse(active_ids)
        for picking in pickings:
            picking._action_done()
            # for move in picking.move_lines._get_subcontract_production():
            #     for submove in move.move_raw_ids:
            #         submove._action_done()

    def _action_done(self):
        self.scheduled_date = self.effective_date
        res = super(StockPicking, self.with_context(force_effective_date=self.effective_date))._action_done()
        for pick in self:
            pick.write({'date_done': pick.effective_date})
            pick.move_lines.write({'date': pick.effective_date})
            pick.move_line_ids.write({'date': pick.effective_date})
        return res


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id,
                                   cost):
        self.ensure_one()

        move_lines = self._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id, description)
        date = self._context.get('force_effective_date')
        return {
            'journal_id': journal_id,
            'line_ids': move_lines,
            'date': date,
            'ref': description,
            'stock_move_id': self.id,
            'stock_valuation_layer_ids': [(6, None, [svl_id])],
            'move_type': 'entry',
        }


class Valuation(models.Model):
    _inherit = "stock.valuation.layer"

    move_date = fields.Datetime(related='stock_move_id.date', store=True)
