# -*- coding: utf-8 -*-
import os

from wildcard.hps.interfaces import IWildcardHPSSettings
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.component.interfaces import ComponentLookupError


try:
    from plone.uuid.interfaces import IUUID
except ImportError:
    def IUUID(obj, default=None):
        return default


def getUID(obj):
    value = IUUID(obj, None)
    if not value and hasattr(obj, 'UID'):
        value = obj.UID()
    return value


def getExternalOnlyIndexes():
    override_values = os.getenv('HPS_FORCE_EXTERNAL_INDEXES', None)
    if override_values is not None:
        return set([a.strip() for a in override_values.split(",")])

    try:
        # default to Title, Description, and SearchableText
        return getUtility(IRegistry).forInterface(
            IWildcardHPSSettings,
            check=False
        ).external_only_indexes or {'Title', 'Description', 'SearchableText'}
    # a ComponentLookupError would probably indicate that the wildcard.hps addon hasn't
    # been installed in the site, but maybe that HPS_FORCE_ENABLED is set to Yes/On/True
    # which would mean that the registry wouldn't have any settings associated with the
    # IWildcardHPSSettings... I think the most reasonable option in this state is to just
    # use the default set
    except (KeyError, AttributeError, ComponentLookupError):
        return {'Title', 'Description', 'SearchableText'}


def getTruthyEnv(key):
    if key is None:
        return False
    var = os.getenv(key)
    return var is not None and var.lower().strip() in ('yes', 'true', '1', 'on')


def getIntOrNone(key):
    var = os.getenv(key)
    if var is None:
        return None

    try:
        return int(var)
    except ValueError:
        pass

    return None


def getFloatOrNone(key):
    var = os.getenv(key)
    if var is None:
        return None

    try:
        return float(var)
    except ValueError:
        pass

    return None
