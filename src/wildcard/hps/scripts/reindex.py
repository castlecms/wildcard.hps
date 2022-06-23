"""
The point of this script is to reindex the whole catalog.

Normally, when done through the 'manage_rebuildCatalog' process of, say
the Products.CMFPlone.CatalogTool.CatalogTool, rebulding will mean
dropping the index and walking each object.

With large sites, this is problematic because it can take a long time and
can leave a partial or bad index presenting to users while things are
being reindexed.

This script aims to provide an alternative method such that objects
are walked over, reindexed, and then objects that were not seen will be
removed from the index.

This still takes a long time, but tries to keep as much of the index
available as possible while the process is running.

"""

import datetime
import logging
import os
import sys
import tempfile
if sys.platform != "win32":
    import fcntl

from AccessControl.SecurityManagement import newSecurityManager
from plone import api
from plone.uuid.interfaces import IUUID
from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot
from zope.app.publication.interfaces import BeforeTraverseEvent
from zope.component import getMultiAdapter
from zope.component.hooks import setSite
from zope.event import notify
from zope.globalrequest import getRequest, setRequest
from zope.interface import alsoProvides
import transaction

from wildcard.hps import logger
from wildcard.hps.interfaces import (
    IMappingProvider,
    IReindexActive,
)
from wildcard.hps.hook import index_batch
from wildcard.hps.opensearch import WildcardHPSCatalog


if os.getenv("HPS_OVERRIDE_LOGGING") is not None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


# based on the tendo implementation -- reimplemented here
# so another dep doesn't needed to be added that adds a bunch of
# other stuff not needed
class SingleInstance(object):
    def __init__(self):
        self.initialized = False
        self.lockfile = os.path.normpath(tempfile.gettempdir() + "/wildcard.hps.lock")
        if sys.platform == 'win32':
            try:
                if os.path.exists(self.lockfile):
                    os.unlink(self.lockfile)
                self.fd = os.open(self.lockfile, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except OSError:
                type, e, tb = sys.exc_info()
                if e.errno == 13:
                    logger.error("instance already running, quiting")
                    sys.exit(1)
                raise
        else:
            self.fp = open(self.lockfile, 'w')
            self.fp.flush()
            try:
                fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                logger.error("instance already running, quitting")
                sys.exit(1)
        self.initialized = True

    def __del__(self):
        if not self.initialized:
            return
        try:
            if sys.platform == 'win32':
                if hasattr(self, 'fd'):
                    os.close(self.fd)
                    os.unlink(self.lockfile)
            else:
                fcntl.lockf(self.fp, fcntl.LOCK_UN)
                if os.path.isfile(self.lockfile):
                    os.unlink(self.lockfile)
        except Exception:
            logger.warning("something happened when cleaning up", exc_info=True)
            sys.exit(-1)


def setup_site(site):
    setSite(site)
    site.clearCurrentSkin()
    site.setupCurrentSkin(site.REQUEST)
    notify(BeforeTraverseEvent(site, site.REQUEST))
    setRequest(site.REQUEST)


def index_site(site):
    setup_site(site)
    catalog = api.portal.get_tool('portal_catalog')
    hpscatalog = WildcardHPSCatalog(catalog)
    if not hpscatalog.enabled:
        logger.info("HPS Catalog is not enabled, skipping {}".format(site.getPhysicalPath()))
        return

    req = getRequest()
    if req is None:
        logger.critical("could not get fake request")
        sys.exit(1)
    alsoProvides(req, IReindexActive)

    # make sure index exists -- we do this directly, without using
    # hpscatalog.convertToOpenSearch() so that the catalogtool (and db)
    # doesn't need an update
    if not hpscatalog.connection.indices.exists(index=hpscatalog.index_name):
        logger.info("creating index {}".format(hpscatalog.index_name))
        adapter = getMultiAdapter((getRequest(), hpscatalog), IMappingProvider)
        mapping = adapter()
        hpscatalog.connection.indices.put_mapping(
            body=mapping,
            index=hpscatalog.index_name)

    # first we want to get all document ids from opensearch -- using a scroll in order to
    # get all index values
    indexed_uids = []
    query = {
        "query": {
            "match_all": {}
        }
    }
    logger.info("getting UID's from hps index...")
    result = hpscatalog.connection.search(
        index=hpscatalog.index_name,
        scroll='2s',
        size=10000,  # maximum result size possible
        body=query,
        # don't want any fields returned, since we just want the ID, which maps to a uid
        _source=[]
    )
    totaluids = len(result['hits']['hits'])
    logger.info("extracting ({}, total {}) existing UID's from response...".format(totaluids, totaluids))
    indexed_uids.extend([r['_id'] for r in result['hits']['hits']])
    scroll_id = result['_scroll_id']
    while scroll_id:
        result = hpscatalog.connection.scroll(
            scroll_id=scroll_id,
            scroll='2s',
        )
        numresults = len(result['hits']['hits'])
        if numresults == 0:
            break
        totaluids += numresults
        logger.info("extracting ({}, total {}) existing UID's from response...".format(numresults, totaluids))
        indexed_uids.extend([r['_id'] for r in result['hits']['hits']])
        scroll_id = result['_scroll_id']

    logger.info("extracted {} uids".format(totaluids))

    logger.info("scanning catalog...")
    index = {}
    count = 0
    for brain in catalog():
        count += 1
        try:
            ob = brain.getObject()
        except Exception:
            logger.info('Could not get object of {}'.format(brain.getPath()))
            continue
        try:
            uid = IUUID(ob)
            index[uid] = ob
        except TypeError:
            logger.info('Could not get UID of {}'.format(brain.getPath()))
            continue
        if uid in indexed_uids:
            # remove from uids... When all said and done,
            # we'll make sure the uids left are in fact no longer on the
            # system and remove them from es
            indexed_uids.remove(uid)
        if len(index) > 300:
            logger.info('finished indexing {}'.format(count))
            index_batch([], index, [], hpscatalog)
            site._p_jar.invalidateCache()
            transaction.begin()
            site._p_jar.sync()
            index = {}
    index_batch([], index, [], hpscatalog)
    logger.info('finished indexing {}'.format(count))

    logger.info("removing missing UID's from HPS index...")
    remove = []
    for uid in indexed_uids:
        brains = catalog(UID=uid)
        if len(brains) == 0:
            remove.append(uid)
    index_batch(remove, {}, [], hpscatalog)
    logger.info("{} records removed".format(len(remove)))


def run(app):
    SingleInstance()

    user = app.acl_users.getUser('admin')
    newSecurityManager(None, user.__of__(app.acl_users))

    starttime = datetime.datetime.now()

    for oid in app.objectIds():
        obj = app[oid]

        if IPloneSiteRoot.providedBy(obj):
            index_site(obj)

    endtime = datetime.datetime.now()
    deltat = endtime - starttime
    logger.info("done. took {}s".format(deltat.total_seconds()))


def setup_and_run():
    conf_path = os.getenv("HPS_ZOPE_CONF_PATH")
    if conf_path is None or not os.path.exists(conf_path):
        raise Exception('Could not find zope.conf at {}'.format(conf_path))

    from Zope2 import configure
    configure(conf_path)
    import Zope2
    app = Zope2.app()
    from Testing.ZopeTestCase.utils import makerequest
    app = makerequest(app)
    app.REQUEST['PARENTS'] = [app]
    from zope.globalrequest import setRequest
    setRequest(app.REQUEST)
    from AccessControl.SpecialUsers import system as user
    from AccessControl.SecurityManagement import newSecurityManager
    newSecurityManager(None, user)

    run(app)


if __name__ == '__main__':
    setup_and_run()
