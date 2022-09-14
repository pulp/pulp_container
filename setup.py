#!/usr/bin/env python3

from setuptools import find_packages, setup

with open("requirements.txt") as requirements:
    requirements = requirements.readlines()

with open("README.rst") as f:
    long_description = f.read()

setup(
    name="pulp-container",
    version="2.10.9",
    description="Container plugin for the Pulp Project",
    long_description=long_description,
    license="GPLv2+",
    author="Pulp Team",
    author_email="pulp-list@redhat.com",
    url="https://pulpproject.org/",
    python_requires=">=3.8",
    install_requires=requirements,
    include_package_data=True,
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    entry_points={"pulpcore.plugin": ["pulp_container = pulp_container:default_app_config"]},
)
