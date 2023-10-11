# -*- coding: utf-8 -*-
from wildcard.hps.indexes import getIndex
from wildcard.hps.interfaces import IAdditionalIndexDataProvider
from wildcard.hps.utils import getExternalOnlyIndexes
from wildcard.hps.utils import getUID
from plone import api
from plone.app.uuid.utils import uuidToObject
from plone.indexer.interfaces import IIndexableObject
from plone.indexer.interfaces import IIndexer
from plone.uuid.interfaces import IUUID
from Products.CMFCore.interfaces import ISiteRoot
from zope.component import getAdapters
from zope.component import queryMultiAdapter
from zope.component.hooks import getSite
from zope.component.hooks import setSite

import logging
import random
import six
import time
import traceback
import transaction
import urllib3


logger = logging.getLogger('wildcard.hps')


def index_batch(remove, index, positions, hpscatalog=None):  # noqa: C901
    if hpscatalog is None:
        from wildcard.hps.opensearch import WildcardHPSCatalog
        hpscatalog = WildcardHPSCatalog(api.portal.get_tool('portal_catalog'))

    setSite(api.portal.get())
    conn = hpscatalog.connection
    bulk_size = hpscatalog.get_setting('bulk_size', 50)

    if len(remove) > 0:
        bulk_data = []
        for uid in remove:
            bulk_data.append({
                'delete': {
                    '_index': hpscatalog.index_name,
                    '_id': uid
                }
            })
        result = hpscatalog.connection.bulk(
            index=hpscatalog.index_name,
            body=bulk_data)

        if "errors" in result and result["errors"] is True:
            logger.error("Error in bulk indexing removal: %s" % result)

    if len(index) > 0:
        if type(index) in (list, tuple, set):
            # does not contain objects, must be async, convert to dict
            index = dict([(k, None) for k in index])
        bulk_data = []

        for uid, obj in index.items():
            # If content has been moved (ie by a contentrule) then the object
            # passed here is the original object, not the moved one.
            # So if there is a uuid, we use this to get the correct object.
            # See https://github.com/collective/wildcard.hps/issues/65 # noqa
            if uid is not None:
                obj = uuidToObject(uid)

            if obj is None:
                obj = uuidToObject(uid)
                if obj is None:
                    continue
            bulk_data.extend([{
                'index': {
                    '_index': hpscatalog.index_name,
                    '_id': uid
                }
            }, get_index_data(obj, hpscatalog)])
            if len(bulk_data) % bulk_size == 0:
                result = conn.bulk(
                    index=hpscatalog.index_name,
                    body=bulk_data)

                if "errors" in result and result["errors"] is True:
                    logger.error("Error in bulk indexing: %s" % result)

                bulk_data = []

        if len(bulk_data) > 0:
            result = conn.bulk(
                index=hpscatalog.index_name,
                body=bulk_data)

            if "errors" in result and result["errors"] is True:
                logger.error("Error in bulk indexing: %s" % result)

    if len(positions) > 0:
        bulk_data = []
        index = getIndex(hpscatalog.catalogtool._catalog, 'getObjPositionInParent')
        for uid, ids in positions.items():
            if uid == '/':
                parent = getSite()
            else:
                parent = uuidToObject(uid)
            if parent is None:
                logger.warn('could not find object to index positions')
                continue
            for _id in ids:
                ob = parent[_id]
                wrapped_object = get_wrapped_object(ob, hpscatalog)
                try:
                    value = index.get_value(wrapped_object)
                except Exception:
                    continue
                bulk_data.extend([{
                    'update': {
                        '_index': hpscatalog.index_name,
                        '_id': IUUID(ob)
                    }
                }, {
                    'doc': {
                        'getObjPositionInParent': value
                    }
                }])
                if len(bulk_data) % bulk_size == 0:
                    conn.bulk(
                        index=hpscatalog.index_name,
                        body=bulk_data)
                    bulk_data = []

        if len(bulk_data) > 0:
            conn.bulk(
                index=hpscatalog.index_name,
                body=bulk_data)


def get_wrapped_object(obj, hpscatalog):
    wrapped_object = None
    if not IIndexableObject.providedBy(obj):
        # This is the CMF 2.2 compatible approach, which should be used
        # going forward
        wrapper = queryMultiAdapter((obj, hpscatalog.catalogtool),
                                    IIndexableObject)
        if wrapper is not None:
            wrapped_object = wrapper
        else:
            wrapped_object = obj
    else:
        wrapped_object = obj
    return wrapped_object


# Ignore errors in converting to unicode, so json.dumps
# does not barf when we're trying to send data to opensearch.
def fix_unicode_for_opensearch(value):
    val = value

    if not six.PY2 and isinstance(val, bytes):
        val = val.decode('utf-8', 'ignore')
    elif six.PY2 and isinstance(val, str):
        val = six.text_type(val, 'utf-8', 'ignore')
    elif six.PY2 and isinstance(val, unicode):
        # we're already getting a unicode string, but maybe it's not good utf-8
        # so encode it as a string, then use six to convert it back
        # to an appropriate unicode string, and in the process ignore characters
        # that would otherwise be a problem
        val = six.text_type(val.encode('utf-8', 'ignore'), 'utf-8', 'ignore')
    elif isinstance(val, tuple):
        vallist = []
        for v in val:
            vallist.append(fix_unicode_for_opensearch(v))
        val = tuple(vallist)
    elif isinstance(val, list):
        vallist = []
        for v in val:
            vallist.append(fix_unicode_for_opensearch(v))
        val = vallist
    elif isinstance(val, dict):
        valdict = {}
        for (key, v) in val.items():
            valdict[key] = fix_unicode_for_opensearch(v)
        val = valdict

    return val


def get_index_data(obj, hpscatalog):  # noqa: C901
    catalog = hpscatalog.catalogtool._catalog

    wrapped_object = get_wrapped_object(obj, hpscatalog)
    index_data = {}
    for index_name in catalog.indexes.keys():
        index = getIndex(catalog, index_name)
        if index is not None:
            try:
                value = index.get_value(wrapped_object)
            except Exception:
                logger.error('Error indexing value: %s: %s\n%s' % (
                    '/'.join(obj.getPhysicalPath()),
                    index_name,
                    traceback.format_exc()))
                value = None
            if value in (None, 'None'):
                # yes, we'll index null data...
                value = None

            value = fix_unicode_for_opensearch(value)

            index_data[index_name] = value

    # in case these indexes are deleted
    # (to increase performance and improve ram usage)
    for name in getExternalOnlyIndexes():
        if name in index_data:
            continue
        indexer = queryMultiAdapter((obj, hpscatalog.catalogtool), IIndexer, name=name)
        if indexer is not None:
            try:
                val = fix_unicode_for_opensearch(indexer())
                index_data[name] = val
            except Exception:
                logger.error('Error indexing value: %s: %s\n%s' % (
                    '/'.join(obj.getPhysicalPath()),
                    name,
                    traceback.format_exc()))
        else:
            val = getattr(obj, name, None)
            if callable(val):
                val = val()
            val = fix_unicode_for_opensearch(val)
            index_data[name] = val

    for _, adapter in getAdapters((obj,), IAdditionalIndexDataProvider):
        fixeddata = {}
        for key, val in adapter(hpscatalog, index_data).items():
            fixeddata[key] = fix_unicode_for_opensearch(val)
        index_data.update(fixeddata)

    return index_data


try:
    from collective.celery import task

    @task.as_admin()
    def index_batch_async(remove, index, positions):
        retries = 0
        while True:
            # if doing batch updates, this can give ES problems
            if retries < 4:
                try:
                    index_batch(remove, index, positions)
                    break
                except urllib3.exceptions.ReadTimeoutError:
                    retries += 1
                    if retries >= 4:
                        raise
                    time.sleep(random.choice([0.5, 0.75, 1, 1.25, 1.5]))

    CELERY_INSTALLED = True
except ImportError:
    CELERY_INSTALLED = False


class CommitHook(object):

    def __init__(self, hpscatalog):
        self.remove = set()
        self.index = {}
        self.positions = {}
        self.hpscatalog = hpscatalog

    def schedule_celery(self):
        index_batch_async.apply_async(
            args=[self.remove, self.index.keys(), self.positions],
            kwargs={},
            without_transaction=True)

    def __call__(self, trns):
        if not trns:
            return

        if CELERY_INSTALLED:
            self.schedule_celery()
        else:
            index_batch(self.remove, self.index, self.positions, self.hpscatalog)

        self.index = {}
        self.remove = []
        self.positions = {}


def getHook(hpscatalog=None):
    if hpscatalog is None:
        from wildcard.hps.opensearch import WildcardHPSCatalog
        hpscatalog = WildcardHPSCatalog(api.portal.get_tool('portal_catalog'))
    if not hpscatalog.enabled:
        return

    trns = transaction.get()
    hook = None
    for _hook in trns._after_commit:
        if isinstance(_hook[0], CommitHook):
            hook = _hook[0]
            break
    if hook is None:
        hook = CommitHook(hpscatalog)
        trns.addAfterCommitHook(hook)
    return hook


def remove_object(hpscatalog, obj):
    hook = getHook(hpscatalog)
    uid = getUID(obj)
    if uid is None:
        logger.error("Tried to unindex an object of None uid")
        return

    hook.remove.add(uid)
    if uid in hook.index:
        del hook.index[uid]


def add_object(hpscatalog, obj):
    hook = getHook(hpscatalog)
    uid = getUID(obj)
    if uid is None:
        logger.error("Tried to index an object of None uid")
        return

    hook.index[uid] = obj
    if uid in hook.remove:
        hook.remove.remove(uid)


def index_positions(obj, ids):
    hook = getHook()
    if ISiteRoot.providedBy(obj):
        hook.positions['/'] = ids
    else:
        uid = getUID(obj)
        if uid is None:
            logger.error("Tried to index an object of None uid")
            return
        hook.positions[getUID(obj)] = ids
