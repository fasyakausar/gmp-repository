import copy
from odoo import models, fields, api
from odoo.tools import float_round


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    price_subtotal_rounded = fields.Monetary(
        compute='_compute_price_subtotal_rounded',
        currency_field='currency_id',
        store=False,
    )

    @api.depends('price_subtotal')
    def _compute_price_subtotal_rounded(self):
        for line in self:
            line.price_subtotal_rounded = float_round(
                line.price_subtotal, precision_digits=0, rounding_method='HALF-UP')


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _round(self, value):
        return float_round(value, precision_digits=0, rounding_method='HALF-UP')

    def _get_rounded_tax_totals(self):
        self.ensure_one()
        if not self.tax_totals:
            return {}
        totals = copy.deepcopy(self.tax_totals)

        if totals.get('amount_total') is not None:
            totals['amount_total'] = self._round(totals['amount_total'])
            totals['formatted_amount_total'] = self.currency_id.format(totals['amount_total'])

        if totals.get('amount_untaxed') is not None:
            totals['amount_untaxed'] = self._round(totals['amount_untaxed'])
            totals['formatted_amount_untaxed'] = self.currency_id.format(totals['amount_untaxed'])

        for subtotal in totals.get('subtotals', []):
            if subtotal.get('amount') is not None:
                subtotal['amount'] = self._round(subtotal['amount'])
                subtotal['formatted_amount'] = self.currency_id.format(subtotal['amount'])

        for tax_groups in totals.get('groups_by_subtotal', {}).values():
            for tax_group in tax_groups:
                if tax_group.get('tax_group_amount') is not None:
                    tax_group['tax_group_amount'] = self._round(tax_group['tax_group_amount'])
                    tax_group['formatted_tax_group_amount'] = self.currency_id.format(
                        tax_group['tax_group_amount'])

        return totals