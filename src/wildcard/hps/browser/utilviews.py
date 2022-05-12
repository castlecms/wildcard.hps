# -*- coding: utf-8 -*-
from AccessControl import Unauthorized
from Acquisition import aq_parent
from wildcard.hps.opensearch import WildcardHPSCatalog
from Products.Five import BrowserView
from zope.component import getMultiAdapter


class Utils(BrowserView):

    def convert(self):
        if self.request.method == 'POST':
            authenticator = getMultiAdapter((self.context, self.request),
                                            name=u'authenticator')
            if not authenticator.verify():
                raise Unauthorized

            hpscatalog = WildcardHPSCatalog(self.context)
            hpscatalog.convertToOpenSearch()
        site = aq_parent(self.context)
        self.request.response.redirect('%s/@@wildcardhps-controlpanel' % (
            site.absolute_url()))

    def rebuild(self):
        if self.request.method == 'POST':
            authenticator = getMultiAdapter((self.context, self.request),
                                            name=u'authenticator')
            if not authenticator.verify():
                raise Unauthorized

            self.context.manage_catalogRebuild()

        site = aq_parent(self.context)
        self.request.response.redirect('%s/@@wildcardhps-controlpanel' % (
            site.absolute_url()))
