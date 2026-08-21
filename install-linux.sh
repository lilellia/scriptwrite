#!/usr/bin/env bash

PYTHON="./.venv/bin/python3"

eprintf() {
  local format="$1"
  shift

  # shellcheck disable=SC2059
  printf "$format" "$@" >&2
}

fatal() {
  local message="$1"
  local code="${2:-1}"
  eprintf "$message"
  exit "$code"
}

verify-python() {
  if /usr/bin/test -f "$PYTHON"; then
    return 0
  else
    fatal "Python undetected at ($PYTHON). Must install a virtual environment.\n"
  fi
}


ensure-python-dependencies() {
  local code
  code="$($PYTHON -c "import nuitka, PySide6" 1>/dev/null 2>/dev/null ; echo $?)"
  if /usr/bin/test "$code" -eq 0; then
    return 0
  else
    eprintf "Python (at $PYTHON) seems to be missing dependencies. Installing...\n"
    $PYTHON -m ensurepip 2>/dev/null  # `uv init` doesn't provide a local pip, which... sort of makes sense?
    $PYTHON -m pip install nuitka pyside6
  fi
}

build() {
  local mode="${1:-standalone}"

  if /usr/bin/test "$mode" != "standalone" -a "$mode" != "onefile"; then
    fatal "Invalid build mode $mode. Must be either 'standalone' or 'onefile'.\n"
  fi

  $PYTHON -m nuitka \
    "--$mode" \
    --enable-plugin=pyside6 \
    --assume-yes-for-downloads \
    --output-dir=dist \
    --include-data-files=./scriptwrite/widgets/color_names.toml=scriptwrite/widgets/color_names.toml \
    --include-data-dir=./scriptwrite/assets=scriptwrite/assets \
    --include-data-dir=./scriptwrite/themes=scriptwrite/themes \
    scriptwrite.py
}

get-xdg-dir() {
  # get-xdg-dir DATA "$HOME/.local/share"
  local var="$1"
  local default="$2"

  local value
  value="$(printenv "XDG_${var}_HOME")"

  if /usr/bin/test -z "$value"; then
    # $XDG_XXX_HOME isn't set, so use the default
    echo "$default"
  elif /usr/bin/test "$(grep -qE "^/" <<<"$value" ; echo $?)" -eq 0; then
    # it is set and points to an absolute path, so use that
    echo "$value"
  else
    # it is set but points to a relative path, so use the default
    eprintf "\$XDG_${var}_HOME is set to a relative path ($value), which is invalid.\n"
    echo "$default"
  fi
}

get-install-dir() {
  local base
  base="$(get-xdg-dir "DATA" "$HOME/.local/share")"

  echo "$base/scriptwrite"
}

get-bin-dir() {
  echo "$HOME/.local/bin"
}


main() {
  # local mode="${1:-standalone}"

  verify-python
  ensure-python-dependencies

  build standalone

  # move to ~/.local/share/scriptwrite (or sim.)
  local install_dir
  install_dir="$(get-install-dir)"
  rm -rf "$install_dir"
  mv ./dist/scriptwrite.dist "$install_dir"
  eprintf 'Installed into %s\n' "$install_dir"

  # put symlink in path
  local bin_dir
  bin_dir="$(get-bin-dir)"
  ln -sf "$install_dir/scriptwrite.bin" "$bin_dir/scriptwrite"
  eprintf 'Created symlink at %s\n' "$bin_dir/scriptwrite"
}

main "$@"
