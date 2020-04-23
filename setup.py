#!/usr/bin/env python3

from setuptools import find_packages, setup

requirements = [
    'pulpcore>=3.3,<3.4',
    'ecdsa~=0.13.2',
    'pyjwkest~=1.4.0',
    'pyjwt[crypto]~=1.7.1'
]

with open('README.rst') as f:
    long_description = f.read()

setup(
    name='pulp-container',
    version='1.3.0',
    description='Container plugin for the Pulp Project',
    long_description=long_description,
    license='GPLv2+',
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    url='https://pulpproject.org/',
    python_requires='>=3.6',
    install_requires=requirements,
    include_package_data=True,
    packages=find_packages(exclude=['tests', 'tests.*']),
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Development Status :: 5 - Production/Stable',
        'Framework :: Django',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    entry_points={
        'pulpcore.plugin': [
            'pulp_container = pulp_container:default_app_config',
        ]
    }
)
