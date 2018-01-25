import os
import subprocess

from tox.config import hookimpl


def real_python3(python):
    """
    use real_prefix to determine if we're running inside a virtualenv,
    and if so, use it as the base path to determine the real python
    executable path.
    """
    args = [str(python), '-c', 'import sys; print(sys.real_prefix)']

    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, _ = process.communicate()
    output = output.decode('UTF-8').strip()
    path = os.path.join(output, 'bin/python3')

    # process fails, implies *not* in active virtualenv
    if not process.returncode == 0:
        return python

    # the executable path must exist
    assert os.path.isfile(path)
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
