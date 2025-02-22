from __future__ import annotations

import abc
import re
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping

if TYPE_CHECKING:
    import pandas as pd

from cached_property import cached_property

import ibis
import ibis.expr.operations as ops
import ibis.expr.schema as sch
import ibis.expr.types as ir
from ibis.common.exceptions import TranslationError
from ibis.util import deprecated

__all__ = ('BaseBackend', 'Database')


class Database:
    """Generic Database class."""

    def __init__(self, name: str, client: Any) -> None:
        self.name = name
        self.client = client

    def __repr__(self) -> str:
        """Return type name and the name of the database."""
        return f'{type(self).__name__}({self.name!r})'

    def __dir__(self) -> list[str]:
        """Return the attributes and tables of the database.

        Returns
        -------
        list[str]
            A list of the attributes and tables available in the database.
        """
        attrs = dir(type(self))
        unqualified_tables = [self._unqualify(x) for x in self.tables]
        return sorted(frozenset(attrs + unqualified_tables))

    def __contains__(self, table: str) -> bool:
        """Check if the given table is available in the current database.

        Parameters
        ----------
        table
            Table name

        Returns
        -------
        bool
            True if the given table is available in the current database.
        """
        return table in self.tables

    @property
    def tables(self) -> list[str]:
        """Return a list with all available tables.

        Returns
        -------
        list[str]
            The list of tables in the database
        """
        return self.list_tables()

    def __getitem__(self, table: str) -> ir.TableExpr:
        """Return a TableExpr for the given table name.

        Parameters
        ----------
        table
            Table name

        Returns
        -------
        TableExpr
            Table expression
        """
        return self.table(table)

    def __getattr__(self, table: str) -> ir.TableExpr:
        """Return a TableExpr for the given table name.

        Parameters
        ----------
        table
            Table name

        Returns
        -------
        TableExpr
            Table expression
        """
        return self.table(table)

    def _qualify(self, value):
        return value

    def _unqualify(self, value):
        return value

    def drop(self, force: bool = False) -> None:
        """Drop the database.

        Parameters
        ----------
        force
            If `True`, drop any objects that exist, and do not fail if the
            database does not exist.
        """
        self.client.drop_database(self.name, force=force)

    def table(self, name: str) -> ir.TableExpr:
        """Return a table expression referencing a table in this database.

        Parameters
        ----------
        name
            The name of a table

        Returns
        -------
        TableExpr
            Table expression
        """
        qualified_name = self._qualify(name)
        return self.client.table(qualified_name, self.name)

    def list_tables(self, like=None):
        """List the tables in the database.

        Parameters
        ----------
        like
            A pattern to use for listing tables.
        """
        return self.client.list_tables(like, database=self.name)


class BaseBackend(abc.ABC):
    """Base backend class.

    All Ibis backends must subclass this class and implement all the required
    methods.
    """

    database_class = Database
    table_class: type[ops.DatabaseTable] = ops.DatabaseTable

    def __init__(self, *args, **kwargs):
        self._con_args: tuple[Any] = args
        self._con_kwargs: dict[str, Any] = kwargs

    def __getstate__(self):
        return dict(
            database_class=self.database_class,
            table_class=self.table_class,
            _con_args=self._con_args,
            _con_kwargs=self._con_kwargs,
        )

    def __hash__(self):
        return hash(self.db_identity)

    def __eq__(self, other):
        return self.db_identity == other.db_identity

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The name of the backend, for example 'sqlite'."""

    @cached_property
    def db_identity(self) -> str:
        """Return the identity of the database.

        Multiple connections to the same
        database will return the same value for `db_identity`.

        The default implementation assumes connection parameters uniquely
        specify the database.

        Returns
        -------
        Hashable
            Database identity
        """
        parts = [self.table_class.__name__]
        parts.extend(self._con_args)
        parts.extend(f'{k}={v}' for k, v in self._con_kwargs.items())
        return '_'.join(map(str, parts))

    def connect(self, *args, **kwargs) -> BaseBackend:
        """Connect to the database.

        Parameters
        ----------
        args
            Connection parameters
        kwargs
            Additional connection parameters

        Notes
        -----
        This returns a new backend instance with saved `args` and `kwargs`,
        calling `reconnect` is called before returning.

        Returns
        -------
        BaseBackend
            An instance of the backend
        """
        new_backend = self.__class__(*args, **kwargs)
        new_backend.reconnect()
        return new_backend

    def reconnect(self) -> None:
        """Reconnect to the database already configured with connect."""
        self.do_connect(*self._con_args, **self._con_kwargs)

    def do_connect(self, *args, **kwargs) -> None:
        """Connect to database specified by `args` and `kwargs`."""

    @deprecated(instead='equivalent methods in the backend')
    def database(self, name: str | None = None) -> Database:
        """Return a `Database` object for the `name` database.

        Parameters
        ----------
        name
            Name of the database to return the object for.

        Returns
        -------
        Database
            A database object for the specified database.
        """
        return self.database_class(
            name=name or self.current_database, client=self
        )

    @property
    @abc.abstractmethod
    def current_database(self) -> str | None:
        """Return the name of the current database.

        Backends that don't support different databases will return None.

        Returns
        -------
        str | None
            Name of the current database.
        """

    @abc.abstractmethod
    def list_databases(self, like: str = None) -> list[str]:
        """List existing databases in the current connection.

        Parameters
        ----------
        like
            A pattern in Python's regex format to filter returned database
            names.

        Returns
        -------
        list[str]
            The database names that exist in the current connection, that match
            the `like` pattern if provided.
        """

    @deprecated(version='2.0', instead='`name in client.list_databases()`')
    def exists_database(self, name: str) -> bool:
        """Return whether a database name exists in the current connection.

        Parameters
        ----------
        name
            Database to check for existence

        Returns
        -------
        bool
            Whether `name` exists
        """
        return name in self.list_databases()

    @staticmethod
    def _filter_with_like(
        values: Iterable[str],
        like: str | None = None,
    ) -> list[str]:
        """Filter names with a `like` pattern (regex).

        The methods `list_databases` and `list_tables` accept a `like`
        argument, which filters the returned tables with tables that match the
        provided pattern.

        We provide this method in the base backend, so backends can use it
        instead of reinventing the wheel.

        Parameters
        ----------
        values
            Iterable of strings to filter
        like
            Pattern to use for filtering names

        Returns
        -------
        list[str]
            Names filtered by the `like` pattern.
        """
        if like is None:
            return list(values)

        pattern = re.compile(like)
        return sorted(filter(lambda t: pattern.findall(t), values))

    @abc.abstractmethod
    def list_tables(
        self, like: str | None = None, database: str | None = None
    ) -> list[str]:
        """Return the list of table names in the current database.

        For some backends, the tables may be files in a directory,
        or other equivalent entities in a SQL database.

        Parameters
        ----------
        like : str, optional
            A pattern in Python's regex format.
        database : str, optional
            The database to list tables of, if not the current one.

        Returns
        -------
        list[str]
            The list of the table names that match the pattern `like`.
        """

    @deprecated(version='2.0', instead='`name in client.list_tables()`')
    def exists_table(self, name: str, database: str | None = None) -> bool:
        """Return whether a table name exists in the database.

        Parameters
        ----------
        name
            Table name
        database
            Database to check if given

        Returns
        -------
        bool
            Whether `name` is a table
        """
        return len(self.list_tables(like=name, database=database)) > 0

    @deprecated(
        version='2.0',
        instead='change the current database before calling `.table()`',
    )
    def table(self, name: str, database: str | None = None) -> ir.TableExpr:
        """Return a table expression from the database."""

    @deprecated(version='2.0', instead='`.table(name).schema()`')
    def get_schema(self, table_name: str, database: str = None) -> sch.Schema:
        """Return the schema of `table_name`."""
        return self.table(name=table_name, database=database).schema()

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Return the version of the backend engine.

        For database servers, return the server version.

        For others such as SQLite and pandas return the version of the
        underlying library or application.

        Returns
        -------
        str
            The backend version
        """

    def register_options(self) -> None:
        """Register custom backend options."""

    def compile(
        self,
        expr: ir.Expr,
        params: Mapping[ir.Expr, Any] | None = None,
    ) -> Any:
        """Compile an expression."""
        return self.compiler.to_sql(expr, params=params)

    def execute(self, expr: ir.Expr) -> Any:
        """Execute an expression."""

    @deprecated(
        version='2.0',
        instead='`compile` and capture `TranslationError` instead',
    )
    def verify(
        self,
        expr: ir.Expr,
        params: Mapping[ir.Expr, Any] | None = None,
    ) -> bool:
        """Verify `expr` is an expression that can be compiled."""
        try:
            self.compile(expr, params=params)
            return True
        except TranslationError:
            return False

    def add_operation(self, operation: ops.Node) -> Callable:
        """Add a translation function to the backend for a specific operation.

        Operations are defined in `ibis.expr.operations`, and a translation
        function receives the translator object and an expression as
        parameters, and returns a value depending on the backend. For example,
        in SQL backends, a NullLiteral operation could be translated to the
        string `"NULL"`.

        Examples
        --------
        >>> @ibis.sqlite.add_operation(ibis.expr.operations.NullLiteral)
        ... def _null_literal(translator, expression):
        ...     return 'NULL'
        """
        if not hasattr(self, 'compiler'):
            raise RuntimeError(
                'Only SQL-based backends support `add_operation`'
            )

        def decorator(translation_function: Callable) -> None:
            self.compiler.translator_class.add_operation(
                operation, translation_function
            )

        return decorator

    def create_database(self, name: str, force: bool = False) -> None:
        """Create a new database.

        Not all backends implement this method.

        Parameters
        ----------
        name
            Name of the new database.
        force
            If `False`, an exception is raised if the database already exists.
        """
        raise NotImplementedError(
            f'Backend "{self.name}" does not implement "create_database"'
        )

    def create_table(
        self,
        name: str,
        obj: pd.DataFrame | ir.TableExpr | None = None,
        schema: ibis.Schema | None = None,
        database: str | None = None,
    ) -> None:
        """Create a new table.

        Not all backends implement this method.

        Parameters
        ----------
        name
            Name of the new table.
        obj
            An Ibis table expression or pandas table that will be used to
            extract the schema and the data of the new table. If not provided,
            `schema` must be given.
        schema
            The schema for the new table. Only one of `schema` or `obj` can be
            provided.
        database
            Name of the database where the table will be created, if not the
            default.
        """
        raise NotImplementedError(
            f'Backend "{self.name}" does not implement "create_table"'
        )

    def drop_table(
        self,
        name: str,
        database: str | None = None,
        force: bool = False,
    ) -> None:
        """Drop a table.

        Parameters
        ----------
        name
            Name of the table to drop.
        database
            Name of the database where the table exists, if not the default.
        force
            If `False`, an exception is raised if the table does not exist.
        """
        raise NotImplementedError(
            f'Backend "{self.name}" does not implement "drop_table"'
        )

    def create_view(
        self,
        name: str,
        expr: ir.TableExpr,
        database: str | None = None,
    ) -> None:
        """Create a view.

        Parameters
        ----------
        name
            Name for the new view.
        expr
            An Ibis table expression that will be used to extract the query
            of the view.
        database
            Name of the database where the view will be created, if not the
            default.
        """
        raise NotImplementedError(
            f'Backend "{self.name}" does not implement "create_view"'
        )

    def drop_view(
        self, name: str, database: str | None = None, force: bool = False
    ) -> None:
        """Drop a view.

        Parameters
        ----------
        name
            Name of the view to drop.
        database
            Name of the database where the view exists, if not the default.
        force
            If `False`, an exception is raised if the view does not exist.
        """
        raise NotImplementedError(
            f'Backend "{self.name}" does not implement "drop_view"'
        )
