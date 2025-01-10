Changelog
=========

1.4.5 (2025-01-10)
------------------

- add explicit env var for disabling collection of host info for nodes during opensearch sniffing
- explicitly set the sniffer_timeout, sniff_on_start, and sniff_on_connection_fail parameters
- move fetching connection kwargs to it's own method


1.4.4 (2023-10-11)
------------------

- missing '.items()'


1.4.3 (2023-10-11)
------------------

- handle unicode for index data derived from IAdditionalIndexDataProvider adapters


1.4.2 (2023-05-15)
------------------

- abstract unicode handling code for hook when getting index data, and handle
  tuples, lists, and dict values


1.4.1 (2023-05-11)
------------------

- handle unicode error and fix bug in hook when getting index data


1.4.0 (2022-11-04)
------------------

- allow a custom prefix to be defined for fetching connection settings from the
  environment (default to the previous hard-coded 'OPENSEARCH_' value)


1.3.0 (2022-08-17)
------------------

- add HPS_FORCE_EXTERNAL_INDEXES
- update default set returned when external indexes setting is not configured yet


1.2.1 (2022-06-23)
------------------

- fix some view name's in the control panel templates


1.2.0 (2022-05-25)
------------------

- add HPS_INCLUDE_TRASHED_BY_DEFAULT env for disabling a filter on searchResults
  from WildcardHPSCatalog (see readme entry for HPS_INCLUDE_TRASHED_BY_DEFAULT)


1.1.1 (2022-05-12)
------------------

- add property on wildcard.hps.opensearch.WildcardHPSCatalog for the instance prefix


1.1.0 (2022-05-12)
------------------

- initial fork from: https://github.com/collective/collective.elasticsearch/commit/d21bf7b9311a9fc923283eeff11c42f4145180b4
  this fork aims to primarily maintain compatibility with the OpenSearch project, which
  itself has forked from ElasticSearch 7.10.
