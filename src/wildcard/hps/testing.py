# -*- coding: utf-8 -*-
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.testing import z2
from Products.CMFCore.utils import getToolByName
from zope.configuration import xmlconfig


try:
    import Products.ATContentTypes
    HAS_ATCONTENTTYPES = True
except ImportError:
    HAS_ATCONTENTTYPES = False


class WildcardHPS(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        super(WildcardHPS, self).setUpZope(app, configurationContext)
        # load ZCML

        import plone.app.contenttypes
        xmlconfig.file('configure.zcml', plone.app.contenttypes,
                       context=configurationContext)
        z2.installProduct(app, 'plone.app.contenttypes')

        import plone.app.event.dx
        self.loadZCML(package=plone.app.event.dx,
                      context=configurationContext)

        import plone.app.registry
        xmlconfig.file('configure.zcml', plone.app.registry,
                       context=configurationContext)
        z2.installProduct(app, 'plone.app.registry')

        import wildcard.hps
        xmlconfig.file('configure.zcml', wildcard.hps,
                       context=configurationContext)
        z2.installProduct(app, 'Products.DateRecurringIndex')
        z2.installProduct(app, 'wildcard.hps')

    def setUpPloneSite(self, portal):
        super(WildcardHPS, self).setUpPloneSite(portal)
        # install into the Plone site
        applyProfile(portal, 'plone.app.registry:default')
        applyProfile(portal, 'plone.app.contenttypes:default')
        applyProfile(portal, 'wildcard.hps:default')
        setRoles(portal, TEST_USER_ID, ('Member', 'Manager'))
        workflowTool = getToolByName(portal, 'portal_workflow')
        workflowTool.setDefaultChain('plone_workflow')

    def tearDownPloneSite(self, portal):
        super(WildcardHPS, self).tearDownPloneSite(portal)
        applyProfile(portal, 'plone.app.contenttypes:uninstall')


WildcardHPS_FIXTURE = WildcardHPS()
WildcardHPS_INTEGRATION_TESTING = IntegrationTesting(
    bases=(WildcardHPS_FIXTURE,), name='WildcardHPS:Integration')
WildcardHPS_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(WildcardHPS_FIXTURE,), name='WildcardHPS:Functional')


if HAS_ATCONTENTTYPES:
    class WildcardHPSAT(PloneSandboxLayer):
        defaultBases = (PLONE_FIXTURE, )

        def setUpZope(self, app, configurationContext):
            super(WildcardHPSAT, self).setUpZope(app, configurationContext)
            # load ZCML

            xmlconfig.file('configure.zcml', Products.ATContentTypes,
                           context=configurationContext)
            z2.installProduct(app, 'Products.ATContentTypes')

            import plone.app.registry
            xmlconfig.file('configure.zcml', plone.app.registry,
                           context=configurationContext)
            z2.installProduct(app, 'plone.app.registry')

            import wildcard.hps
            xmlconfig.file('configure.zcml', wildcard.hps,
                           context=configurationContext)
            z2.installProduct(app, 'Products.DateRecurringIndex')
            z2.installProduct(app, 'wildcard.hps')

        def setUpPloneSite(self, portal):
            super(WildcardHPSAT, self).setUpPloneSite(portal)
            # install into the Plone site
            applyProfile(portal, 'plone.app.registry:default')
            applyProfile(portal, 'Products.ATContentTypes:default')
            applyProfile(portal, 'wildcard.hps:default')
            setRoles(portal, TEST_USER_ID, ('Member', 'Manager'))
            workflowTool = getToolByName(portal, 'portal_workflow')
            workflowTool.setDefaultChain('plone_workflow')

    WildcardHPS_FIXTURE_AT = WildcardHPSAT()
    WildcardHPS_FUNCTIONAL_TESTING_AT = FunctionalTesting(
        bases=(WildcardHPS_FIXTURE_AT,), name='WildcardHPS:FunctionalAT')


def browserLogin(portal, browser, username=None, password=None):
    handleErrors = browser.handleErrors
    try:
        browser.handleErrors = False
        browser.open(portal.absolute_url() + '/login_form')
        if username is None:
            username = TEST_USER_NAME
        if password is None:
            password = TEST_USER_PASSWORD
        browser.getControl(name='__ac_name').value = username
        browser.getControl(name='__ac_password').value = password
        browser.getControl(name='submit').click()
    finally:
        browser.handleErrors = handleErrors


def createObject(context, _type, id, delete_first=True,
                 check_for_first=False, **kwargs):
    if delete_first and id in context:
        context.manage_delObjects([id])
    if not check_for_first or id not in context:
        return context[context.invokeFactory(_type, id, **kwargs)]

    return context[id]
