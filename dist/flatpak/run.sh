#!/bin/sh
export RIVALCFG_GUI_LOCALE_DIR="/app/share/locale"
export PYTHONPATH="/app/lib/rivalcfg-gui:${PYTHONPATH}"
exec python3 /app/lib/rivalcfg-gui/rivalcfg_gui.py "$@"
