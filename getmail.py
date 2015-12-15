# This file is part of the helpdesk module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['GetmailServer']
__metaclass__ = PoolMeta


class GetmailServer:
    __name__ = 'getmail.server'
    kind = fields.Selection([
            ('generic', 'Generic'),
            ], 'Kind')
