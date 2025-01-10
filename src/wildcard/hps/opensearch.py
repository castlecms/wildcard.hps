# -*- coding: utf-8 -*-
import math
import os

from DateTime import DateTime
from plone import api
from plone.registry.interfaces import IRegistry
from Products.CMFCore.permissions import AccessInactivePortalContent
from Products.CMFCore.utils import _checkPermission
from Products.CMFCore.utils import _getAuthenticatedUser
from Products.ZCatalog.Lazy import LazyMap
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError, TransportError
from zope.component import ComponentLookupError
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.globalrequest import getRequest
from zope.interface import implementer
from zope.interface import alsoProvides

from wildcard.hps import hook
from wildcard.hps import logger
from wildcard.hps.brain import BrainFactory
from wildcard.hps.interfaces import IWildcardHPSCatalog
from wildcard.hps.interfaces import IWildcardHPSSettings
from wildcard.hps.interfaces import IMappingProvider
from wildcard.hps.interfaces import IQueryAssembler
from wildcard.hps.interfaces import IReindexActive
from wildcard.hps.utils import getExternalOnlyIndexes
from wildcard.hps.utils import getTruthyEnv
from wildcard.hps.utils import getIntOrNone
from wildcard.hps.utils import getFloatOrNone


CONVERTED_ATTR = '_hpsconverted'
INDEX_VERSION_ATTR = '_hpsindexversion'


class SearchResult(object):

    def __init__(self, hpscatalog, query, **query_params):
        if 'sort' in query_params:
            raise Exception('bad query param')
        if 'start' in query_params:
            raise Exception('bad query param')

        self.hpscatalog = hpscatalog
        self.bulk_size = hpscatalog.get_setting('bulk_size', 50)
        qassembler = getMultiAdapter((getRequest(), hpscatalog), IQueryAssembler)
        dquery, self.sort = qassembler.normalize(query)
        self.query = qassembler(dquery)

        # results are stored in a dictionary, keyed
        # but the start index of the bulk size for the
        # results it holds. This way we can skip around
        # for result data in a result object
        result = hpscatalog._search(self.query, sort=self.sort, **query_params)['hits']
        self.results = {
            0: result['hits']
        }
        self.count = result['total']['value']
        self.query_params = query_params

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        '''
        Lazy loading es results with negative index support.
        We store the results in buckets of what the bulk size is.
        This is so you can skip around in the indexes without needing
        to load all the data.
        Example(all zero based indexing here remember):
            (525 results with bulk size 50)
            - self[0]: 0 bucket, 0 item
            - self[10]: 0 bucket, 10 item
            - self[50]: 50 bucket: 0 item
            - self[55]: 50 bucket: 5 item
            - self[352]: 350 bucket: 2 item
            - self[-1]: 500 bucket: 24 item
            - self[-2]: 500 bucket: 23 item
            - self[-55]: 450 bucket: 19 item
        '''
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.stop)]
        else:
            if key + 1 > self.count:
                raise IndexError
            elif key < 0 and abs(key) > self.count:
                raise IndexError

            # these defaults should not be used, but are placed here to keep happy
            # linters that can't reason out the below if/else well
            start = result_key = -1
            result_index = key

            if key >= 0:
                result_key = int(key / self.bulk_size) * self.bulk_size
                start = result_key
                result_index = key % self.bulk_size
            elif key < 0:
                last_key = int(math.floor(
                    float(self.count) / float(self.bulk_size)
                )) * self.bulk_size
                start = result_key = last_key - (
                    (abs(key) / self.bulk_size) * self.bulk_size)
                if last_key == result_key:
                    result_index = key
                else:
                    result_index = (key % self.bulk_size) - (
                        self.bulk_size - (self.count % last_key)
                    )

            if result_key not in self.results:
                self.results[result_key] = self.hpscatalog._search(
                    self.query, sort=self.sort, start=start,
                    **self.query_params)['hits']['hits']

            return self.results[result_key][result_index]


@implementer(IWildcardHPSCatalog)
class WildcardHPSCatalog(object):
    '''
    from patched methods
    '''

    # Keep in mind that other packages will likely use
    # this object to get a connection object, etc -- that way they don't have to
    # know about all the settings and tidbits for connecting
    #
    # that means the init should probably be kept as side-effect free as possible
    #
    # catalogtool is, eg, the result of `api.portal.get_tool('portal_catalog')`
    # envprefix is the prefix applied to opensearch connection settings fetched from from the environment
    #   - note: you can see a comprehensive list of these in the README that use the default
    #           'OPENSEARCH_' prefix
    def __init__(self, catalogtool, envprefix='OPENSEARCH_'):
        self.envprefix = envprefix
        self.catalogtool = catalogtool
        self.catalog = catalogtool._catalog

        try:
            registry = getUtility(IRegistry)
            try:
                self.registry = registry.forInterface(
                    IWildcardHPSSettings,
                    check=False
                )
            except Exception:
                self.registry = None
        except ComponentLookupError:
            self.registry = None

        self._conn = None

    def _get_hosts(self):
        # hosts can be RFC-1738 formatted urls
        # multiple hosts can be specified by putting a space between urls
        hosts_env = os.getenv("{}HOSTS".format(self.envprefix))
        hosts = ['https://admin:admin@localhost:9200']
        if hosts_env is not None:
            hosts = [a for a in hosts_env.split(' ') if len(a.strip()) > 0]
        return hosts

    def get_connection_kwargs(self):
        kwargs = dict()

        # NODES

        # default timeout
        timeout = getIntOrNone("{}TIMEOUT".format(self.envprefix))
        if timeout is not None:
            kwargs["timeout"] = timeout

        # retry connecting to different node when request fails
        kwargs["retry_on_timeout"] = getTruthyEnv("{}RETRY_ON_TIMEOUT".format(self.envprefix))

        # SNIFFING
        if getTruthyEnv("{}DISABLE_HOST_INFO_CALLBACK".format(self.envprefix)):
            def no_host_info_callback(*args, **kwargs):
                return None

            # if the "host_info_callback" method returns None for all hosts it's given,
            # then none of the host info from /_nodes/_all/http calls will be used
            # to modify the statically defined host list given to the connection
            # initially
            #
            # if you truly don't want sniffing to happen at all during the use of
            # the OpenSearch() object, you'll want to disable this. Otherwise there's
            # several different times and ways that it'll attempt to sniff (or do the
            # equivalent), even if it doesn't sniff "on_start" or "on_connection_fail"
            kwargs["host_info_callback"] = no_host_info_callback

        # sniff for nodes before doing anything
        kwargs["sniff_on_start"] = getTruthyEnv("{}SNIFF_ON_START".format(self.envprefix))

        # refresh nodes after a node fails to respond
        kwargs["sniff_on_connection_fail"] = getTruthyEnv("{}SNIFF_ON_CONNECTION_FAIL".format(self.envprefix))

        # refresh nodes on interval
        #
        # keep in mind, if DISABLE_HOST_INFO_CALLBACK is not TRUE, and SNIFF_ON_START and
        # SNIFF_ON_CONNECTION_FAIL are both FALSE, then there are still conditions which
        # OpenSearch() will query node info for updated hosts to connect to... and one of
        # those ways might be if there is any sniffer timeout value other than None.
        kwargs["sniffer_timeout"] = getIntOrNone("{}SNIFFER_TIMEOUT".format(self.envprefix))

        # timeout of sniff request
        sniff_timeout = getFloatOrNone("{}SNIFF_TIMEOUT".format(self.envprefix))
        if sniff_timeout is not None:
            kwargs["sniff_timeout"] = sniff_timeout

        # SSL

        # turn on SSL
        kwargs["use_ssl"] = getTruthyEnv("{}USE_SSL".format(self.envprefix))

        # verify ssl certificates
        kwargs["verify_certs"] = getTruthyEnv("{}VERIFY_CERTS".format(self.envprefix))
        if not kwargs["verify_certs"]:
            # when not verifying, warning will be displayed unless disabled
            kwargs["ssl_show_warn"] = getTruthyEnv("{}SSL_SHOW_WARN".format(self.envprefix))

        # provide a path to CA certs on disk
        ca_certs_path = os.getenv("{}CA_CERTS_PATH".format(self.envprefix))
        if ca_certs_path is not None:
            kwargs["ca_certs"] = ca_certs_path

        # SSL client auth, PEM formatted SSL client certificate
        client_cert_path = os.getenv("{}CLIENT_CERT_PATH".format(self.envprefix))
        if client_cert_path is not None:
            kwargs["client_cert"] = client_cert_path

        # SSL client auth, PEM formatted SSL client key
        client_key_path = os.getenv("{}CLIENT_KEY_PATH".format(self.envprefix))
        if client_key_path is not None:
            kwargs["client_key"] = client_key_path

        # CONNECTION

        # for some reason, the connection object, while it acepts an RFC-1738 formatted
        # URL list for the hosts parameter, and parses out the http_auth information
        # just fine from each of those listed node URL's, it doesn't appear
        # to propagate the credentials to connections made to individual nodes.
        #
        # instead, it appears to expect, at least for now (2022/03/30 -- v1.1.0) that
        # there is an http_auth kwarg passed to the OpenSearch() init, and that will
        # get propagated to all calls to any node
        http_auth_user = os.getenv("{}HTTP_USERNAME".format(self.envprefix))
        http_auth_pass = os.getenv("{}HTTP_PASSWORD".format(self.envprefix))
        http_auth = ""
        if http_auth_user is not None:
            http_auth += http_auth_user
        http_auth += ":"
        if http_auth_pass is not None:
            http_auth += http_auth_pass
        if http_auth.strip() != ":":
            kwargs["http_auth"] = http_auth

        return kwargs

    @property
    def connection(self):
        if self._conn is None:
            kwargs = self.get_connection_kwargs()

            self._conn = OpenSearch(hosts=self._get_hosts(), **kwargs)
        return self._conn

    def _search(self, query, sort=None, **query_params):
        '''
        '''
        if 'start' in query_params:
            query_params['from_'] = query_params.pop('start')

        query_params['stored_fields'] = query_params.get(
            'stored_fields', 'path.path')
        query_params['size'] = self.get_setting('bulk_size', 50)

        body = {'query': query}
        if sort is not None:
            body['sort'] = sort

        return self.connection.search(index=self.index_name,
                                      body=body,
                                      **query_params)

    def search(self, query, factory=None, **query_params):
        """
        @param query: dict
            The plone query
        @param factory: function(result: dict): any
            The factory that maps each OpenSearch result.
            By default, get the plone catalog brain.
        @param query_params:
            Parameters to pass to the search method
            'stored_fields': the list of fields to get from stored source
        @return: LazyMap
        """
        result = SearchResult(self, query, **query_params)
        if not factory:
            factory = BrainFactory(self.catalog)
        return LazyMap(factory, result, result.count)

    @property
    def catalog_converted(self):
        return getattr(self.catalogtool, CONVERTED_ATTR, False)

    @property
    def enabled(self):
        force_enabled = getTruthyEnv("HPS_FORCE_ENABLE")
        if force_enabled:
            # if hps is force-enabled, then it is expected that
            # the appropriate mappings and indexes have been
            # created already... we'll output a warning here to
            # remind
            logger.warn(
                "HPS_FORCE_ENABLE active... please make sure your indexes "
                "and mappings have already been created!")

        return (
            force_enabled
            or (
                self.registry
                and self.registry.enabled
                and self.catalog_converted))

    def get_setting(self, name, default=None):
        return getattr(self.registry, name, default)

    def catalog_object(self, obj, uid=None, idxs=[], update_metadata=1,
                       pghandler=None):
        if idxs != ['getObjPositionInParent']:
            self.catalogtool._old_catalog_object(
                obj, uid, idxs, update_metadata, pghandler)

        if not self.enabled:
            return
        hook.add_object(self, obj)

    def uncatalog_object(self, uid, obj=None, *args, **kwargs):
        # always need to uncatalog to remove brains, etc
        if obj is None:
            # with archetypes, the obj is not passed, only the uid is
            try:
                obj = api.content.get(uid)
            except KeyError:
                pass

        result = self.catalogtool._old_uncatalog_object(uid, *args, **kwargs)
        if self.enabled:
            hook.remove_object(self, obj)

        return result

    def manage_catalogRebuild(self, *args, **kwargs):
        if self.registry.enabled:
            self.recreateCatalog()

        alsoProvides(getRequest(), IReindexActive)
        return self.catalogtool._old_manage_catalogRebuild(*args, **kwargs)

    def manage_catalogClear(self, *args, **kwargs):
        if self.enabled:
            self.recreateCatalog()

        return self.catalogtool._old_manage_catalogClear(*args, **kwargs)

    def recreateCatalog(self):
        conn = self.connection

        try:
            conn.indices.delete(index=self.real_index_name)
        except NotFoundError:
            pass
        except TransportError as exc:
            if exc.error != 'illegal_argument_exception':
                raise
            conn.indices.delete_alias(index="_all", name=self.real_index_name)

        if self.index_version:
            try:
                conn.indices.delete_alias(
                    self.index_name,
                    self.real_index_name)
            except NotFoundError:
                pass
        self.convertToOpenSearch()

    @property
    def include_trashed_by_default(self):
        return getTruthyEnv("HPS_INCLUDE_TRASHED_BY_DEFAULT")

    def searchResults(self, REQUEST=None, check_perms=False, **kw):
        enabled = False
        if self.enabled:
            # need to also check if it is a search result we care about
            # using opensearch for
            if getExternalOnlyIndexes().intersection(kw.keys()):
                enabled = True
        if not enabled:
            if check_perms:
                return self.catalogtool._old_searchResults(REQUEST, **kw)
            else:
                return self.catalogtool._old_unrestrictedSearchResults(
                    REQUEST,
                    **kw)

        if isinstance(REQUEST, dict):
            query = REQUEST.copy()
        else:
            query = {}

        # IF 'trashed' should NOT be included by default AND the caller hasn't explicitly
        # told us a value for how to query 'trashed', THEN explicitly exclude 'trashed'
        # entries
        if not self.include_trashed_by_default and 'trashed' not in kw:
            kw['trashed'] = False

        query.update(kw)

        if check_perms:
            show_inactive = query.get('show_inactive', False)
            if isinstance(REQUEST, dict) and not show_inactive:
                show_inactive = 'show_inactive' in REQUEST

            user = _getAuthenticatedUser(self.catalogtool)
            query['allowedRolesAndUsers'] = \
                self.catalogtool._listAllowedRolesAndUsers(user)

            if not show_inactive and not _checkPermission(
                    AccessInactivePortalContent, self.catalogtool):
                query['effectiveRange'] = DateTime()
        orig_query = query.copy()
        logger.debug('Running query: %s' % repr(orig_query))
        try:
            results = self.search(query)
            return results
        except Exception:
            logger.error(
                'Error running Query: {0!r}'.format(orig_query), exc_info=True)
            return self.catalogtool._old_searchResults(REQUEST, **kw)

    def convertToOpenSearch(self):
        setattr(self.catalogtool, CONVERTED_ATTR, True)
        self.catalogtool._p_changed = True
        adapter = getMultiAdapter((getRequest(), self), IMappingProvider)
        mapping = adapter()
        self.connection.indices.put_mapping(
            body=mapping,
            index=self.index_name)

    @property
    def instance_prefix(self):
        return os.getenv("HPS_INSTANCE_INDEX_PREFIX")

    @property
    def index_name(self):
        iprefix = self.instance_prefix
        if iprefix is not None:
            iprefix += "-"
        else:
            iprefix = ""
        site_path = '-'.join(self.catalogtool.getPhysicalPath()[1:]).lower()
        return "{prefix}{site}".format(
            prefix=iprefix,
            site=site_path)

    @property
    def index_version(self):
        return getattr(self.catalogtool, INDEX_VERSION_ATTR, None)

    def bump_index_version(self):
        version = getattr(self.catalogtool, INDEX_VERSION_ATTR, None)
        if version is None:
            version = 1
        else:
            version += 1
        setattr(self.catalogtool, INDEX_VERSION_ATTR, version)
        self.catalogtool._p_changed = True
        return version

    @property
    def real_index_name(self):
        if self.index_version:
            return '%s_%i' % (self.index_name, self.index_version)
        return self.index_name
