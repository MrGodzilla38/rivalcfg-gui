# RivalCFG GUI

A Linux desktop configuration tool for the SteelSeries Rival 3 mouse.

## What It Does

This application lets you configure your SteelSeries Rival 3 using the `rivalcfg` command-line tool:

- **DPI:** Adjust 5 preset values via slider (200–8500, in 100-step increments)
- **Polling Rate:** Choose 125 / 250 / 500 / 1000 Hz
- **RGB Lighting:** Set logo and wheel colors, and select light effects (steady, breath, breath-slow, rainbow-shift, disco)
- **Reset All Settings:** Restore mouse factory defaults

## Supported Devices

- SteelSeries Rival 3

> Note: Other SteelSeries devices may be supported by `rivalcfg`, but this GUI is currently tested only against the Rival 3 command set.

## Installation

### 1. Install dependencies

```bash
# rivalcfg (via pip)
pip install rivalcfg

# python-gobject (GTK3 bindings)
# Arch Linux / Manjaro:
pacman -S python-gobject

# Debian / Ubuntu:
# sudo apt install python3-gi
```

### 2. Run the application

```bash
python rivalcfg_gui.py
```

If no mouse is connected or `rivalcfg` is not found, the application will exit immediately with an error message.

## Requirements

- Python 3
- GTK3
- python-gobject (`gi`)
- `rivalcfg` command-line tool
