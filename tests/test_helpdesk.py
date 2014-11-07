#!/usr/bin/env python
# This file is part of the helpdesk module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends


class HelpdeskTestCase(unittest.TestCase):
    'Test Helpdesk module'

    def setUp(self):
        trytond.tests.test_tryton.install_module('helpdesk')

    def test0005views(self):
        'Test views'
        test_view('helpdesk')

    def test0006depends(self):
        'Test depends'
        test_depends()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        HelpdeskTestCase))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
