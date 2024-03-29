# temBoard Agent functional tests

This directory contains functional tests for each plugin. To run these tests you'll need:
  * PostgreSQL binaries of the version you want the agent will be connected to when running the tests
  * `pytest`

Those tests are intented to be run in CircleCI.

## `pytest` installation

``` console
# pip install pytest
```

## Run the tests

There are 3 environment variables that can be used to change the global behaviour (default values are set into `test/configtest.py`):
  * `TBD_PGVERSION`: Major PostgreSQL version
  * `TBD_PGPORT`: PostgreSQL TCP listen port
  * `TBD_WORKPATH`: Work path where temp data are stored

To run the whole test suite:
``` console
$ tests/func/run_tests_docker.sh  # --pdb -x pytest args
```

## Run the tests using docker

You can also run the tests via docker for several versions of Postgres.

Choose CentOS version between `centos6` and `centos7` with envvar `TAG`.
Defaults to `centos7`.

Choose Postgres version from `9.4` to `10` with envvar `POSTGRES_VERSION`.
Defaults to `10`.

In case of failure, the container wait for you to enter and debug with `make
shell`

``` console
$ TAG=centos7 POSTGRES_VERSION=9.5 make run
…
test_1  | + tail -f /dev/null

$ make shell
[root@3e8037d18e8b /workspace]# ./tests/func/run_tests_docker.sh -x --pdb
…
```
