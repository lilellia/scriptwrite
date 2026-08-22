#!/bin/sh

usage() {
    echo "INSTALL_PREFIX=... $0" >&2
    # shellcheck disable=SC2016
    # ("Expressions don't expand in single quotes, use double quotes for that")
    echo 'INSTALL_PREFIX defines where the app will be installed. By default: INSTALL_PREFIX=$XDG_DATA_HOME if set and valid, else its usual value of $HOME/.local/share)' >&2
}

# Make sure usage is correct
if /usr/bin/test "$#" -eq 0; then
    true
elif /usr/bin/test "$#" -eq 1 && /usr/bin/test "$1" = '-h'; then
    usage
    exit 0
elif /usr/bin/test "$#" -eq 1 && /usr/bin/test "$1" = '--help'; then
    usage
    exit 0
else
    echo "Invalid arguments: $*" >&2
    usage
    exit 1
fi

# Figure out what the install prefix should be
if /usr/bin/test -z "$INSTALL_PREFIX"; then
    # user didn't give us a prefix, so try to use $XDG_DATA_HOME
    if /usr/bin/test -n "$XDG_DATA_HOME" -a "$(echo "$XDG_DATA_HOME" | grep -qE '^/' ; echo "$?")" -eq 0; then
        # $XDG_DATA_HOME is set and valid, so we'll use that
        echo "Using $XDG_DATA_HOME as install location" >&2
        INSTALL_PREFIX="$XDG_DATA_HOME"
    else
        echo "\$XDG_DATA_HOME ($XDG_DATA_HOME) is either unset or a relative path (which is invalid). Using $HOME/.local/share as install location instead" >&2
        INSTALL_PREFIX="$HOME/.local/share"
    fi
else
    echo "Using $INSTALL_PREFIX as install location" >&2
fi

# Make sure we have Python installed correctly

is_sufficient_python() {
    # ex: is_sufficient_python /usr/bin/python3
    # prints 0 if sufficient, 1 otherwise
    echo "$("$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' ; echo "$?")"
}

is_python_311() {
    # ex: is_python_311 /usr/bin/python3
    # prints 0 if 3.11, 1 otherwise
    "$1" -c 'import sys; print(0 if sys.version_info.major == 3 and sys.version_info.minor == 11 else 1)'
}

# first look for virtualenv Python
if /usr/bin/test -f './.venv/bin/python3'; then
    PYTHON='./.venv/bin/python3'
    if /usr/bin/test "$(is_sufficient_python "$PYTHON")" -eq 1; then
        echo "local virtualenv Python ($PYTHON) is version $($PYTHON --version), must be 3.11+" >&2
        exit 1
    fi
else
    # try to make a virtualenv
    echo 'local virtualenv Python executable not found'
    MADE_VENV=0
    for py in python3 python python3.11 python3.12 python3.13 python3.14; do
        if /usr/bin/test "$(which "$py" ; echo "$?")" -eq 1; then
            continue
        fi

        if /usr/bin/test "$(is_sufficient_python "$py")" -eq 0; then
            echo "found $py ($(command -v $py)): $($py --version)). Creating virtualenv" >&2
            $py -m venv .venv
            PYTHON='./.venv/bin/python3'
            MADE_VENV=1
            break
        fi
    done

    if /usr/bin/test "$MADE_VENV" -eq 0; then
        echo 'failed to make virtualenv' >&2
        exit 1
    fi
fi

# make sure that the virtualenv has what it needs
if /usr/bin/test "$($PYTHON -c 'import PySide6, nuitka' ; echo "$?")" -eq 1; then
    echo 'Python found to be missing dependencies. Installing...'
    $PYTHON -m ensurepip  # uv doesn't automatically include pip for some reason, but... pip is the standard, so that's what we're going to use
    $PYTHON -m pip install --upgrade pip
    $PYTHON -m pip install nuitka pyside6

    if /usr/bin/test "$(is_python_311 "$PYTHON")" -eq 0; then
        # 3.11, specifically, also requires typing-extensions
        $PYTHON -m pip install typing-extensions
    fi
fi

# go ahead and actually build the app now
$PYTHON -m nuitka \
  "--standalone" \
  --enable-plugin=pyside6 \
  --assume-yes-for-downloads \
  --output-dir=dist \
  --include-data-files=./scriptwrite/widgets/color_names.toml=scriptwrite/widgets/color_names.toml \
  --include-data-dir=./scriptwrite/assets=scriptwrite/assets \
  --include-data-dir=./scriptwrite/themes=scriptwrite/themes \
  scriptwrite.py

# now move the build artefact
rm -rf "$INSTALL_PREFIX/scriptwrite"
mv './dist/scriptwrite.dist' "$INSTALL_PREFIX/scriptwrite"
echo "Installed files to $INSTALL_PREFIX/scriptwrite" >&2

# create symlink to binary
SYMLINK_LOCATION="$HOME/.local/bin/scriptwrite"
ln -sf "$INSTALL_PREFIX/scriptwrite/scriptwrite.bin" "$SYMLINK_LOCATION"
chmod +x "$SYMLINK_LOCATION"
echo "Created symlink at $SYMLINK_LOCATION" >&2

# write desktop file
DESKTOP_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/applications/scriptwrite.desktop"
rm -f "$DESKTOP_FILE"
printf "[Desktop Entry]\nType=Application\nName=%s\nComment=%s\nPath=%s\nExec=%s\nTerminal=%s\nIcon=%s" \
    'scriptwrite' \
    'ASMR RP scriptwriting application' \
    "$INSTALL_PREFIX/scriptwrite" \
    'scriptwrite %f' \
    'false' \
    "$INSTALL_PREFIX/scriptwrite/scriptwrite/assets/icon.png" \
    >> "$DESKTOP_FILE"
echo "Wrote $DESKTOP_FILE"
