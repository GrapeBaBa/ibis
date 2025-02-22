from __future__ import annotations

from collections import OrderedDict
from typing import Any, Mapping

import pandas as pd
from clickhouse_driver.client import Client as _DriverClient

import ibis
import ibis.config
import ibis.expr.schema as sch
from ibis.backends.base.sql import BaseSQLBackend
from ibis.config import options

from .client import ClickhouseDataType, ClickhouseTable, fully_qualified_re
from .compiler import ClickhouseCompiler

_default_compression: str | bool

try:
    import lz4  # noqa: F401

    _default_compression = 'lz4'
except ImportError:
    _default_compression = False


class Backend(BaseSQLBackend):
    name = 'clickhouse'
    table_expr_class = ClickhouseTable
    compiler = ClickhouseCompiler

    def do_connect(
        self,
        host: str = 'localhost',
        port: int = 9000,
        database: str = 'default',
        user: str = 'default',
        password: str = '',
        client_name: str = 'ibis',
        compression: str | bool = _default_compression,
    ):
        """Create a ClickHouse client for use with Ibis.

        Parameters
        ----------
        host
            Host name of the clickhouse server
        port
            Clickhouse server's  port
        database
            Default database when executing queries
        user
            User to authenticate with
        password
            Password to authenticate with
        client_name
            This will appear in clickhouse server logs
        compression
            Weather or not to use compression.
            Default is lz4 if installed else False.
            Possible choices: lz4, lz4hc, quicklz, zstd, True, False
            True is equivalent to 'lz4'.

        Examples
        --------
        >>> import ibis
        >>> import os
        >>> clickhouse_host = os.environ.get('IBIS_TEST_CLICKHOUSE_HOST',
        ...                                  'localhost')
        >>> clickhouse_port = int(os.environ.get('IBIS_TEST_CLICKHOUSE_PORT',
        ...                                      9000))
        >>> client = ibis.clickhouse.connect(
        ...     host=clickhouse_host,
        ...     port=clickhouse_port
        ... )
        >>> client  # doctest: +ELLIPSIS
        <ibis.clickhouse.client.ClickhouseClient object at 0x...>

        Returns
        -------
        ClickhouseClient
            A clickhouse client
        """
        self.con = _DriverClient(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            client_name=client_name,
            compression=compression,
        )

    def register_options(self):
        ibis.config.register_option(
            'temp_db',
            '__ibis_tmp',
            'Database to use for temporary tables, views. functions, etc.',
        )

    @property
    def version(self) -> str:
        self.con.connection.force_connect()
        try:
            info = self.con.connection.server_info
        except Exception:
            self.con.connection.disconnect()
            raise

        return f'{info.version_major}.{info.version_minor}.{info.revision}'

    @property
    def current_database(self):
        return self.con.connection.database

    def list_databases(self, like=None):
        data, schema = self.raw_sql('SELECT name FROM system.databases')
        databases = list(data[0])
        return self._filter_with_like(databases, like)

    def list_tables(self, like=None, database=None):
        data, schema = self.raw_sql('SHOW TABLES')
        databases = list(data[0])
        return self._filter_with_like(databases, like)

    def raw_sql(
        self,
        query: str,
        external_tables: Mapping[str, pd.DataFrame] | None = None,
    ) -> Any:
        """Execute a SQL string `query` against the database.

        Parameters
        ----------
        query
            Raw SQL string
        external_tables
            Mapping of table name to pandas DataFrames providing
            external datasources for the query

        Returns
        -------
        Any
            The resutls of executing the query
        """
        external_tables_list = []
        if external_tables is None:
            external_tables = {}
        for name, df in external_tables.items():
            if not isinstance(df, pd.DataFrame):
                raise TypeError(
                    'External table is not an instance of pandas ' 'dataframe'
                )
            schema = sch.infer(df)
            external_tables_list.append(
                {
                    'name': name,
                    'data': df.to_dict('records'),
                    'structure': list(
                        zip(
                            schema.names,
                            [
                                str(ClickhouseDataType.from_ibis(t))
                                for t in schema.types
                            ],
                        )
                    ),
                }
            )

        ibis.util.log(query)
        return self.con.execute(
            query,
            columnar=True,
            with_column_types=True,
            external_tables=external_tables_list,
        )

    def fetch_from_cursor(self, cursor, schema):
        data, columns = cursor
        if not len(data):
            # handle empty resultset
            return pd.DataFrame([], columns=schema.names)

        df = pd.DataFrame.from_dict(OrderedDict(zip(schema.names, data)))
        return schema.apply_to(df)

    def close(self):
        """Close Clickhouse connection and drop any temporary objects"""
        self.con.disconnect()

    def _fully_qualified_name(self, name, database):
        if fully_qualified_re.search(name):
            return name

        database = database or self.current_database
        return f'{database}.`{name}`'

    def get_schema(
        self,
        table_name: str,
        database: str | None = None,
    ) -> sch.Schema:
        """Return a Schema object for the indicated table and database.

        Parameters
        ----------
        table_name
            May be fully qualified
        database
            Database name

        Returns
        -------
        sch.Schema
            Ibis schema
        """
        qualified_name = self._fully_qualified_name(table_name, database)
        query = f'DESC {qualified_name}'
        data, columns = self.raw_sql(query)
        return sch.schema(
            data[0], list(map(ClickhouseDataType.parse, data[1]))
        )

    def set_options(self, options):
        self.con.set_options(options)

    def reset_options(self):
        # Must nuke all cursors
        raise NotImplementedError

    def _ensure_temp_db_exists(self):
        name = (options.clickhouse.temp_db,)
        if name not in self.list_databases():
            self.create_database(name, force=True)

    def _get_schema_using_query(self, query, **kwargs):
        data, columns = self.raw_sql(query, **kwargs)
        colnames, typenames = zip(*columns)
        coltypes = list(map(ClickhouseDataType.parse, typenames))
        return sch.schema(colnames, coltypes)

    def _table_command(self, cmd, name, database=None):
        qualified_name = self._fully_qualified_name(name, database)
        return f'{cmd} {qualified_name}'
