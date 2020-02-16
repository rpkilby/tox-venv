tox-venv
========

.. image:: https://travis-ci.org/tox-dev/tox-venv.svg?branch=master
  :target: https://travis-ci.org/tox-dev/tox-venv
.. image:: https://ci.appveyor.com/api/projects/status/fak35ur9yibmn0ly?svg=true
  :target: https://ci.appveyor.com/project/rpkilby/tox-venv
.. image:: https://codecov.io/gh/tox-dev/tox-venv/branch/master/graph/badge.svg
  :target: https://codecov.io/gh/tox-dev/tox-venv
.. image:: https://img.shields.io/pypi/v/tox-venv.svg
  :target: https://pypi.python.org/pypi/tox-venv
.. image:: https://img.shields.io/pypi/pyversions/tox-venv.svg
  :target: https://pypi.org/project/tox-venv/
.. image:: https://img.shields.io/pypi/l/tox-venv.svg
  :target: https://pypi.python.org/pypi/tox-venv


What is tox-venv?
-----------------

tox-venv is a plugin that uses Python 3's builtin ``venv`` module for creating test environments instead of creating
them with the ``virtualenv`` package. For Python versions that do not include ``venv`` (namely 3.2 and earlier), this
package does nothing and reverts to tox's default implementation.


Why use tox-venv?
-----------------

tox-venv was originally created because of compatibility issues between modern versions of Python and an aging
``virtualenv``. Since then, ``virtualenv`` has undergone a major rewrite, and tox-venv has largely been made
unnecessary. However, there may be cases where it's preferable to create test environments directly with the
``venv`` module, in which case you should use tox-venv.


Installation & Usage
--------------------

To use tox-venv, install it alongside tox in your environment. Then, run ``tox`` as normal - no configuration necessary.

.. code-block::

    $ pip install tox tox-venv
    $ tox

If you have already ran tox, it's necessary to recreate the test envs. Either run ``tox --recreate``, or delete the
``.tox`` directory.


Compatibility
-------------

tox-venv is compatible with both Python 2 and 3, however it only creates test environments in Python 3.3 and later.
Python 3.3 environments are only partially compatible, as not all options (such as ``--copies``/``--symlinks``) were
supported. Environments for Python 3.4 and later are fully compatible.


Release process
---------------

* Update changelog
* Update package version in setup.py
* Create git tag for version
* Upload release to PyPI

.. code-block::

    $ pip install -U twine setuptools wheel
    $ rm -rf dist/ build/
    # python setup.py sdist bdist_wheel
    $ twine upload dist/*
