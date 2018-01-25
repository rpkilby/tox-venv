import os
import platform

import py
import pytest

import tox
from tox._pytestplugin import ReportExpectMock
try:
    import json
except ImportError:
    import simplejson as json

pytest_plugins = "pytester"

from tox.session import Session  # noqa #E402 module level import not at top of file
from tox.config import parseconfig  # noqa #E402 module level import not at top of file

from tox_venv.hooks import use_builtin_venv


def test_report_protocol(newconfig):
    config = newconfig([], """
            [testenv:mypython]
            deps=xy
    """)

    class Popen:
        def __init__(self, *args, **kwargs):
            pass

        def communicate(self):
            return "", ""

        def wait(self):
            pass

    session = Session(config, popen=Popen,
                      Report=ReportExpectMock)
    report = session.report
    report.expect("using")
    venv = session.getvenv("mypython")
    action = session.newaction(venv, "update")
    venv.update(action)
    report.expect("logpopen")


def test__resolve_pkg(tmpdir, mocksession):
    distshare = tmpdir.join("distshare")
    spec = distshare.join("pkg123-*")
    pytest.raises(tox.exception.MissingDirectory, 'mocksession._resolve_pkg(spec)')
    distshare.ensure(dir=1)
    pytest.raises(tox.exception.MissingDependency, 'mocksession._resolve_pkg(spec)')
    distshare.ensure("pkg123-1.3.5.zip")
    p = distshare.ensure("pkg123-1.4.5.zip")

    mocksession.report.clear()
    result = mocksession._resolve_pkg(spec)
    assert result == p
    mocksession.report.expect("info", "determin*pkg123*")
    distshare.ensure("pkg123-1.4.7dev.zip")
    mocksession._clearmocks()
    result = mocksession._resolve_pkg(spec)
    mocksession.report.expect("warning", "*1.4.7*")
    assert result == p
    mocksession._clearmocks()
    distshare.ensure("pkg123-1.4.5a1.tar.gz")
    result = mocksession._resolve_pkg(spec)
    assert result == p


def test__resolve_pkg_doubledash(tmpdir, mocksession):
    distshare = tmpdir.join("distshare")
    p = distshare.ensure("pkg-mine-1.3.0.zip")
    res = mocksession._resolve_pkg(distshare.join("pkg-mine*"))
    assert res == p
    distshare.ensure("pkg-mine-1.3.0a1.zip")
    res = mocksession._resolve_pkg(distshare.join("pkg-mine*"))
    assert res == p


class TestSession:
    def test_make_sdist(self, initproj):
        initproj("example123-0.5", filedefs={
            'tests': {'test_hello.py': "def test_hello(): pass"},
            'tox.ini': '''
            '''
        })
        config = parseconfig([])
        session = Session(config)
        sdist = session.get_installpkg_path()
        assert sdist.check()
        assert sdist.ext == ".zip"
        assert sdist == config.distdir.join(sdist.basename)
        sdist2 = session.get_installpkg_path()
        assert sdist2 == sdist
        sdist.write("hello")
        assert sdist.stat().size < 10
        sdist_new = Session(config).get_installpkg_path()
        assert sdist_new == sdist
        assert sdist_new.stat().size > 10

    def test_make_sdist_distshare(self, tmpdir, initproj):
        distshare = tmpdir.join("distshare")
        initproj("example123-0.6", filedefs={
            'tests': {'test_hello.py': "def test_hello(): pass"},
            'tox.ini': '''
            [tox]
            distshare=%s
            ''' % distshare
        })
        config = parseconfig([])
        session = Session(config)
        sdist = session.get_installpkg_path()
        assert sdist.check()
        assert sdist.ext == ".zip"
        assert sdist == config.distdir.join(sdist.basename)
        sdist_share = config.distshare.join(sdist.basename)
        assert sdist_share.check()
        assert sdist_share.read("rb") == sdist.read("rb"), (sdist_share, sdist)

    def test_log_pcall(self, mocksession):
        mocksession.config.logdir.ensure(dir=1)
        assert not mocksession.config.logdir.listdir()
        action = mocksession.newaction(None, "something")
        action.popen(["echo", ])
        match = mocksession.report.getnext("logpopen")
        assert match[1].outpath.relto(mocksession.config.logdir)
        assert match[1].shell is False

    def test_summary_status(self, initproj, capfd):
        initproj("logexample123-0.5", filedefs={
            'tests': {'test_hello.py': "def test_hello(): pass"},
            'tox.ini': '''
            [testenv:hello]
            [testenv:world]
            '''
        })
        config = parseconfig([])
        session = Session(config)
        envs = session.venvlist
        assert len(envs) == 2
        env1, env2 = envs
        env1.status = "FAIL XYZ"
        assert env1.status
        env2.status = 0
        assert not env2.status
        session._summary()
        out, err = capfd.readouterr()
        exp = "%s: FAIL XYZ" % env1.envconfig.envname
        assert exp in out
        exp = "%s: commands succeeded" % env2.envconfig.envname
        assert exp in out

    def test_getvenv(self, initproj, capfd):
        initproj("logexample123-0.5", filedefs={
            'tests': {'test_hello.py': "def test_hello(): pass"},
            'tox.ini': '''
            [testenv:hello]
            [testenv:world]
            '''
        })
        config = parseconfig([])
        session = Session(config)
        venv1 = session.getvenv("hello")
        venv2 = session.getvenv("hello")
        assert venv1 is venv2
        venv1 = session.getvenv("world")
        venv2 = session.getvenv("world")
        assert venv1 is venv2
        pytest.raises(LookupError, lambda: session.getvenv("qwe"))


# not sure we want this option ATM
def XXX_test_package(cmd, initproj):
    initproj("myproj-0.6", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'MANIFEST.in': """
            include doc
            include myproj
            """,
        'tox.ini': ''
    })
    result = cmd.run("tox", "package")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*created sdist package at*",
    ])


def test_minversion(cmd, initproj):
    initproj("interp123-0.5", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'tox.ini': '''
            [tox]
            minversion = 6.0
        '''
    })
    result = cmd.run("tox", "-v")
    result.stdout.fnmatch_lines([
        "*ERROR*tox version is * required is at least 6.0*"
    ])
    assert result.ret


def test_notoxini_help_still_works(initproj, cmd):
    initproj("example123-0.5", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
    })
    result = cmd.run("tox", "-h")
    result.stderr.fnmatch_lines([
        "*ERROR*tox.ini*"
    ])
    result.stdout.fnmatch_lines([
        "*--help*"
    ])
    assert not result.ret


def test_notoxini_help_ini_still_works(initproj, cmd):
    initproj("example123-0.5", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
    })
    result = cmd.run("tox", "--help-ini")
    result.stderr.fnmatch_lines([
        "*ERROR*tox.ini*"
    ])
    result.stdout.fnmatch_lines([
        "*setenv*"
    ])
    assert not result.ret


def test_envdir_equals_toxini_errors_out(cmd, initproj):
    initproj("interp123-0.7", filedefs={
        'tox.ini': '''
            [testenv]
            envdir={toxinidir}
        '''
    })
    result = cmd.run("tox")
    result.stdout.fnmatch_lines([
        "ERROR*venv*delete*",
        "*ConfigError*envdir must not equal toxinidir*",
    ])
    assert result.ret


def test_run_custom_install_command_error(cmd, initproj):
    initproj("interp123-0.5", filedefs={
        'tox.ini': '''
            [testenv]
            install_command=./tox.ini {opts} {packages}
        '''
    })
    result = cmd.run("tox")
    result.stdout.fnmatch_lines([
        "ERROR: invocation failed (errno *), args: ['*/tox.ini*",
    ])
    assert result.ret


def test_unknown_interpreter_and_env(cmd, initproj):
    initproj("interp123-0.5", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'tox.ini': '''
            [testenv:python]
            basepython=xyz_unknown_interpreter
            [testenv]
            changedir=tests
        '''
    })
    result = cmd.run("tox")
    assert result.ret
    result.stdout.fnmatch_lines([
        "*ERROR*InterpreterNotFound*xyz_unknown_interpreter*",
    ])

    result = cmd.run("tox", "-exyz")
    assert result.ret
    result.stdout.fnmatch_lines([
        "*ERROR*unknown*",
    ])


def test_unknown_interpreter(cmd, initproj):
    initproj("interp123-0.5", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'tox.ini': '''
            [testenv:python]
            basepython=xyz_unknown_interpreter
            [testenv]
            changedir=tests
        '''
    })
    result = cmd.run("tox")
    assert result.ret
    result.stdout.fnmatch_lines([
        "*ERROR*InterpreterNotFound*xyz_unknown_interpreter*",
    ])


def test_skip_platform_mismatch(cmd, initproj):
    initproj("interp123-0.5", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'tox.ini': '''
            [testenv]
            changedir=tests
            platform=x123
        '''
    })
    result = cmd.run("tox")
    assert not result.ret
    result.stdout.fnmatch_lines("""
        SKIPPED*platform mismatch*
    """)


def test_skip_unknown_interpreter(cmd, initproj):
    initproj("interp123-0.5", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'tox.ini': '''
            [testenv:python]
            basepython=xyz_unknown_interpreter
            [testenv]
            changedir=tests
        '''
    })
    result = cmd.run("tox", "--skip-missing-interpreters")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*SKIPPED*InterpreterNotFound*xyz_unknown_interpreter*",
    ])


def test_unknown_dep(cmd, initproj):
    initproj("dep123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'tox.ini': '''
            [testenv]
            deps=qweqwe123
            changedir=tests
        '''
    })
    result = cmd.run("tox", )
    assert result.ret
    result.stdout.fnmatch_lines([
        "*ERROR*could not install*qweqwe123*",
    ])


def test_venv_special_chars_issue252(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'tox.ini': '''
            [tox]
            envlist = special&&1
            [testenv:special&&1]
            changedir=tests
        '''
    })
    result = cmd.run("tox", )
    assert result.ret == 0
    result.stdout.fnmatch_lines([
        "*installed*pkg123*"
    ])


def test_unknown_environment(cmd, initproj):
    initproj("env123-0.7", filedefs={
        'tox.ini': ''
    })
    result = cmd.run("tox", "-e", "qpwoei")
    assert result.ret
    result.stdout.fnmatch_lines([
        "*ERROR*unknown*environment*qpwoei*",
    ])


def test_skip_sdist(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'setup.py': """
            syntax error
        """,
        'tox.ini': '''
            [tox]
            skipsdist=True
            [testenv]
            commands=python -c "print('done')"
        '''
    })
    result = cmd.run("tox", )
    assert result.ret == 0


def test_minimal_setup_py_empty(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'setup.py': """
        """,
        'tox.ini': ''

    })
    result = cmd.run("tox", )
    assert result.ret == 1
    result.stdout.fnmatch_lines([
        "*ERROR*empty*",
    ])


def test_minimal_setup_py_comment_only(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'setup.py': """\n# some comment

        """,
        'tox.ini': ''

    })
    result = cmd.run("tox", )
    assert result.ret == 1
    result.stdout.fnmatch_lines([
        "*ERROR*empty*",
    ])


def test_minimal_setup_py_non_functional(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'setup.py': """
        import sys

        """,
        'tox.ini': ''

    })
    result = cmd.run("tox", )
    assert result.ret == 1
    result.stdout.fnmatch_lines([
        "*ERROR*check setup.py*",
    ])


def test_sdist_fails(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'setup.py': """
            syntax error
        """,
        'tox.ini': '',
    })
    result = cmd.run("tox", )
    assert result.ret
    result.stdout.fnmatch_lines([
        "*FAIL*could not package project*",
    ])


@pytest.mark.xfail(strict=True)  # this change is not released yet
def test_no_setup_py_exits(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tox.ini': """
            [testenv]
            commands=python -c "2 + 2"
        """
    })
    os.remove("setup.py")
    result = cmd.run("tox", )
    assert result.ret
    result.stdout.fnmatch_lines([
        "*ERROR*No setup.py file found*"
    ])


def test_package_install_fails(cmd, initproj):
    initproj("pkg123-0.7", filedefs={
        'tests': {'test_hello.py': "def test_hello(): pass"},
        'setup.py': """
            from setuptools import setup
            setup(
                name='pkg123',
                description='pkg123 project',
                version='0.7',
                license='MIT',
                platforms=['unix', 'win32'],
                packages=['pkg123',],
                install_requires=['qweqwe123'],
                )
            """,
        'tox.ini': '',
    })
    result = cmd.run("tox", )
    assert result.ret
    result.stdout.fnmatch_lines([
        "*InvocationError*",
    ])


class TestToxRun:
    @pytest.fixture
    def example123(self, initproj):
        initproj("example123-0.5", filedefs={
            'tests': {
                'test_hello.py': """
                    def test_hello(pytestconfig):
                        pass
                """,
            },
            'tox.ini': '''
                [testenv]
                changedir=tests
                commands= pytest --basetemp={envtmpdir} \
                                  --junitxml=junit-{envname}.xml
                deps=pytest
            '''
        })

    def test_toxuone_env(self, cmd, example123):
        result = cmd.run("tox")
        assert not result.ret
        result.stdout.fnmatch_lines([
            "*junit-python.xml*",
            "*1 passed*",
        ])
        result = cmd.run("tox", "-epython", )
        assert not result.ret
        result.stdout.fnmatch_lines([
            "*1 passed*",
            "*summary*",
            "*python: commands succeeded"
        ])

    def test_different_config_cwd(self, cmd, example123, monkeypatch):
        # see that things work with a different CWD
        monkeypatch.chdir(cmd.tmpdir)
        result = cmd.run("tox", "-c", "example123/tox.ini")
        assert not result.ret
        result.stdout.fnmatch_lines([
            "*1 passed*",
            "*summary*",
            "*python: commands succeeded"
        ])

    def test_json(self, cmd, example123):
        # see that tests can also fail and retcode is correct
        testfile = py.path.local("tests").join("test_hello.py")
        assert testfile.check()
        testfile.write("def test_fail(): assert 0")
        jsonpath = cmd.tmpdir.join("res.json")
        result = cmd.run("tox", "--result-json", jsonpath)
        assert result.ret == 1
        data = json.load(jsonpath.open("r"))
        verify_json_report_format(data)
        result.stdout.fnmatch_lines([
            "*1 failed*",
            "*summary*",
            "*python: *failed*",
        ])


def test_develop(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
    """})
    result = cmd.run("tox", "-vv", "--develop")
    assert not result.ret
    assert "sdist-make" not in result.stdout.str()


def test_usedevelop(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
            [testenv]
            usedevelop=True
    """})
    result = cmd.run("tox", "-vv")
    assert not result.ret
    assert "sdist-make" not in result.stdout.str()


def test_usedevelop_mixed(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
            [testenv:devenv]
            usedevelop=True
            [testenv:nondev]
            usedevelop=False
    """})

    # running only 'devenv' should not do sdist
    result = cmd.run("tox", "-vv", "-e", "devenv")
    assert not result.ret
    assert "sdist-make" not in result.stdout.str()

    # running all envs should do sdist
    result = cmd.run("tox", "-vv")
    assert not result.ret
    assert "sdist-make" in result.stdout.str()


@pytest.mark.parametrize("src_root", [".", "src"])
def test_test_usedevelop(cmd, initproj, src_root):
    initproj("example123-0.5", src_root=src_root, filedefs={
        'tests': {
            'test_hello.py': """
                def test_hello(pytestconfig):
                    pass
            """,
        },
        'tox.ini': '''
            [testenv]
            usedevelop=True
            changedir=tests
            commands=
                pytest --basetemp={envtmpdir} --junitxml=junit-{envname}.xml []
            deps=pytest
        '''
    })
    result = cmd.run("tox", "-v")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*junit-python.xml*",
        "*1 passed*",
    ])
    assert "sdist-make" not in result.stdout.str()
    result = cmd.run("tox", "-epython", )
    assert not result.ret
    assert "develop-inst-noop" in result.stdout.str()
    result.stdout.fnmatch_lines([
        "*1 passed*",
        "*summary*",
        "*python: commands succeeded"
    ])
    # see that things work with a different CWD
    old = cmd.tmpdir.chdir()
    result = cmd.run("tox", "-c", "example123/tox.ini")
    assert not result.ret
    assert "develop-inst-noop" in result.stdout.str()
    result.stdout.fnmatch_lines([
        "*1 passed*",
        "*summary*",
        "*python: commands succeeded"
    ])
    old.chdir()
    # see that tests can also fail and retcode is correct
    testfile = py.path.local("tests").join("test_hello.py")
    assert testfile.check()
    testfile.write("def test_fail(): assert 0")
    result = cmd.run("tox", )
    assert result.ret
    assert "develop-inst-noop" in result.stdout.str()
    result.stdout.fnmatch_lines([
        "*1 failed*",
        "*summary*",
        "*python: *failed*",
    ])
    # test develop is called if setup.py changes
    setup_py = py.path.local("setup.py")
    setup_py.write(setup_py.read() + ' ')
    result = cmd.run("tox", )
    assert result.ret
    assert "develop-inst-nodeps" in result.stdout.str()


def _alwayscopy_not_supported():
    # This is due to virtualenv bugs with alwayscopy in some platforms
    # see: https://github.com/pypa/virtualenv/issues/565
    if hasattr(platform, 'linux_distribution'):
        _dist = platform.linux_distribution(full_distribution_name=False)
        if _dist[0] == 'centos' and _dist[1][0] == '7':
            return True
    return False


@pytest.mark.skipif(_alwayscopy_not_supported(), reason="Platform doesnt support alwayscopy")
def test_alwayscopy(initproj, cmd, mocksession):
    initproj("example123", filedefs={'tox.ini': """
            [testenv]
            commands={envpython} --version
            alwayscopy=True
    """})
    venv = mocksession.getenv('python')
    result = cmd.run("tox", "-vv")
    assert not result.ret

    out = result.stdout.str()
    if use_builtin_venv(venv):
        assert "venv --copies" in out
    else:
        assert "virtualenv --always-copy" in out


def test_alwayscopy_default(initproj, cmd, mocksession):
    initproj("example123", filedefs={'tox.ini': """
            [testenv]
            commands={envpython} --version
    """})
    venv = mocksession.getenv('python')
    result = cmd.run("tox", "-vv")
    assert not result.ret

    out = result.stdout.str()
    if use_builtin_venv(venv):
        assert "venv --copies" not in out
    else:
        assert "virtualenv --always-copy" not in out


@pytest.mark.xfail(strict=True)  # this change is not released yet
def test_empty_activity_ignored(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
            [testenv]
            list_dependencies_command=echo
            commands={envpython} --version
    """})
    result = cmd.run("tox")
    assert not result.ret
    assert "installed:" not in result.stdout.str()


def test_empty_activity_shown_verbose(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
            [testenv]
            list_dependencies_command=echo
            commands={envpython} --version
    """})
    result = cmd.run("tox", "-v")
    assert not result.ret
    assert "installed:" in result.stdout.str()


def test_test_piphelp(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
        # content of: tox.ini
        [testenv]
        commands=pip -h
        [testenv:py26]
        basepython=python
        [testenv:py27]
        basepython=python
    """})
    result = cmd.run("tox")
    assert not result.ret


def test_notest(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
        # content of: tox.ini
        [testenv:py26]
        basepython=python
    """})
    result = cmd.run("tox", "-v", "--notest")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*summary*",
        "*py26*skipped tests*",
    ])
    result = cmd.run("tox", "-v", "--notest", "-epy26")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*py26*reusing*",
    ])


def test_PYC(initproj, cmd, monkeypatch):
    initproj("example123", filedefs={'tox.ini': ''})
    monkeypatch.setenv("PYTHONDOWNWRITEBYTECODE", 1)
    result = cmd.run("tox", "-v", "--notest")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*create*",
    ])


def test_env_VIRTUALENV_PYTHON(initproj, cmd, monkeypatch):
    initproj("example123", filedefs={'tox.ini': ''})
    monkeypatch.setenv("VIRTUALENV_PYTHON", '/FOO')
    result = cmd.run("tox", "-v", "--notest")
    assert not result.ret, result.stdout.lines
    result.stdout.fnmatch_lines([
        "*create*",
    ])


def test_sdistonly(initproj, cmd):
    initproj("example123", filedefs={'tox.ini': """
    """})
    result = cmd.run("tox", "-v", "--sdistonly")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*sdist-make*setup.py*",
    ])
    assert "-mvirtualenv" not in result.stdout.str()


def test_separate_sdist_no_sdistfile(cmd, initproj):
    distshare = cmd.tmpdir.join("distshare")
    initproj(("pkg123-foo", "0.7"), filedefs={
        'tox.ini': """
            [tox]
            distshare=%s
        """ % distshare
    })
    result = cmd.run("tox", "--sdistonly")
    assert not result.ret
    distshare_files = distshare.listdir()
    assert len(distshare_files) == 1
    sdistfile = distshare_files[0]
    assert 'pkg123-foo-0.7.zip' in str(sdistfile)


def test_separate_sdist(cmd, initproj):
    distshare = cmd.tmpdir.join("distshare")
    initproj("pkg123-0.7", filedefs={
        'tox.ini': """
            [tox]
            distshare=%s
            sdistsrc={distshare}/pkg123-0.7.zip
        """ % distshare
    })
    result = cmd.run("tox", "--sdistonly")
    assert not result.ret
    sdistfiles = distshare.listdir()
    assert len(sdistfiles) == 1
    sdistfile = sdistfiles[0]
    result = cmd.run("tox", "-v", "--notest")
    assert not result.ret
    result.stdout.fnmatch_lines([
        "*inst*%s*" % sdistfile,
    ])


def test_sdist_latest(tmpdir, newconfig):
    distshare = tmpdir.join("distshare")
    config = newconfig([], """
            [tox]
            distshare=%s
            sdistsrc={distshare}/pkg123-*
    """ % distshare)
    p = distshare.ensure("pkg123-1.4.5.zip")
    distshare.ensure("pkg123-1.4.5a1.zip")
    session = Session(config)
    sdist_path = session.get_installpkg_path()
    assert sdist_path == p


def test_installpkg(tmpdir, newconfig):
    p = tmpdir.ensure("pkg123-1.0.zip")
    config = newconfig(["--installpkg=%s" % p], "")
    session = Session(config)
    sdist_path = session.get_installpkg_path()
    assert sdist_path == p


def test_envsitepackagesdir(cmd, initproj):
    initproj("pkg512-0.0.5", filedefs={
        'tox.ini': """
        [testenv]
        commands=
            python -c "print(r'X:{envsitepackagesdir}')"
    """})
    result = cmd.run("tox")
    assert result.ret == 0
    result.stdout.fnmatch_lines("""
        X:*tox*site-packages*
    """)


def test_envsitepackagesdir_skip_missing_issue280(cmd, initproj):
    initproj("pkg513-0.0.5", filedefs={
        'tox.ini': """
        [testenv]
        basepython=/usr/bin/qwelkjqwle
        commands=
            {envsitepackagesdir}
    """})
    result = cmd.run("tox", "--skip-missing-interpreters")
    assert result.ret == 0
    result.stdout.fnmatch_lines("""
        SKIPPED:*qwelkj*
    """)


@pytest.mark.parametrize('verbosity', ['', '-v', '-vv'])
def test_verbosity(cmd, initproj, verbosity):
    initproj("pkgX-0.0.5", filedefs={
        'tox.ini': """
        [testenv]
    """})
    result = cmd.run("tox", verbosity)
    assert result.ret == 0

    needle = "Successfully installed pkgX-0.0.5"
    if verbosity == '-vv':
        assert any(needle in line for line in result.outlines)
    else:
        assert all(needle not in line for line in result.outlines)


def verify_json_report_format(data, testenvs=True):
    assert data["reportversion"] == "1"
    assert data["toxversion"] == tox.__version__
    if testenvs:
        for envname, envdata in data["testenvs"].items():
            for commandtype in ("setup", "test"):
                if commandtype not in envdata:
                    continue
                for command in envdata[commandtype]:
                    assert command["output"]
                    assert command["retcode"]
            if envname != "GLOB":
                assert isinstance(envdata["installed_packages"], list)
                pyinfo = envdata["python"]
                assert isinstance(pyinfo["version_info"], list)
                assert pyinfo["version"]
                assert pyinfo["executable"]


def test_envtmpdir(initproj, cmd):
    initproj("foo", filedefs={
        # This file first checks that envtmpdir is existent and empty. Then it
        # creates an empty file in that directory.  The tox command is run
        # twice below, so this is to test whether the directory is cleared
        # before the second run.
        'check_empty_envtmpdir.py': '''if True:
            import os
            from sys import argv
            envtmpdir = argv[1]
            assert os.path.exists(envtmpdir)
            assert os.listdir(envtmpdir) == []
            open(os.path.join(envtmpdir, 'test'), 'w').close()
        ''',
        'tox.ini': '''
            [testenv]
            commands=python check_empty_envtmpdir.py {envtmpdir}
        '''
    })

    result = cmd.run("tox")
    assert not result.ret

    result = cmd.run("tox")
    assert not result.ret


def test_missing_env_fails(initproj, cmd):
    initproj("foo", filedefs={'tox.ini': "[testenv:foo]\ncommands={env:VAR}"})
    result = cmd.run("tox")
    assert result.ret == 1
    result.stdout.fnmatch_lines(["*foo: unresolvable substitution(s): 'VAR'*"])
