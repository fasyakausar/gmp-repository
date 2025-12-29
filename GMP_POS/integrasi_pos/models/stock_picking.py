from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import random

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_integrated = fields.Boolean(string="Integrated", default=False, readonly=True, tracking=True)
    is_updated = fields.Boolean(string="Updated", default=False, readonly=True, tracking=True)
    vit_trxid = fields.Char(string="Transaction ID")
    # target_location = fields.Many2one('master.warehouse', string="Target Location")
    targets = fields.Char(string="Target Locations")