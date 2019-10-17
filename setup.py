import os
from codecs import open
from setuptools import setup

setup(
    name='states',
    version='0.1.10',
    description='state machine for python classes',
    long_description='see <https://github.com/gemerden/statemachine>',  # after long battle to get markdown to work on Pypi
    author='Lars van Gemerden',
    author_email='gemerden@gmail.com',
    license='MIT License',
    packages=['states'],
    install_requires=[],
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 4 - Beta',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2.7',
    ],
    python_requires='>=2.7, <3',
    keywords='access data structure getter setter deleter iterator utility tool',
)
