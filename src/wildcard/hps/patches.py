# -*- coding: utf-8 -*-
from collective.elasticsearch.es import ElasticSearchCatalog
from plone import api
from wildcard.hps import hook
from wildcard.hps.opensearch import WildcardHPSCatalog

def catalog_object(self, object, uid=None, idxs=[],
                   update_metadata=1, pghandler=None):
    escatalog = ElasticSearchCatalog(self)
    if escatalog.enabled is True:
        return escatalog.catalog_object(object, uid, idxs, update_metadata, pghandler)
    hpscatalog = WildcardHPSCatalog(self)
    return hpscatalog.catalog_object(object, uid, idxs, update_metadata, pghandler)


def uncatalog_object(self, uid, obj=None, *args, **kwargs):
    escatalog = ElasticSearchCatalog(self)
    if escatalog.enabled is True:
        return escatalog.uncatalog_object(uid, obj, *args, **kwargs)
    hpscatalog = WildcardHPSCatalog(self)
    return hpscatalog.uncatalog_object(uid, obj, *args, **kwargs)


def unrestrictedSearchResults(self, REQUEST=None, **kw):
    escatalog = ElasticSearchCatalog(self)
    if escatalog.enabled is True:
        return escatalog.searchResults(REQUEST, check_perms=False, **kw)
    hpscatalog = WildcardHPSCatalog(self)
    return hpscatalog.searchResults(REQUEST, check_perms=False, **kw)


def safeSearchResults(self, REQUEST=None, **kw):
    escatalog = ElasticSearchCatalog(self)
    if escatalog.enabled is True:
        return escatalog.searchResults(REQUEST, check_perms=True, **kw)
    hpscatalog = WildcardHPSCatalog(self)
    return hpscatalog.searchResults(REQUEST, check_perms=True, **kw)


def manage_catalogRebuild(self, *args, **kwargs):
    """ need to be publishable """
    escatalog = ElasticSearchCatalog(self)
    if escatalog.enabled is True:
        return escatalog.manage_catalogRebuild(**kwargs)
    hpscatalog = WildcardHPSCatalog(self)
    return hpscatalog.manage_catalogRebuild(**kwargs)


def manage_catalogClear(self, *args, **kwargs):
    """ need to be publishable """
    escatalog = ElasticSearchCatalog(self)
    if escatalog.enabled is True:
        return escatalog.manage_catalogClear(*args, **kwargs)
    hpscatalog = WildcardHPSCatalog(self)
    return hpscatalog.manage_catalogClear(*args, **kwargs)


def _unindexObject(self, ob):
    # same reason as the patch above, we need the actual object passed along
    # this handle dexterity types
    path = '/'.join(ob.getPhysicalPath())
    return self.uncatalog_object(path, obj=ob)


def moveObjectsByDelta(self, ids, delta, subset_ids=None,
                       suppress_events=False):
    res = self._old_moveObjectsByDelta(ids, delta, subset_ids=subset_ids,
                                       suppress_events=suppress_events)
    escatalog = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))
    hpscatalog = WildcardHPSCatalog(api.portal.get_tool('portal_catalog'))
    if hpscatalog.enabled is True or escatalog.enabled is True:
        if subset_ids is None:
            subset_ids = self.idsInOrder()
        hook.index_positions(self.context, subset_ids)
    return res


def PloneSite_moveObjectsByDelta(self, ids, delta, subset_ids=None,
                                 suppress_events=False):
    res = self._old_moveObjectsByDelta(ids, delta, subset_ids=subset_ids,
                                       suppress_events=suppress_events)
    escatalog = ElasticSearchCatalog(api.portal.get_tool('portal_catalog'))
    hpscatalog = WildcardHPSCatalog(api.portal.get_tool('portal_catalog'))
    if hpscatalog.enabled is True or escatalog.enabled is True:
        if subset_ids is None:
            objects = list(self._objects)
            subset_ids = self.getIdsSubset(objects)
        hook.index_positions(self, subset_ids)
    return res
