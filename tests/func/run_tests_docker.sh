#!/bin/bash -eux

#
# Script to run tests on CentOS
#

top_srcdir=$(readlink -m $0/../../..)
cd $top_srcdir
# Ensure that setup.py exists (we are correctly located)
test -f setup.py

teardown() {
    exit_code=$?

    # If not on CI and we are docker entrypoint (PID 1), let's wait forever on
    # error. This allows user to enter the container and debug after a build
    # failure.
    if [ -z "${CI-}" -a $PPID = 1 -a $exit_code -gt 0 ] ; then
        tail -f /dev/null
    fi
}

trap teardown EXIT INT TERM

install_rpm=${TBD_INSTALL_RPM:-0}
export PYTHON=${PYTHON-python2}

# For circle-ci tests we want to install using RPM
# When launched locally we install via pip
if (( install_rpm == 1 ))
then
    # Search for the proper RPM package
    rpmdist=$(rpm --eval '%dist')
    rpm=$(readlink -e dist/rpm/noarch/temboard-agent-*${rpmdist}*.noarch.rpm)
    # Disable pgdg to use base pyscopg2 2.5 from Red Hat.
    yum -d1 "--disablerepo=pgdg*"  install -y $rpm
    rpm --query --queryformat= temboard-agent
else
    $PYTHON -m pip install -e .
    if type -p yum &>/dev/null && $PYTHON --version | grep -F 'Python 2' ; then
	    yum -q -y "--disablerepo=pgdg*" install python-psycopg2
    else
	    $PYTHON -m pip install psycopg2-binary
    fi
fi

$PYTHON -m pip install pytest pytest-mock

for locale in C.UTF-8 en_US.utf8 ; do
	if locale -a | grep -q "$locale" ; then
		export LC_ALL="$locale"
		break
	fi
done

export TBD_PGBIN=$(readlink -e /usr/pgsql-${TBD_PGVERSION}/bin /usr/lib/postgresql/${TBD_PGVERSION}/bin)
export TBD_WORKPATH="/tmp"

# Remove any .pyc file to avoid errors with pytest and cache
find . -name \*.pyc -delete
rm -rf /tmp/tests_temboard
sudo -Eu testuser \
	/usr/bin/env PATH="$PATH" \
	"$PYTHON" -m pytest \
	-vv --capture=no -p no:cacheprovider \
	tests/func/ \
	"$@"
