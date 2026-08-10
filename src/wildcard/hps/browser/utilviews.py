from AccessControl import Unauthorized
from Acquisition import aq_parent
from Products.Five import BrowserView
from wildcard.hps.opensearch import WildcardHPSCatalog
from zope.component import getMultiAdapter


class Utils(BrowserView):
    def convert(self):
        if self.request.method == "POST":
            authenticator = getMultiAdapter((self.context, self.request), name="authenticator")
            if not authenticator.verify():
                raise Unauthorized

            hpscatalog = WildcardHPSCatalog(self.context)
            hpscatalog.convertToOpenSearch()
        site = aq_parent(self.context)
        self.request.response.redirect(f"{site.absolute_url()}/@@wildcardhps-controlpanel")

    def rebuild(self):
        if self.request.method == "POST":
            authenticator = getMultiAdapter((self.context, self.request), name="authenticator")
            if not authenticator.verify():
                raise Unauthorized

            self.context.manage_catalogRebuild()

        site = aq_parent(self.context)
        self.request.response.redirect(f"{site.absolute_url()}/@@wildcardhps-controlpanel")
