#!/usr/bin/env python3
from setuptools import setup

setup(
    name="rivalcfg-gui",
    version="1.5.1",
    description="GTK3 GUI configuration tool for SteelSeries mice",
    long_description="A Linux desktop application for configuring SteelSeries mouse settings including DPI, polling rate, RGB lighting, and button mappings through a modern GTK3 interface.",
    author="MrGodzilla38",
    author_email="oyunustasigodzilla@gmail.com",
    url="https://github.com/MrGodzilla38/rivalcfg-gui",
    license="GPL-3.0-or-later",
    py_modules=["rivalcfg_gui"],
    python_requires=">=3.10",
    install_requires=[
        "evdev>=1.7.1",
        "pynput>=1.7.7",
        "python-xlib>=0.33",
        "rivalcfg>=4.17.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX :: Linux",
        "Topic :: System :: Hardware :: Hardware Drivers",
    ],
)
