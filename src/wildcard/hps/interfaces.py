# -*- coding: utf-8 -*-
from zope import schema
from zope.interface import Interface


class IWildcardHPSLayer(Interface):
    pass


class IWildcardHPSCatalog(Interface):
    pass


class IMappingProvider(Interface):
    def get_index_creation_body(self):
        pass

    def __call__(self):
        pass


class IAdditionalIndexDataProvider(Interface):
    def __call__(self):
        pass


class IReindexActive(Interface):
    pass


class IQueryAssembler(Interface):
    def normalize(self, query):
        pass

    def __call__(self, query):
        pass


class IWildcardHPSSettings(Interface):
    enabled = schema.Bool(
        title=u'Enabled',
        default=False
    )

    external_only_indexes = schema.Set(
        title=u'Indexes for which all searches are done externally',
        default={'Title', 'Description', 'SearchableText'},
        value_type=schema.TextLine(title=u'Index'),
    )
