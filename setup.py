#!/usr/bin/env python3
import ast
import os
import re

from setuptools import setup


here = os.path.dirname(__file__)
with open(os.path.join(here, "README.rst")) as f:
    long_description = f.read()

metadata = {}
with open(os.path.join(here, "qr2text.py")) as f:
    rx = re.compile("(__version__|__author__|__url__|__licence__) = (.*)")
    for line in f:
        m = rx.match(line)
        if m:
            metadata[m.group(1)] = ast.literal_eval(m.group(2))
version = metadata["__version__"]

setup(
    name="qr2text",
    version=version,
    author="Marius Gedminas",
    author_email="marius@gedmin.as",
    url="https://github.com/mgedmin/qr2text",
    description="Convert PyQRCode generated SVG to ASCII art",
    long_description=long_description,
    long_description_content_type='text/x-rst',
    keywords="qr svg ascii art",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    license="GPL",
    python_requires=">=3.7",

    py_modules=["qr2text"],
    zip_safe=False,
    install_requires=[
        'pyqrcode',
        'pyzbar',
    ],
    extras_require={
        'test': [
        ],
    },
    entry_points={
        "console_scripts": [
            "qr2text = qr2text:main",
        ],
    },
)
