import os
import subprocess

import tox


def real_python3(python, version_dict):
    """
    Determine the path of the real python executable, which is then used for
    venv creation. This is necessary, because an active virtualenv environment
    will cause venv creation to malfunction. By getting the path of the real
    executable, this issue is bypassed.

    The provided `python` path may be either:
    - A real python executable
    - A virtual python executable (with venv)
    - A virtual python executable (with virtualenv)

    If the virtual environment was created with virtualenv, the `sys` module
    will have a `real_prefix` attribute, which points to the directory where
    the real python files are installed.

    If `real_prefix` is not present, the environment was not created with
    virtualenv, and the python executable is safe to use.

    The `version_dict` is used for attempting to derive the real executable
    path. This is necessary when the name of the virtual python executable
    does not exist in the Python installation's directory. For example, if
    the `basepython` is explicitly set to `python`, tox will use this name
    instead of attempting `pythonX.Y`. In many cases, Python 3 installations
    do not contain an executable named `python`, so we attempt to derive this
    from the version info. e.g., `python3.6.5`, `python3.6`, then `python3`.
    """
    args = [python, '-c', 'import sys; print(sys.real_prefix)']

    # get python prefix
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT)
        prefix = output.decode('UTF-8').strip()
    except subprocess.CalledProcessError:
        # process fails, implies *not* in active virtualenv
        return python

    # determine absolute binary path
    if os.name == 'nt':  # pragma: no cover
        paths = [os.path.join(prefix, os.path.basename(python))]
    else:
        paths = [os.path.join(prefix, 'bin', python) for python in [
            os.path.basename(python),
            'python%(major)d.%(minor)d.%(micro)d' % version_dict,
            'python%(major)d.%(minor)d' % version_dict,
            'python%(major)d' % version_dict,
            'python',
        ]]

    for path in paths:
        if os.path.isfile(path):
            break
    else:
        path = None

    # the executable path must exist
    assert path, '\n- '.join(['Could not find interpreter. Attempted:'] + paths)
    v1 = subprocess.check_output([python, '--version'])
    v2 = subprocess.check_output([path, '--version'])
    assert v1 == v2, 'Expected versions to match (%s != %s).' % (v1, v2)

    return path


def use_builtin_venv(venv):
    """
    Determine if the builtin venv module should be used to create the testenv's
    virtual environment. The venv module was added in python 3.3, although some
    options are not supported until 3.4 and later.
    """
    version = venv.envconfig.python_info.version_info
    return version is not None and version >= (3, 3)


@tox.hookimpl
def tox_testenv_create(venv, action):
    # Bypass hook when venv is not available for the target python version
    if not use_builtin_venv(venv):
        return

    v = venv.envconfig.python_info.version_info
    version_dict = {'major': v[0], 'minor': v[1], 'micro': v[2]}

    config_interpreter = str(venv.getsupportedinterpreter())
    real_executable = real_python3(config_interpreter, version_dict)

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
