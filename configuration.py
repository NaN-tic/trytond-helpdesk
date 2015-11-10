# This file is part helpdesk module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton

__all__ = ['HelpdeskConfiguration']


class HelpdeskConfiguration(ModelSingleton, ModelSQL, ModelView):
    'Helpdesk Configuration'
    __name__ = 'helpdesk.configuration'
