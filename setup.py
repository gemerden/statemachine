from setuptools import setup

setup(
    name='states3',
    version='0.5.3',
    description='state machine for python classes',
    long_description='see <https://github.com/gemerden/statemachine>',  # after long battle to get markdown to work on PyPI
    author='Lars van Gemerden',
    author_email='gemerden@gmail.com',
    url='https://github.com/gemerden/statemachine',
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
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    python_requires='>=3.6',
    keywords='statemachine states transitions object-oriented nested multi-state callbacks '
             'condition contextmanager performance easy-to-use low-memory',
)
