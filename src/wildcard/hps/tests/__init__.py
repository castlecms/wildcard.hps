# -*- coding: utf-8 -*-
# coding: utf-8
from wildcard.hps import hook
from wildcard.hps.opensearch import WildcardHPSCatalog
from wildcard.hps.interfaces import IWildcardHPSSettings
from wildcard.hps.testing import WildcardHPS_FUNCTIONAL_TESTING
from wildcard.hps.testing import WildcardHPS_INTEGRATION_TESTING
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility

import time
import transaction
import unittest2 as unittest


class BaseTest(unittest.TestCase):

    layer = WildcardHPS_INTEGRATION_TESTING

    def setUp(self):
        super(BaseTest, self).setUp()
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.request.environ['testing'] = True
        self.app = self.layer['app']

        registry = getUtility(IRegistry)
        settings = registry.forInterface(IWildcardHPSSettings, check=False)
        # disable sniffing hosts in tests because docker...
        settings.sniffer_timeout = None
        settings.enabled = True
        settings.sniffer_timeout = 0.0

        self.catalog = getToolByName(self.portal, 'portal_catalog')
        self.hpscatalog = WildcardHPSCatalog(self.catalog)
        self.catalog.manage_catalogRebuild()
        # need to commit here so all tests start with a baseline
        # of OpenSearch enabled
        self.commit()

    def commit(self):
        transaction.commit()

    def clearTransactionEntries(self):
        _hook = hook.getHook(self.hpscatalog)
        _hook.remove = []
        _hook.index = {}

    def tearDown(self):
        super(BaseTest, self).tearDown()
        self.hpscatalog.connection.indices.delete_alias(
            index=self.hpscatalog.real_index_name, name=self.hpscatalog.index_name)
        self.hpscatalog.connection.indices.delete(index=self.hpscatalog.real_index_name)
        self.clearTransactionEntries()
        # Wait for OpenSearch to remove the index
        time.sleep(0.1)


class BaseFunctionalTest(BaseTest):

    layer = WildcardHPS_FUNCTIONAL_TESTING
