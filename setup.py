# -*- coding: utf-8 -*-
"""Installer for the wildcard.hps package."""

from setuptools import find_packages
from setuptools import setup


long_description = '\n\n'.join([
    open('README.md').read(),
    open('CHANGES.md').read(),
])


setup(
    name='wildcard.hps',
    version='1.4.5',
    description="opensearch integration with CastleCMS and Plone",
    long_description=long_description,
    long_description_content_type='text/markdown',
    # Get more from https://pypi.org/classifiers/
    classifiers=[
        "Environment :: Web Environment",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Plone",
        "Framework :: Plone :: Addon",
        'Framework :: Plone :: 5.0',
        "Framework :: Plone :: 5.1",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.7",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords='castlecms plone opensearch search indexing',
    author='Wildcard Corp.',
    author_email='corporate@wildcardcorp.com',
    url='https://github.com/castlecms/wildcard.hps',
    project_urls={
        'PyPI': 'https://pypi.python.org/pypi/wildcard.hps',
        'Source': 'https://github.com/castlecms/wildcard.hps',
        'Tracker': 'https://github.com/castlecms/wildcard.hps/issues',
    },
    license='GPL version 2',
    packages=find_packages('src', exclude=['ez_setup']),
    namespace_packages=['wildcard'],
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    python_requires=">2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*, !=3.6.*",
    install_requires=[
        'setuptools',
        'opensearch-py',
        'plone.app.registry',
        'plone.api',
        'setuptools',
    ],
    extras_require={
        'test': [
            'plone.app.contentrules',
            'plone.app.testing',
            'plone.testing>=5.0.0',
            'Products.ATContentTypes',
            'unittest2',
        ],
    },
    entry_points="""
    [celery_tasks]
    castle = wildcard.hps.hook
    [z3c.autoinclude.plugin]
    target = plone
    [console_scripts]
    update_locale = wildcard.hps.locales.update:update_locale
    reindex_hps = wildcard.hps.scripts.reindex:setup_and_run
    """,
)
