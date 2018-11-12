import os
from codecs import open
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file; convert to .rst is possible
try:
    import pypandoc
    long_description = pypandoc.convert_file(os.path.join(here, 'README.md'), 'rst')
except Exception:
    with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()

setup(
    name='states',
    version='0.1.7',
    description='state machine for python classes',
    long_description=long_description,
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
