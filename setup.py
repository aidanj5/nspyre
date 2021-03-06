#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup
import codecs

def read(filename):
	return codecs.open(filename, encoding='utf-8').read()

long_description = '\n\n'.join([read('LICENSE'),
								read('README.md'),
								read('AUTHORS')])

__doc__ = long_description

setup(name='nspyre',
	version='0.2.1',
	license='MIT',
	description='Networked Scientific Python Research Environment',
	long_description=long_description,
	keywords='measurement control instrumentation science',
	author='Alexandre Bourassa',
	author_email='abourassa@uchicago.edu',
	url='https://github.com/AlexBourassa/nspyre',
	packages=['nspyre',],
	install_requires=[
		'numpy>=1.16.4',
		'pyvisa-py>=0.4.1',
		'pyqt5>=5.13.2',
		'msgpack>=0.6.2',
		'msgpack-numpy>=0.4.4.3',
		#'pyzmq>=18.0.2', use conda install for now
		'pymongo>=3.9.0',
		'pandas>=0.25.2',
		'QScintilla>=2.11.3',
		'pyqtgraph>=0.11.0',
		'pyyaml>=5.1.2',
		'scipy>=1.2.1',
		'tqdm>=4.32.2',
		#'lantzdev>=0.5', # TODO integrate new lantz version
		'lantz @ git+https://github.com/awsch/lantz.git@drivers_develop'],
	platforms='any',
	classifiers=[
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: MIT License",
	],
)
