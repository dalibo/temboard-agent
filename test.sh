#!/bin/bash -eux

top_srcdir=$(readlink -m $0/..)
cd $top_srcdir
# Ensure that setup.py exists (we are correctly located)
test -f setup.py

# Search for the proper RPM package
test -f /tmp/dist/artifact-1
