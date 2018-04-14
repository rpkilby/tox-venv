import os
import platform
import subprocess

import pluggy

hookimpl = pluggy.HookimplMarker("tox")


def real_python3(python):
    """
    Determine the path of the real python executable, which is then used for
    venv creation. This is necessary, because an active virtualenv environment
    will cause venv creation to malfunction. By getting the path of the real
    executable, this issue is bypassed.

    The provided `python` path may be either:
    - A real python executable
    - A virtualized python executable (with venv)
    - A virtualized python executable (with virtualenv)

    If the virtual environment was created with virtualenv, the `sys` module
    will have a `real_prefix` attribute, which points to the directory where
    the real python files are installed.

    If `real_prefix` is not present, the environment was not created with
    virtualenv, and the python executable is safe to use.
    """
    args = [str(python), '-c', 'import sys; print(sys.real_prefix)']

    # get python prefix
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    prefix = output.decode('UTF-8').strip()

    # determine absolute binary path
    if platform.system() == 'Windows':
        executable = 'python.exe'
    else:
        executable = 'bin/python3'
    path = os.path.join(prefix, executable)

    # process fails, implies *not* in active virtualenv
    if not process.returncode == 0:
        return python

    # the executable path must exist
    assert os.path.isfile(path), "Expected '%s' to exist." % path
    return path


def use_builtin_venv(venv):
    """
    Determine if the builtin venv module should be used to create the testenv's
    virtual environment. The venv module was added in python 3.3, although some
    options are not supported until 3.4 and later.
    """
    version = venv.envconfig.python_info.version_info
    return version is not None and version >= (3, 3)


@hookimpl
def tox_testenv_create(venv, action):
    # Bypass hook when venv is not available for the target python version
    if not use_builtin_venv(venv):
        return

    config_interpreter = venv.getsupportedinterpreter()
    real_executable = real_python3(config_interpreter)

    args = [real_executable, '-m', 'venv']
    if venv.envconfig.sitepackages:
        args.append('--system-site-packages')
    if venv.envconfig.alwayscopy:
        args.append('--copies')

    venv.session.make_emptydir(venv.path)
    basepath = venv.path.dirpath()
    basepath.ensure(dir=1)
    args.append(venv.path.basename)
    venv._pcall(args, venv=False, action=action, cwd=basepath)
    # Return non-None to indicate the plugin has completed
    return True
