import sys


def test_venv(cmd, initproj):
    initproj(
        "pkg-1",
        filedefs={
            "tox.ini": """
                [tox]
                skipsdist=True
                [testenv]
                commands = python -c 'import sys; print(sys.prefix)'
            """
        },
    )
    result = cmd("-v", "-e", "py")
    result.assert_success()

    def index_of(m):
        return next((i for i, l in enumerate(result.outlines) if l.startswith(m)), None)

    module = "venv" if sys.version_info >= (3, 3) else "virtualenv"
    assert any(
        " -m {}".format(module) in l
        for l in result.outlines[
            index_of("py create: ") + 1 : index_of("py installed: ")
        ]
    ), result.output()
