#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""materialsCloudCompute is a library for performing condensed matter calculations in the AWS cloud

DESCRIPTION
"""
import os
import re
from setuptools import setup

DOCLINES = __doc__.split('\n')

classifiers = ['Development Status :: 4 - Beta',
               'Intended Audience :: Developers',
               'License :: OSI Approved :: BSD License',
               'Operating System :: OS Independent',
               'Programming Language :: Python',
               'Programming Language :: Python :: 3.6',
               'Programming Language :: Python :: 3.7']

def get_version():
    """Pulls version from mcc/__init__.py::__version__"""
    with open(os.path.join("mcc", "__init__.py")) as f:
        for line in f.readlines():
            match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", line, re.M)
            if match:
                return match.group(1)
        raise RuntimeError(f"Unable to find version string in {os.path.join('mcc', '__init__.py')}.")


def setup_package():
    """Setup package function"""
    metadata = dict(name="materialsCloudCompute",
                    version=get_version(),
                    description=DOCLINES[0],
                    long_description='\n'.join(DOCLINES[2:]),
                    classifiers=classifiers,
                    author="David M Fobes",
                    author_email="dfobes@lanl.gov",
                    license="BSD",
                    platforms=["macOS", "linux", "unix"],
                    install_requires=["click", "awscli", "boto3"],
                    setup_requires=["pytest-runner"],
                    tests_require=["pytest", "codecov"],
                    entry_points={"console_scripts": ["mcc=mcc.monitor.server:main"]},
                    packages=["mcc", "mcc.monitor"]
                   )

    setup(**metadata)


if __name__ == "__main__":
    setup_package()
