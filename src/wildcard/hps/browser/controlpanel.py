# -*- coding: utf-8 -*-
from wildcard.hps import logger
from wildcard.hps.opensearch import WildcardHPSCatalog
from wildcard.hps.interfaces import IWildcardHPSSettings
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from z3c.form import form

import math


class WildcardHPSControlPanelForm(RegistryEditForm):
    form.extends(RegistryEditForm)
    schema = IWildcardHPSSettings

    label = u'Wildcard HPS Search Settings'

    control_panel_view = '@@wildcardhps-controlpanel'


class WildcardHPSControlPanelFormWrapper(ControlPanelFormWrapper):
    index = ViewPageTemplateFile('controlpanel_layout.pt')

    def __init__(self, *args, **kwargs):
        super(WildcardHPSControlPanelFormWrapper, self).__init__(*args, **kwargs)
        self.portal_catalog = getToolByName(self.context, 'portal_catalog')
        self.hpscatalog = WildcardHPSCatalog(self.portal_catalog)

    @property
    def connection_status(self):
        try:
            return self.hpscatalog.connection.status()['ok']
        except AttributeError:
            try:
                health_status = self.hpscatalog.connection.cluster.health()['status']
                return health_status in ('green', 'yellow')
            except Exception:
                return False
        except Exception:
            return False

    @property
    def es_info(self):
        try:
            info = self.hpscatalog.connection.info()
            try:
                stats = self.hpscatalog.connection.indices.stats(
                    index=self.hpscatalog.real_index_name
                )['indices'][self.hpscatalog.real_index_name]['primaries']
                size_in_mb = stats['store']['size_in_bytes'] / 1024.0 / 1024.0
                return [
                    ('Cluster Name', info.get('name')),
                    ('OpenSearch Version', info['version']['number']),
                    ('Number of docs', stats['docs']['count']),
                    ('Deleted docs', stats['docs']['deleted']),
                    ('Size', str(int(math.ceil(size_in_mb))) + 'MB'),
                    ('Query Count', stats['search']['query_total'])
                ]
            except KeyError:
                return [
                    ('Cluster Name', info.get('name')),
                    ('OpenSearch Version', info['version']['number'])
                ]
        except Exception:
            logger.warning('Error getting stats', exc_info=True)
            return []

    @property
    def active(self):
        return self.hpscatalog.get_setting('enabled')


WildcardHPSControlPanelView = layout.wrap_form(
    WildcardHPSControlPanelForm,
    WildcardHPSControlPanelFormWrapper)
