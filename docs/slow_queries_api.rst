.. _slow_queries_api:

SlowQueries API
===============

.. http:get:: /slow_queries

    Get list of slow queries

    :query key: Agent's key for authentication (optional)
    :reqheader X-Session: Session ID
    :status 200: no error
    :status 401: invalid session
    :status 500: internal error
    :status 406: header ``X-Session`` is malformed.


**Example request**:

.. sourcecode:: http

    GET /slow_queries HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/4.0+master Python/3.7.2
    Date: Fri, 24 May 2019 12:42:52 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    [
        {
            "datetime": "2019-05-24 08:47:25.032429+00",
            "duration": 1001.16,
            "username": "postgres",
            "appname": "psql",
            "dbname": "postgres",
            "temp_blks_written": 0,
            "hitratio": 100.0,
            "ntuples": 1,
            "query": "select pg_sleep(1);",
            "plan": "{\n  \"Plan\": {\n    \"Node Type\": \"Result\",\n    \"Parallel Aware\": false,\n    \"Startup Cost\": 0.00,\n    \"Total Cost\": 0.01,\n    \"Plan Rows\": 1,\n    \"Plan Width\": 4,\n    \"Actual Startup Time\": 1001.144,\n    \"Actual Total Time\": 1001.145,\n    \"Actual Rows\": 1,\n    \"Actual Loops\": 1,\n    \"Output\": [\"pg_sleep('1'::double precision)\"],\n    \"Shared Hit Blocks\": 0,\n    \"Shared Read Blocks\": 0,\n    \"Shared Dirtied Blocks\": 0,\n    \"Shared Written Blocks\": 0,\n    \"Local Hit Blocks\": 0,\n    \"Local Read Blocks\": 0,\n    \"Local Dirtied Blocks\": 0,\n    \"Local Written Blocks\": 0,\n    \"Temp Read Blocks\": 0,\n    \"Temp Written Blocks\": 0\n  }\n}"
        },
    ]

.. http:get:: /slow_queries/reset

    Reset the slow queries log file

    :query key: Agent's key for authentication (optional)
    :reqheader X-Session: Session ID
    :status 200: no error
    :status 401: invalid session
    :status 500: internal error
    :status 406: header ``X-Session`` is malformed.


**Example request**:

.. sourcecode:: http

    GET /slow_queries/reset HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e


**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/4.0+master Python/3.7.2
    Date: Fri, 24 May 2019 12:42:52 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {"ok": "done"}


.. http:get:: /slow_queries/settings

    Get the ``pg_track_slow_queries`` extension settings values.

    :reqheader X-Session: Session ID
    :status 200: no error
    :status 401: invalid session
    :status 500: internal error
    :status 406: header ``X-Session`` or setting item is malformed.


**Example request**:

.. sourcecode:: http

    GET /slow_queries/reset HTTP/1.1
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e

**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.8
    Date: Fri, 24 May 2019 12:42:52 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    [
        {
            "category": "Customized Options",
            "rows": [
                {
                    "name": "pg_track_slow_queries.compression",
                    "setting": "on",
                    "setting_raw": "on",
                    "unit": null,
                    "vartype": "bool",
                    "min_val": null,
                    "max_val": null,
                    "boot_val": "on",
                    "reset_val": "on",
                    "enumvals": null,
                    "context": "superuser",
                    "desc": "Enables data compression. ",
                    "pending_restart": false
                },
                {
                    "...": "..."
                }
            ]
        }
    ]

.. http:post:: /slow_queries/settings

    Update the ``pg_track_slow_queries`` extension settings values. This API issues ``ALTER SYSTEM`` SQL statements.

    :reqheader X-Session: Session ID
    :status 200: no error
    :status 401: invalid session
    :status 500: internal error
    :status 406: header ``X-Session`` or setting item is malformed.
    :status 400: invalid JSON format.


**Example request**:

.. sourcecode:: http

    POST /slowqueries/settings HTTP/1.1
    Content-Type: application/json
    X-Session: 3b28ed94743e3ada57b217bbf9f36c6d1eb45e669a1ab693e8ca7ac3bd070b9e

    {
        "settings":
        [
            {
                "name": "pg_track_slow_queries.log_min_duration",
                "setting": "4000"
            }
        ]
    }

**Example response**:

.. sourcecode:: http

    HTTP/1.0 200 OK
    Server: temboard-agent/0.0.1 Python/2.7.8
    Date: Fri, 24 May 2019 12:42:52 GMT
    Access-Control-Allow-Origin: *
    Content-type: application/json

    {
        "settings": [
            {
                "name": "pg_track_slow_queries.log_min_duration",
                "setting": "4000",
                "previous_setting": "1s",
                "restart": false
            }
        ]
    }
