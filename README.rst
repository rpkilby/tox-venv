tox-venv
========

.. image:: https://travis-ci.org/tox-dev/tox-venv.svg?branch=master
  :target: https://travis-ci.org/tox-dev/tox-venv
.. image:: https://ci.appveyor.com/api/projects/status/fak35ur9yibmn0ly?svg=true
  :target: https://ci.appveyor.com/project/rpkilby/tox-venv



What is tox-venv?
-----------------

tox-venv is a plugin that uses Python 3's builtin ``venv`` module for creating test environments, instead of creating
them with the ``virtualenv`` package.


Why use tox-venv?
-----------------

``virtualenv`` is historically python 2/3 compatible, however to achieve this, it ships some files that are pinned at
their python 2.6 version, such as the ``site`` module (see: pypa/virtualenv#355). This has a couple of effects:

- Builds using the ``-Werror`` option fail, as the deprecations are raised before the test suite can run.
- Users cannot take advantage of newer features of the ``site`` module in their test environments.
- Eventually, these deprecations will become exceptions in future versions of python.

Eventually, tox-venv should become obsolete once the corresponding PR is merged (tox-dev/tox#630). At that point,
it should be safe to simply remove tox-venv from your test dependencies.
