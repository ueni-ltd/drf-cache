# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='drf-cache',
    version='0.0.1',
    author='Michal Bock',
    author_email='michal.bock@gmail.com',
    packages=['drf_cache'],
    url='https://github.com/ueni-ltd/drf-cache',
    license='MIT',
    description='Django app that that implements caching for rest_framework views.',
    long_description=open('README.md').read(),
    zip_safe=False,
    include_package_data=True,
    package_data={'': ['README.md']},
    install_requires=['django>=1.8.0', 'djangorestframework>=3.7.0'],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
