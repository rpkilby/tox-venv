import io

from setuptools import setup, find_packages


def get_long_description():
    with io.open('README.rst', encoding='utf-8') as f:
        return f.read()


setup(
    name='tox-venv',
    description='Use python3 venvs for python3 tox testenvs',
    long_description=get_long_description(),
    author='Ryan P Kilby',
    author_email='rpkilby@ncsu.edu',
    url='https://github.com/tox-dev/tox-venv',
    license='BSD',
    version='0.3.1',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    entry_points={'tox': ['venv = tox_venv.hooks']},
    install_requires=['tox>=2.0'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: tox',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Testing',
    ],
)
