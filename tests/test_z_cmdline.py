import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import py
import pytest

import tox
from tox.config import parseconfig
from tox.reporter import Verbosity
from tox.session import Session

from tox_venv.hooks import use_builtin_venv

pytest_plugins = "pytester"


class TestSession:
    def test_log_pcall(self, mocksession):
        mocksession.logging_levels(quiet=Verbosity.DEFAULT, verbose=Verbosity.INFO)
        mocksession.config.logdir.ensure(dir=1)
        assert not mocksession.config.logdir.listdir()
        with mocksession.newaction("what", "something") as action:
            action.popen(["echo"])
            match = mocksession.report.getnext("logpopen")
            log_name = py.path.local(match[1].split(">")[-1].strip()).relto(
                mocksession.config.logdir
            )
            assert log_name == "what-0.log"

    def test_summary_status(self, initproj, capfd):
        initproj(
            "logexample123-0.5",
            filedefs={
                "tests": {"test_hello.py": "def test_hello(): pass"},
                "tox.ini": """
            [testenv:hello]
            [testenv:world]
            """,
            },
        )
        config = parseconfig([])
        session = Session(config)
        envs = list(session.venv_dict.values())
        assert len(envs) == 2
        env1, env2 = envs
        env1.status = "FAIL XYZ"
        assert env1.status
        env2.status = 0
        assert not env2.status
        session._summary()
        out, err = capfd.readouterr()
        exp = "{}: FAIL XYZ".format(env1.envconfig.envname)
        assert exp in out
        exp = "{}: commands succeeded".format(env2.envconfig.envname)
        assert exp in out

    def test_getvenv(self, initproj):
        initproj(
            "logexample123-0.5",
            filedefs={
                "tests": {"test_hello.py": "def test_hello(): pass"},
                "tox.ini": """
            [testenv:hello]
            [testenv:world]
            """,
            },
        )
        config = parseconfig([])
        session = Session(config)
        venv1 = session.getvenv("hello")
        venv2 = session.getvenv("hello")
        assert venv1 is venv2
        venv1 = session.getvenv("world")
        venv2 = session.getvenv("world")
        assert venv1 is venv2
        with pytest.raises(LookupError):
            session.getvenv("qwe")


def test_notoxini_help_still_works(initproj, cmd):
    initproj("example123-0.5", filedefs={"tests": {"test_hello.py": "def test_hello(): pass"}})
    result = cmd("-h")
    msg = "ERROR: tox config file (either pyproject.toml, tox.ini, setup.cfg) not found\n"
    assert result.err == msg
    assert result.out.startswith("usage: ")
    assert any("--help" in l for l in result.outlines), result.outlines
    result.assert_success(is_run_test_env=False)


def test_notoxini_help_ini_still_works(initproj, cmd):
    initproj("example123-0.5", filedefs={"tests": {"test_hello.py": "def test_hello(): pass"}})
    result = cmd("--help-ini")
    assert any("setenv" in l for l in result.outlines), result.outlines
    result.assert_success(is_run_test_env=False)


def test_envdir_equals_toxini_errors_out(cmd, initproj):
    initproj(
        "interp123-0.7",
        filedefs={
            "tox.ini": """
            [testenv]
            envdir={toxinidir}
        """
        },
    )
    result = cmd()
    assert result.outlines[1] == "ERROR: ConfigError: envdir must not equal toxinidir"
    assert re.match(
        r"ERROR: venv \'python\' in .* would delete project", result.outlines[0]
    ), result.outlines[0]
    result.assert_fail()


def test_run_custom_install_command_error(cmd, initproj):
    initproj(
        "interp123-0.5",
        filedefs={
            "tox.ini": """
            [testenv]
            install_command=./tox.ini {opts} {packages}
        """
        },
    )
    result = cmd()
    result.assert_fail()
    re.match(
        r"ERROR:   python: InvocationError for command .* \(exited with code \d+\)",
        result.outlines[-1],
    ), result.out


def test_unknown_interpreter_and_env(cmd, initproj):
    initproj(
        "interp123-0.5",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "tox.ini": """
            [testenv:python]
            basepython=xyz_unknown_interpreter
            [testenv]
            changedir=tests
            skip_install = true
        """,
        },
    )
    result = cmd()
    result.assert_fail()
    assert any(
        "ERROR: InterpreterNotFound: xyz_unknown_interpreter" == l for l in result.outlines
    ), result.outlines

    result = cmd("-exyz")
    result.assert_fail()
    assert result.out == "ERROR: unknown environment 'xyz'\n"


def test_unknown_interpreter(cmd, initproj):
    initproj(
        "interp123-0.5",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "tox.ini": """
            [testenv:python]
            basepython=xyz_unknown_interpreter
            [testenv]
            changedir=tests
        """,
        },
    )
    result = cmd()
    result.assert_fail()
    assert any(
        "ERROR: InterpreterNotFound: xyz_unknown_interpreter" == l for l in result.outlines
    ), result.outlines


def test_skip_platform_mismatch(cmd, initproj):
    initproj(
        "interp123-0.5",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "tox.ini": """
            [testenv]
            changedir=tests
            platform=x123
        """,
        },
    )
    result = cmd()
    result.assert_success()
    assert any(
        "SKIPPED:  python: platform mismatch ({!r} does not match 'x123')".format(sys.platform)
        == l
        for l in result.outlines
    ), result.outlines


def test_skip_unknown_interpreter(cmd, initproj):
    initproj(
        "interp123-0.5",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "tox.ini": """
            [testenv:python]
            basepython=xyz_unknown_interpreter
            [testenv]
            changedir=tests
        """,
        },
    )
    result = cmd("--skip-missing-interpreters")
    result.assert_success()
    msg = "SKIPPED:  python: InterpreterNotFound: xyz_unknown_interpreter"
    assert any(msg == l for l in result.outlines), result.outlines


def test_skip_unknown_interpreter_result_json(cmd, initproj, tmpdir):
    report_path = tmpdir.join("toxresult.json")
    initproj(
        "interp123-0.5",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "tox.ini": """
            [testenv:python]
            basepython=xyz_unknown_interpreter
            [testenv]
            changedir=tests
        """,
        },
    )
    result = cmd("--skip-missing-interpreters", "--result-json", report_path)
    result.assert_success()
    msg = "SKIPPED:  python: InterpreterNotFound: xyz_unknown_interpreter"
    assert any(msg == l for l in result.outlines), result.outlines
    setup_result_from_json = json.load(report_path)["testenvs"]["python"]["setup"]
    for setup_step in setup_result_from_json:
        assert "InterpreterNotFound" in setup_step["output"]
        assert setup_step["retcode"] == 0


def test_unknown_dep(cmd, initproj):
    initproj(
        "dep123-0.7",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "tox.ini": """
            [testenv]
            deps=qweqwe123
            changedir=tests
        """,
        },
    )
    result = cmd()
    result.assert_fail()
    assert result.outlines[-1].startswith("ERROR:   python: could not install deps [qweqwe123];")


def test_venv_special_chars_issue252(cmd, initproj):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "tox.ini": """
            [tox]
            envlist = special&&1
            [testenv:special&&1]
            changedir=tests
        """,
        },
    )
    result = cmd()
    result.assert_success()
    pattern = re.compile("special&&1 installed: .*pkg123==0.7.*")
    assert any(pattern.match(line) for line in result.outlines), result.outlines


def test_unknown_environment(cmd, initproj):
    initproj("env123-0.7", filedefs={"tox.ini": ""})
    result = cmd("-e", "qpwoei")
    result.assert_fail()
    assert result.out == "ERROR: unknown environment 'qpwoei'\n"


def test_unknown_environment_with_envlist(cmd, initproj):
    initproj(
        "pkg123",
        filedefs={
            "tox.ini": """
            [tox]
            envlist = py{36,37}-django{20,21}
        """
        },
    )
    result = cmd("-e", "py36-djagno21")
    result.assert_fail()
    assert result.out == "ERROR: unknown environment 'py36-djagno21'\n"


def test_minimal_setup_py_empty(cmd, initproj):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "setup.py": """
        """,
            "tox.ini": "",
        },
    )
    result = cmd()
    result.assert_fail()
    assert result.outlines[-1] == "ERROR: setup.py is empty"


def test_minimal_setup_py_comment_only(cmd, initproj):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "setup.py": """\n# some comment

        """,
            "tox.ini": "",
        },
    )
    result = cmd()
    result.assert_fail()
    assert result.outlines[-1] == "ERROR: setup.py is empty"


def test_minimal_setup_py_non_functional(cmd, initproj):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "setup.py": """
        import sys

        """,
            "tox.ini": "",
        },
    )
    result = cmd()
    result.assert_fail()
    assert any(re.match(r".*ERROR.*check setup.py.*", l) for l in result.outlines), result.outlines


def test_sdist_fails(cmd, initproj):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "setup.py": """
            syntax error
        """,
            "tox.ini": "",
        },
    )
    result = cmd()
    result.assert_fail()
    assert any(
        re.match(r".*FAIL.*could not package project.*", l) for l in result.outlines
    ), result.outlines


def test_no_setup_py_exits(cmd, initproj):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tox.ini": """
            [testenv]
            commands=python -c "2 + 2"
        """
        },
    )
    os.remove("setup.py")
    result = cmd()
    result.assert_fail()
    assert any(
        re.match(r".*ERROR.*No setup.py file found.*", l) for l in result.outlines
    ), result.outlines


def test_package_install_fails(cmd, initproj):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tests": {"test_hello.py": "def test_hello(): pass"},
            "setup.py": """
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
            "tox.ini": "",
        },
    )
    result = cmd()
    result.assert_fail()
    assert result.outlines[-1].startswith("ERROR:   python: InvocationError for command ")


@pytest.fixture
def example123(initproj):
    yield initproj(
        "example123-0.5",
        filedefs={
            "tests": {
                "test_hello.py": """
                def test_hello(pytestconfig):
                    pass
            """
            },
            "tox.ini": """
            [testenv]
            changedir=tests
            commands= pytest --basetemp={envtmpdir} \
                              --junitxml=junit-{envname}.xml
            deps=pytest
        """,
        },
    )


def test_toxuone_env(cmd, example123):
    result = cmd()
    result.assert_success()
    assert re.match(
        r".*generated\W+xml\W+file.*junit-python\.xml" r".*\W+1\W+passed.*", result.out, re.DOTALL
    )
    result = cmd("-epython")
    result.assert_success()
    assert re.match(
        r".*\W+1\W+passed.*" r"summary.*" r"python:\W+commands\W+succeeded.*",
        result.out,
        re.DOTALL,
    )


def test_different_config_cwd(cmd, example123):
    # see that things work with a different CWD
    with example123.dirpath().as_cwd():
        result = cmd("-c", "example123/tox.ini")
    result.assert_success()
    assert re.match(
        r".*\W+1\W+passed.*" r"summary.*" r"python:\W+commands\W+succeeded.*",
        result.out,
        re.DOTALL,
    )


def test_result_json(cmd, initproj, example123):
    cwd = initproj(
        "example123",
        filedefs={
            "tox.ini": """
            [testenv]
            deps = setuptools
            commands_pre = python -c 'print("START")'
            commands = python -c 'print("OK")'
                       - python -c 'raise SystemExit(1)'
                       python -c 'raise SystemExit(2)'
                       python -c 'print("SHOULD NOT HAPPEN")'
            commands_post = python -c 'print("END")'
        """
        },
    )
    json_path = cwd / "res.json"
    result = cmd("--result-json", json_path)
    result.assert_fail()
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert data["reportversion"] == "1"
    assert data["toxversion"] == tox.__version__

    for env_data in data["testenvs"].values():
        for command_type in ("setup", "test"):
            if command_type not in env_data:
                assert False, "missing {}".format(command_type)
            for command in env_data[command_type]:
                assert isinstance(command["command"], list)
                assert "retcode" in command
                assert isinstance(command["retcode"], int)
        # virtualenv, deps install, package install, freeze
        assert len(env_data["setup"]) == 4
        # 1 pre + 3 command + 1 post
        assert len(env_data["test"]) == 5
        assert isinstance(env_data["installed_packages"], list)
        pyinfo = env_data["python"]
        assert isinstance(pyinfo["version_info"], list)
        assert pyinfo["version"]
        assert pyinfo["executable"]
    assert "wrote json report at: {}".format(json_path) == result.outlines[-1]


def test_developz(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
    """
        },
    )
    result = cmd("-vv", "--develop")
    result.assert_success()
    assert "sdist-make" not in result.out


def test_usedevelop(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
            [testenv]
            usedevelop=True
    """
        },
    )
    result = cmd("-vv")
    result.assert_success()
    assert "sdist-make" not in result.out


def test_usedevelop_mixed(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
            [testenv:dev]
            usedevelop=True
            [testenv:nondev]
            usedevelop=False
    """
        },
    )

    # running only 'dev' should not do sdist
    result = cmd("-vv", "-e", "dev")
    result.assert_success()
    assert "sdist-make" not in result.out

    # running all envs should do sdist
    result = cmd("-vv")
    result.assert_success()
    assert "sdist-make" in result.out


@pytest.mark.parametrize("skipsdist", [False, True])
@pytest.mark.parametrize("src_root", [".", "src"])
def test_test_usedevelop(cmd, initproj, src_root, skipsdist):
    name = "example123-spameggs"
    base = initproj(
        (name, "0.5"),
        src_root=src_root,
        filedefs={
            "tests": {
                "test_hello.py": """
                def test_hello(pytestconfig):
                    pass
            """
            },
            "tox.ini": """
            [testenv]
            usedevelop=True
            changedir=tests
            commands=
                pytest --basetemp={envtmpdir} --junitxml=junit-{envname}.xml []
            deps=pytest"""
            + """
            skipsdist={}
        """.format(
                skipsdist
            ),
        },
    )
    result = cmd("-v")
    result.assert_success()
    assert re.match(
        r".*generated\W+xml\W+file.*junit-python\.xml" r".*\W+1\W+passed.*", result.out, re.DOTALL
    )
    assert "sdist-make" not in result.out
    result = cmd("-epython")
    result.assert_success()
    assert "develop-inst-noop" in result.out
    assert re.match(
        r".*\W+1\W+passed.*" r"summary.*" r"python:\W+commands\W+succeeded.*",
        result.out,
        re.DOTALL,
    )

    # see that things work with a different CWD
    with base.dirpath().as_cwd():
        result = cmd("-c", "{}/tox.ini".format(name))
        result.assert_success()
        assert "develop-inst-noop" in result.out
        assert re.match(
            r".*\W+1\W+passed.*" r"summary.*" r"python:\W+commands\W+succeeded.*",
            result.out,
            re.DOTALL,
        )

    # see that tests can also fail and retcode is correct
    testfile = py.path.local("tests").join("test_hello.py")
    assert testfile.check()
    testfile.write("def test_fail(): assert 0")
    result = cmd()
    result.assert_fail()
    assert "develop-inst-noop" in result.out
    assert re.match(
        r".*\W+1\W+failed.*" r"summary.*" r"python:\W+commands\W+failed.*", result.out, re.DOTALL
    )

    # test develop is called if setup.py changes
    setup_py = py.path.local("setup.py")
    setup_py.write(setup_py.read() + " ")
    result = cmd()
    result.assert_fail()
    assert "develop-inst-nodeps" in result.out


def test_warning_emitted(cmd, initproj):
    initproj(
        "spam-0.0.1",
        filedefs={
            "tox.ini": """
        [testenv]
        skipsdist=True
        usedevelop=True
    """,
            "setup.py": """
        from setuptools import setup
        from warnings import warn
        warn("I am a warning")

        setup(name="spam", version="0.0.1")
    """,
        },
    )
    cmd()
    result = cmd()
    assert "develop-inst-noop" in result.out
    assert "I am a warning" in result.err


def test_alwayscopy(initproj, cmd, mocksession):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
            [testenv]
            commands={envpython} --version
            alwayscopy=True
    """
        },
    )
    venv = mocksession.getvenv("python")
    result = cmd("-vv")
    result.assert_success()
    if use_builtin_venv(venv):
        assert "venv --copies" in result.out
    else:
        assert "virtualenv --always-copy" in result.out


def test_alwayscopy_default(initproj, cmd, mocksession):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
            [testenv]
            commands={envpython} --version
    """
        },
    )
    venv = mocksession.getvenv("python")
    result = cmd("-vv")
    result.assert_success()
    if use_builtin_venv(venv):
        assert "venv --copies" not in result.out
    else:
        assert "virtualenv --always-copy" not in result.out


@pytest.mark.skipif("sys.platform == 'win32'", reason="no echo on Windows")
def test_empty_activity_ignored(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
            [testenv]
            list_dependencies_command=echo
            commands={envpython} --version
    """
        },
    )
    result = cmd()
    result.assert_success()
    assert "installed:" not in result.out


@pytest.mark.skipif("sys.platform == 'win32'", reason="no echo on Windows")
def test_empty_activity_shown_verbose(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
            [testenv]
            list_dependencies_command=echo
            commands={envpython} --version
    """
        },
    )
    result = cmd("-v")
    result.assert_success()
    assert "installed:" in result.out


def test_test_piphelp(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
            # content of: tox.ini
            [testenv]
            commands=pip -h
    """
        },
    )
    result = cmd("-vv")
    result.assert_success()


def test_notest(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "tox.ini": """
        # content of: tox.ini
        [testenv:py26]
        basepython=python
    """
        },
    )
    result = cmd("-v", "--notest")
    result.assert_success()
    assert re.match(r".*summary.*" r"py26\W+skipped\W+tests.*", result.out, re.DOTALL)
    result = cmd("-v", "--notest", "-epy26")
    result.assert_success()
    assert re.match(r".*py26\W+reusing.*", result.out, re.DOTALL)


def test_notest_setup_py_error(initproj, cmd):
    initproj(
        "example123",
        filedefs={
            "setup.py": """\
                from setuptools import setup
                setup(name='x', install_requires=['fakefakefakefakefakefake']),
            """,
            "tox.ini": "",
        },
    )
    result = cmd("--notest")
    result.assert_fail()
    assert re.search("ERROR:.*InvocationError", result.out)


def test_PYC(initproj, cmd, monkeypatch):
    initproj("example123", filedefs={"tox.ini": ""})
    monkeypatch.setenv("PYTHONDOWNWRITEBYTECODE", "1")
    result = cmd("-v", "--notest")
    result.assert_success()
    assert "create" in result.out


def test_env_VIRTUALENV_PYTHON(initproj, cmd, monkeypatch):
    initproj("example123", filedefs={"tox.ini": ""})
    monkeypatch.setenv("VIRTUALENV_PYTHON", "/FOO")
    result = cmd("-v", "--notest")
    result.assert_success()
    assert "create" in result.out


def test_envsitepackagesdir(cmd, initproj):
    initproj(
        "pkg512-0.0.5",
        filedefs={
            "tox.ini": """
        [testenv]
        commands=
            python -c "print(r'X:{envsitepackagesdir}')"
    """
        },
    )
    result = cmd()
    result.assert_success()
    assert re.match(r".*\nX:.*tox.*site-packages.*", result.out, re.DOTALL)


def test_envsitepackagesdir_skip_missing_issue280(cmd, initproj):
    initproj(
        "pkg513-0.0.5",
        filedefs={
            "tox.ini": """
        [testenv]
        basepython=/usr/bin/qwelkjqwle
        commands=
            {envsitepackagesdir}
    """
        },
    )
    result = cmd("--skip-missing-interpreters")
    result.assert_success()
    assert re.match(r".*SKIPPED:.*qwelkj.*", result.out, re.DOTALL)


@pytest.mark.parametrize("verbosity", ["", "-v", "-vv"])
def test_verbosity(cmd, initproj, verbosity):
    initproj(
        "pkgX-0.0.5",
        # Note: This is related to https://github.com/tox-dev/tox#935
        # For some reason, the .egg-info/ directory is interacting with the
        # PYTHONPATH on Appveyor, causing the package to *not* be installed
        # since pip already thinks it is. By setting the `src_root`, we can
        # avoid the issue.
        src_root="src",
        filedefs={
            "tox.ini": """
        [testenv]
    """
        },
    )
    result = cmd(verbosity)
    result.assert_success()

    needle = "Successfully installed pkgX-0.0.5"
    if verbosity == "-vv":
        assert any(needle in line for line in result.outlines), result.outlines
    else:
        assert all(needle not in line for line in result.outlines), result.outlines


def test_envtmpdir(initproj, cmd):
    initproj(
        "foo",
        filedefs={
            # This file first checks that envtmpdir is existent and empty. Then it
            # creates an empty file in that directory.  The tox command is run
            # twice below, so this is to test whether the directory is cleared
            # before the second run.
            "check_empty_envtmpdir.py": """if True:
            import os
            from sys import argv
            envtmpdir = argv[1]
            assert os.path.exists(envtmpdir)
            assert os.listdir(envtmpdir) == []
            open(os.path.join(envtmpdir, 'test'), 'w').close()
        """,
            "tox.ini": """
            [testenv]
            commands=python check_empty_envtmpdir.py {envtmpdir}
        """,
        },
    )

    result = cmd()
    result.assert_success()

    result = cmd()
    result.assert_success()


def test_missing_env_fails(initproj, cmd):
    initproj("foo", filedefs={"tox.ini": "[testenv:foo]\ncommands={env:VAR}"})
    result = cmd()
    result.assert_fail()
    assert result.out.endswith(
        "foo: unresolvable substitution(s): 'VAR'."
        " Environment variables are missing or defined recursively.\n"
    )


def test_tox_console_script(initproj):
    initproj("help", filedefs={"tox.ini": ""})
    result = subprocess.check_call(["tox", "--help"])
    assert result == 0


def test_tox_quickstart_script(initproj):
    initproj("help", filedefs={"tox.ini": ""})
    result = subprocess.check_call(["tox-quickstart", "--help"])
    assert result == 0


def test_tox_cmdline_no_args(monkeypatch, initproj):
    initproj("help", filedefs={"tox.ini": ""})
    monkeypatch.setattr(sys, "argv", ["caller_script", "--help"])
    with pytest.raises(SystemExit):
        tox.cmdline()


def test_tox_cmdline_args(initproj):
    initproj("help", filedefs={"tox.ini": ""})
    with pytest.raises(SystemExit):
        tox.cmdline(["caller_script", "--help"])


@pytest.mark.parametrize("exit_code", [0, 6])
def test_exit_code(initproj, cmd, exit_code, mocker):
    """ Check for correct InvocationError, with exit code,
        except for zero exit code """
    import tox.exception

    mocker.spy(tox.exception, "exit_code_str")
    tox_ini_content = "[testenv:foo]\ncommands=python -c 'import sys; sys.exit({:d})'".format(
        exit_code
    )
    initproj("foo", filedefs={"tox.ini": tox_ini_content})
    cmd()
    if exit_code:
        # need mocker.spy above
        assert tox.exception.exit_code_str.call_count == 1
        (args, kwargs) = tox.exception.exit_code_str.call_args
        assert kwargs == {}
        (call_error_name, call_command, call_exit_code) = args
        assert call_error_name == "InvocationError"
        # quotes are removed in result.out
        # do not include "python" as it is changed to python.EXE by appveyor
        expected_command_arg = " -c 'import sys; sys.exit({:d})'".format(exit_code)
        assert expected_command_arg in call_command
        assert call_exit_code == exit_code
    else:
        # need mocker.spy above
        assert tox.exception.exit_code_str.call_count == 0
