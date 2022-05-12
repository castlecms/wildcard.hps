# -*- coding: utf-8 -*-
from wildcard.hps.indexes import EZCTextIndex
from wildcard.hps.indexes import getIndex
from wildcard.hps.interfaces import IQueryAssembler
from wildcard.hps.utils import getExternalOnlyIndexes
from zope.interface import implementer


@implementer(IQueryAssembler)
class QueryAssembler(object):

    def __init__(self, request, hpscatalog):
        self.hpscatalog = hpscatalog
        self.catalogtool = hpscatalog.catalogtool
        self.request = request

    def normalize(self, query):
        sort_on = []
        sort = query.pop('sort_on', None)
        # default plone is ascending
        sort_order = query.pop('sort_order', 'asc')
        if sort_order in ('descending', 'reverse', 'desc'):
            sort_order = 'desc'
        else:
            sort_order = 'asc'

        if sort:
            for sort_str in sort.split(','):
                sort_on.append({
                    sort_str: {"order": sort_order}
                })
        sort_on.append('_score')
        if 'b_size' in query:
            del query['b_size']
        if 'b_start' in query:
            del query['b_start']
        if 'sort_limit' in query:
            del query['sort_limit']
        return query, sort_on

    def __call__(self, dquery):
        filters = []
        matches = []
        catalog = self.catalogtool._catalog
        idxs = catalog.indexes.keys()
        query = {'match_all': {}}
        external_only_indexes = getExternalOnlyIndexes()
        for key, value in dquery.items():
            if key not in idxs and key not in external_only_indexes:
                continue

            index = getIndex(catalog, key)
            if index is None and key in external_only_indexes:
                # deleted index for plone performance but still need on ES
                index = EZCTextIndex(catalog, key)

            qq = index.get_query(key, value)
            if qq is None:
                continue

            if index is not None and index.filter_query:
                if isinstance(qq, list):
                    filters.extend(qq)
                else:
                    filters.append(qq)
            else:
                if isinstance(qq, list):
                    matches.extend(qq)
                else:
                    matches.append(qq)
        if len(filters) == 0 and len(matches) == 0:
            return query
        else:
            query = {
                'bool': dict()
            }
            if len(filters) > 0:
                query['bool']['filter'] = filters

            if len(matches) > 0:
                query['bool']['should'] = matches
                query['bool']['minimum_should_match'] = 1
            return query
