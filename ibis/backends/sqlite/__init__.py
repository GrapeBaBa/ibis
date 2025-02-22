# Copyright 2015 Cloudera Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy

if TYPE_CHECKING:
    import ibis.expr.types as ir

from ibis.backends.base import Database
from ibis.backends.base.sql.alchemy import BaseAlchemyBackend

from . import udf
from .compiler import SQLiteCompiler


class Backend(BaseAlchemyBackend):
    name = 'sqlite'
    # TODO check if there is a reason to not use the parent AlchemyDatabase, or
    # if there is technical debt that makes this required
    database_class = Database
    compiler = SQLiteCompiler

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._con: sqlalchemy.engine.Engine = None
        self._meta: sqlalchemy.MetaData = None

    def __getstate__(self) -> dict:
        r = super().__getstate__()
        r.update(
            dict(
                compiler=self.compiler,
                database_name=self.database_name,
                _con=None,  # clear connection on copy()
                _meta=None,
            )
        )
        return r

    @property
    def con(self) -> sqlalchemy.engine.Engine:
        if self._con is None:
            self.reconnect()
        return self._con

    @con.setter
    def con(self, v: sqlalchemy.engine.Engine | None):
        self._con = v

    @property
    def meta(self) -> sqlalchemy.MetaData:
        if self._meta is None:
            self.reconnect()
        return self._meta

    @meta.setter
    def meta(self, v: sqlalchemy.MetaData):
        self._meta = v

    def do_connect(
        self,
        path: str | Path | None = None,
        create: bool = False,
    ) -> None:
        """Create an Ibis client connected to a SQLite database.

        Multiple database files can be created using the `attach()` method

        Parameters
        ----------
        path
            File path to the SQLite database file. If None, creates an
            in-memory transient database and you can use attach() to add more
            files
        create
            If the database file does not exist, create it
        """
        self.database_name = "base"

        super().do_connect(sqlalchemy.create_engine("sqlite://"))
        if path is not None:
            self.attach(self.database_name, path, create=create)

        udf.register_all(self.con)

        self._meta = sqlalchemy.MetaData(bind=self.con)

    def list_tables(self, like=None, database=None):
        if database is None:
            database = self.current_database
        return super().list_tables(like, database=database)

    def attach(
        self,
        name: str,
        path: str | Path,
        create: bool = False,
    ) -> None:
        """Connect another SQLite database file to the current connection.

        Parameters
        ----------
        name
            Database name within SQLite
        path
            Path to sqlite3 database file
        create
            If the database file does not exist, create file if `True`
            otherwise raise an exception
        """
        if not os.path.exists(path) and not create:
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), path
            )

        quoted_name = self.con.dialect.identifier_preparer.quote(name)
        self.raw_sql(
            "ATTACH DATABASE {path!r} AS {name}".format(
                path=path, name=quoted_name
            )
        )
        self.has_attachment = True

    def _get_sqla_table(self, name, schema=None, autoload=True):
        return sqlalchemy.Table(
            name,
            self.meta,
            schema=schema or self.current_database,
            autoload=autoload,
        )

    def table(self, name: str, database: str | None = None) -> ir.TableExpr:
        """Create a table expression from a table in the SQLite database.

        Parameters
        ----------
        name
            Table name
        database
            Name of the attached database that the table is located in.

        Returns
        -------
        TableExpr
            Table expression
        """
        alch_table = self._get_sqla_table(name, schema=database)
        node = self.table_class(alch_table, self)
        return self.table_expr_class(node)

    def _table_from_schema(
        self, name, schema, database: str | None = None
    ) -> sqlalchemy.Table:
        columns = self._columns_from_schema(name, schema)
        return sqlalchemy.Table(name, self.meta, schema=database, *columns)
