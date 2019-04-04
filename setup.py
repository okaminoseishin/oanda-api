#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='oanda',
    version=0.2,
    description='Wrapper for Oanda V20 API',
    project_urls={
        'Source code': 'https://github.com/okaminoseishin/oanda-api'
    },

    license='GNU GPL v3',
    author='Vladyslav Cheriachukin',
    author_email='vladyslav.cheriachukin@gmail.com',
    keywords='wrapper oanda api forex trading',

    packages=find_packages(),
    python_requires='>=3.7.2',
    install_requires=[
        'wrapt>=1.11.1',
        'requests>=2.21.0'
    ]
)
