#!/bin/bash
set -e
set -u

python -m pip install --upgrade --no-cache-dir pip 'setuptools<58.3.0'
python -m pip install --upgrade --no-cache-dir mock==1.0.1 pillow==5.4.1 'alabaster>=0.7,<0.8,!=0.7.5' commonmark==0.8.1 recommonmark==0.5.0 'sphinx<2' 'sphinx-rtd-theme<0.5' 'readthedocs-sphinx-ext<2.2'
python -m pip install --upgrade --upgrade-strategy eager --no-cache-dir '.[docs]'
