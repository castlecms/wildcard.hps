wildcard.hps
============

CastleCMS and Plone integration with [OpenSearch](https://opensearch.org)

This product was forked from [collective.elasticsearch](https://github.com/collective/collective.elasticsearch)
in order to provide integration with OpenSearch instead of ElasticSearch. OpenSearch itself is
a fork of ElasticSearch and compatible with, at least, the ES 7.10.x series of releases (at least
at opensearch-py 1.1.0). Compatibility may diverge in the future, and while the collective.elasticsearch
package will likely try to maintain compatibility with ElasticSearch, wildcard.hps is intended
to maintain compatibility with OpenSearch.

## Quickstart

First, start up an instance (for official guides, see the [opensearch project documentation](https://opensearch.org/docs/latest/opensearch/install/index/))

```
$ docker run -p 9200:9200 -p 9600:9600 -e "discovery.type=single-node" opensearchproject/opensearch:latest
$ curl -XGET https://localhost:9200 -u 'admin:admin' -k
```

Second, setup Plone/CastleCMS:

1. add `wildcard.hps` to the `eggs` section of your buildout
3. run buildout
4. restart your instance, using relevant Environment Variables to connect to your opensearch instance
5. install the 'Wildcard HPS' product
6. under the 'Wildcard HPS' control panel, click 'Convert Catalog' then 'Rebuild Catalog'

Configuration Settings are passed as environment variables. See the "Configuration" section
below for more details.


## Overview

This package aims to index all fields the `portal_catalog` indexes
and allows you to delete the `Title`, `Description` and `SearchableText`
indexes which can provide significant improvement to performance and RAM usage.

OpenSearch queries are ONLY used when Title, Description and SearchableText
text are in the query. Otherwise, Plone's default catalog will be used.
This is because Plone's default catalog is faster on normal queries than using
OpenSearch.


## Configuration

Configuration for OpenSearch connections, and custom index naming, is done through
Environment Variables. This allows per-instance customization without the need to
modify site data, and allows for many deployments to use the same cluster(s) without
_needing_ to do per-site customized index names.

Available Environrment Variable Options:

  * `HPS_ZOPE_CONF_PATH`
    * path to a zope.conf to get a Zope app instance
    * NOTE: this is only needed for the `reindex_hps` script that gets installed.
      See `wildcard/hps/scripts/reindex.py`.
  * `HPS_OVERRIDE_LOGGING`
    * if present, will tell the `reindex_hps` script to override the root logging
      configuration, and print logging to console at INFO level.
  * `HPS_FORCE_ENABLE`
    * default: no
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * will force the "enabled" lookup to be True
  * `HPS_INSTANCE_INDEX_PREFIX`
    * default: None
    * a string value prepended to index names used by the Plone instances this addon is installed into
  * `HPS_INCLUDE_TRASHED_BY_DEFAULT`
    * default: no
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * will default searchResults to include trashed entries (which are not included by default)
  * `HPS_FOCE_EXTERNAL_INDEXES`
    * default: None
    * a list of object properties that will be included in the externally index object (IE
      the indexed object in opensearch)
  * `OPENSEARCH_HOSTS`
    * default: https://admin:admin@localhost:9200
    * a list of RFC-1738 formated urls. multiple urls can be specified by putting a space between urls.
    * NOTE: for now, the opensearch-py (1.1.0) does not respect the HTTP auth info that is formatted
      as part of the URL, instead use `OPENSEARCH_HTTP_USERNAME` and `OPENSEARCH_HTTP_PASSWORD` to pass
      the same HTTP auth to each request to any node listed as a host.
  * `OPENSEARCH_HTTP_USERNAME`
    * default: None
    * a username to use in all connections to any node in the `OPENSEARCH_HOSTS` list
  * `OPENSEARCH_HTTP_PASSWORD`
    * default: None
    * a password to use in all connections to any node in the `OPENSEARCH_HOSTS` list
  * `OPENSEARCH_TIMEOUT`
    * default connection timeout
  * `OPENSEARCH_RETRY_ON_TIMEOUT`
    * default: Off
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * retry connection to different node when connection fails
  * `OPENSEARCH_DISABLE_HOST_INFO_CALLBACK`
    * default: False
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * if enabled, will effectivly disable all sniffing and force the use of the specific
      hosts given by `OPENSEARCH_HOSTS`
  * `OPENSEARCH_SNIFF_ON_START`
    * default: False
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * refresh nodes before doing anything
  * `OPENSEARCH_SNIFF_ON_CONNECTION_FAIL`
    * default: False
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * refresh nodes after a node fails to respond
  * `OPENSEARCH_SNIFFER_TIMEOUT`
    * default: None
    * refresh node list on this time (in seconds) interval -- note, you may want to
      not include this value if you want to completely disable sniffing
  * `OPENSEARCH_SNIFF_TIMEOUT`
    * default: 0.1
    * timeout of sniff request
  * `OPENSEARCH_USE_SSL`
    * default: False
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * connections to OpenSearch will use SSL
  * `OPENSEARCH_VERIFY_CERTS`
    * default: True
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * verify SSL certificates when using SSL connections to OpenSearch
  * `OPENSEARCH_SSL_SHOW_WARN`
    * default: True
    * accepted values (all other values are equivalent to False): Yes, True, 1, On
    * when verifying SSL certificates is disabled, then a warning will be shown by default
  * `OPENSEARCH_CERTS_PATH`
    * default: None
    * a path to a directory containing CA Certificates used in SSL verification
  * `OPENSEARCH_CLIENT_CERT_PATH`
    * default: None
    * a path to a PEM formated SSL client certificate for SSL client auth
  * `OPENSEARCH_CLIENT_CERT_KEY` -- 
    * default: None
    * a path to a PEM formated SSL client key for SSL client auth


## Compatibility

Only tested with Plone 5 with Dexterity types.

Only compatible with versions of OpenSearch (and ElasticSearch) compatible
with the `opensearch-py` library.

For ElasticSearch integration, see [collective.elasticsearch](https://github.com/collective/collective.elasticsearch).


## State

Support for all index column types is done EXCEPT for the DateRecurringIndex
index column type. If you are doing a full text search along with a query that
contains a DateRecurringIndex column, it will not work.


## Celery support

This package comes with Celery support where all indexing operations will be pushed
into celery to be run asynchronously.

Please see instructions for collective.celery to see how this works.


## Running tests

First, start an instance of OpenSearch.

Second,

```
$ virtualenv ./env
$ ./env/bin/pip install -r requirements.txt
$ ./env/bin/buildout -c buildout.cfg
$ ./bin/test
```
