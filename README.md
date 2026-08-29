# scriptwrite

## Installation

### Linux

Qt is more fragmented on Linux and the PyPI bindings for PySide6 don't always play nicely with system plugins. Thus, it may be preferable to build `scriptwrite` against the system Qt directly. If you don't need system plugins or simply prefer to use the PyPI version, you may do so.

In either case, with the virtualenv set up, you can directly run `./.venv/bin/python scriptwrite.py [FILE]`. After installation, `scriptwrite` should be on `$PATH` and thus you can run simply `scriptwrite [FILE]`. If no file is passed, a blank file is loaded.

#### with system Qt:

```bash
$ git clone https://github.com/lilellia/scriptwrite.git
$ cd scriptwrite

# make sure that system Python has PySide6
# on managed systems, you'll instead need to go through apt/dnf/pacman
$ /usr/bin/python3 -m pip install pyside6

$ ./install-linux.sh
```

The installer script will try to set up a virtual environment correctly, but it may be easier to set it up manually in advance because we need to pull system packages and that makes things weird:

```bash
$ uv venv --python /usr/bin/python3 --system-site-packages
$ uv sync
$ ./install-linux.sh
```

#### with nonsystem Qt:

```bash
$ git clone https://github.com/lilellia/scriptwrite.git
$ cd scriptwrite
$ USE_LOCAL_QT=1 ./install-linux.sh
```

Again, the installer script will try to set up a virtualenv, but this time it's weird because we need an extra dependency, so you may also wish to set it up manually:

```bash
$ uv venv
$ uv sync --group pypi-qt
$ USE_LOCAL_QT=1 ./install-linux.sh
```