"""Ibis expression API definitions."""

from __future__ import annotations

import collections
import datetime
import functools
import numbers
import operator
from typing import IO, Iterable, Mapping, Sequence, TypeVar

import dateutil.parser
import pandas as pd
import toolz

import ibis.common.exceptions as com
import ibis.expr.analysis as _L
import ibis.expr.builders as bl
import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
import ibis.expr.rules as rlz
import ibis.expr.schema as sch
import ibis.expr.types as ir
import ibis.expr.window as win
import ibis.util as util
from ibis.expr.random import random  # noqa
from ibis.expr.schema import Schema
from ibis.expr.types import (  # noqa
    ArrayColumn,
    ArrayScalar,
    ArrayValue,
    BooleanColumn,
    BooleanScalar,
    BooleanValue,
    CategoryScalar,
    CategoryValue,
    ColumnExpr,
    DateColumn,
    DateScalar,
    DateValue,
    DecimalColumn,
    DecimalScalar,
    DecimalValue,
    DestructColumn,
    DestructScalar,
    DestructValue,
    Expr,
    FloatingColumn,
    FloatingScalar,
    FloatingValue,
    GeoSpatialColumn,
    GeoSpatialScalar,
    GeoSpatialValue,
    IntegerColumn,
    IntegerScalar,
    IntegerValue,
    IntervalColumn,
    IntervalScalar,
    IntervalValue,
    LineStringColumn,
    LineStringScalar,
    LineStringValue,
    MapColumn,
    MapScalar,
    MapValue,
    MultiLineStringColumn,
    MultiLineStringScalar,
    MultiLineStringValue,
    MultiPointColumn,
    MultiPointScalar,
    MultiPointValue,
    MultiPolygonColumn,
    MultiPolygonScalar,
    MultiPolygonValue,
    NullColumn,
    NullScalar,
    NullValue,
    NumericColumn,
    NumericScalar,
    NumericValue,
    PointColumn,
    PointScalar,
    PointValue,
    PolygonColumn,
    PolygonScalar,
    PolygonValue,
    ScalarExpr,
    StringColumn,
    StringScalar,
    StringValue,
    StructColumn,
    StructScalar,
    StructValue,
    TableExpr,
    TimeColumn,
    TimeScalar,
    TimestampColumn,
    TimestampScalar,
    TimestampValue,
    TimeValue,
    ValueExpr,
    array,
    literal,
    map,
    null,
    struct,
)
from ibis.expr.types.groupby import GroupedTableExpr  # noqa
from ibis.expr.window import (
    cumulative_window,
    range_window,
    rows_with_max_lookback,
    trailing_range_window,
    trailing_window,
    window,
)

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

__all__ = (
    'aggregate',
    'array',
    'case',
    'cast',
    'coalesce',
    'cross_join',
    'cumulative_window',
    'date',
    'desc',
    'Expr',
    'geo_area',
    'geo_as_binary',
    'geo_as_ewkb',
    'geo_as_ewkt',
    'geo_as_text',
    'geo_azimuth',
    'geo_buffer',
    'geo_centroid',
    'geo_contains',
    'geo_contains_properly',
    'geo_covers',
    'geo_covered_by',
    'geo_crosses',
    'geo_d_fully_within',
    'geo_disjoint',
    'geo_difference',
    'geo_d_within',
    'geo_envelope',
    'geo_equals',
    'geo_geometry_n',
    'geo_geometry_type',
    'geo_intersection',
    'geo_intersects',
    'geo_is_valid',
    'geo_line_locate_point',
    'geo_line_merge',
    'geo_line_substring',
    'geo_ordering_equals',
    'geo_overlaps',
    'geo_touches',
    'geo_distance',
    'geo_end_point',
    'geo_length',
    'geo_max_distance',
    'geo_n_points',
    'geo_n_rings',
    'geo_perimeter',
    'geo_point',
    'geo_point_n',
    'geo_simplify',
    'geo_srid',
    'geo_start_point',
    'geo_transform',
    'geo_unary_union',
    'geo_union',
    'geo_within',
    'geo_x',
    'geo_x_max',
    'geo_x_min',
    'geo_y',
    'geo_y_max',
    'geo_y_min',
    'greatest',
    'ifelse',
    'infer_dtype',
    'infer_schema',
    'interval',
    'join',
    'least',
    'literal',
    'map',
    'NA',
    'negate',
    'now',
    'null',
    'param',
    'pi',
    'prevent_rewrite',
    'random',
    'range_window',
    'row_number',
    'rows_with_max_lookback',
    'schema',
    'Schema',
    'sequence',
    'struct',
    'table',
    'time',
    'timestamp',
    'trailing_range_window',
    'trailing_window',
    'where',
    'window',
)


infer_dtype = dt.infer
infer_schema = sch.infer


NA = null()

T = TypeVar("T")


def param(type: dt.DataType) -> ir.ScalarExpr:
    """Create a deferred parameter of a given type.

    Parameters
    ----------
    type
        The type of the unbound parameter, e.g., double, int64, date, etc.

    Returns
    -------
    ScalarExpr
        A scalar expression backend by a parameter

    Examples
    --------
    >>> import ibis
    >>> import ibis.expr.datatypes as dt
    >>> start = ibis.param(dt.date)
    >>> end = ibis.param(dt.date)
    >>> schema = [('timestamp_col', 'timestamp'), ('value', 'double')]
    >>> t = ibis.table(schema)
    >>> predicates = [t.timestamp_col >= start, t.timestamp_col <= end]
    >>> expr = t.filter(predicates).value.sum()
    """
    return ops.ScalarParameter(dt.dtype(type)).to_expr()


def sequence(values: Sequence[T | None]) -> ir.ListExpr:
    """Wrap a list of Python values as an Ibis sequence type.

    Parameters
    ----------
    values
        Should all be None or the same type

    Returns
    -------
    ListExpr
        A list expression
    """
    return ops.ValueList(values).to_expr()


def schema(
    pairs: Iterable[tuple[str, dt.DataType]]
    | Mapping[str, dt.DataType]
    | None = None,
    names: Iterable[str] | None = None,
    types: Iterable[str | dt.DataType] | None = None,
) -> sch.Schema:
    """Validate and return an Schema object.

    Parameters
    ----------
    pairs
        List or dictionary of name, type pairs. Mutually exclusive with `names`
        and `types`.
    names
        Field names. Mutually exclusive with `pairs`.
    types
        Field types. Mutually exclusive with `pairs`.

    Examples
    --------
    >>> from ibis import schema
    >>> sc = schema([('foo', 'string'),
    ...              ('bar', 'int64'),
    ...              ('baz', 'boolean')])
    >>> sc2 = schema(names=['foo', 'bar', 'baz'],
    ...              types=['string', 'int64', 'boolean'])

    Returns
    -------
    Schema
        An ibis schema
    """  # noqa: E501
    if pairs is not None:
        return Schema.from_dict(dict(pairs))
    else:
        return Schema(names, types)


_schema = schema


def table(schema: sch.Schema, name: str | None = None) -> ir.TableExpr:
    """Create an unbound table for build expressions without data.


    Parameters
    ----------
    schema
        A schema for the table
    name
        Name for the table

    Returns
    -------
    TableExpr
        An unbound table expression
    """
    if not isinstance(schema, Schema):
        schema = _schema(pairs=schema)

    node = ops.UnboundTable(schema, name=name)
    return node.to_expr()


def desc(expr: ir.ColumnExpr | str) -> ir.SortExpr | ops.DeferredSortKey:
    """Create a descending sort key from `expr` or column name.

    Parameters
    ----------
    expr
        The expression or column name to use for sorting

    Examples
    --------
    >>> import ibis
    >>> t = ibis.table([('g', 'string')])
    >>> result = t.group_by('g').size('count').sort_by(ibis.desc('count'))

    Returns
    -------
    ops.DeferredSortKey
        A deferred sort key
    """
    if not isinstance(expr, Expr):
        return ops.DeferredSortKey(expr, ascending=False)
    else:
        return ops.SortKey(expr, ascending=False).to_expr()


def timestamp(
    value: str | numbers.Integral,
    timezone: str | None = None,
) -> ir.TimestampScalar:
    """Construct a timestamp literal if `value` is coercible to a timestamp.

    Parameters
    ----------
    value
        The value to use for constructing the timestamp
    timezone
        The timezone of the timestamp

    Returns
    -------
    TimestampScalar
        A timestamp expression
    """
    if isinstance(value, str):
        try:
            value = pd.Timestamp(value, tz=timezone)
        except pd.errors.OutOfBoundsDatetime:
            value = dateutil.parser.parse(value)
    if isinstance(value, numbers.Integral):
        raise TypeError(
            (
                "Passing an integer to ibis.timestamp is not supported. Use "
                "ibis.literal({value}).to_timestamp() to create a timestamp "
                "expression from an integer."
            ).format(value=value)
        )
    return literal(value, type=dt.Timestamp(timezone=timezone))


def date(value: str) -> ir.DateScalar:
    """Return a date literal if `value` is coercible to a date.

    Parameters
    ----------
    value
        Date string

    Returns
    -------
    DateScalar
        A date expression
    """
    if isinstance(value, str):
        value = pd.to_datetime(value).date()
    return literal(value, type=dt.date)


def time(value: str) -> ir.TimeScalar:
    """Return a time literal if `value` is coercible to a time.

    Parameters
    ----------
    value
        Time string

    Returns
    -------
    TimeScalar
        A time expression
    """
    if isinstance(value, str):
        value = pd.to_datetime(value).time()
    return literal(value, type=dt.time)


def interval(
    value: int | datetime.timedelta | None = None,
    unit: str = 's',
    years: int | None = None,
    quarters: int | None = None,
    months: int | None = None,
    weeks: int | None = None,
    days: int | None = None,
    hours: int | None = None,
    minutes: int | None = None,
    seconds: int | None = None,
    milliseconds: int | None = None,
    microseconds: int | None = None,
    nanoseconds: int | None = None,
) -> ir.IntervalScalar:
    """Return an interval literal expression.

    Parameters
    ----------
    value
        Interval value. If passed, must be combined with `unit`.
    unit
        Unit of `value`
    years
        Number of years
    quarters
        Number of quarters
    months
        Number of months
    weeks
        Number of weeks
    days
        Number of days
    hours
        Number of hours
    minutes
        Number of minutes
    seconds
        Number of seconds
    milliseconds
        Number of milliseconds
    microseconds
        Number of microseconds
    nanoseconds
        Number of nanoseconds

    Returns
    -------
    IntervalScalar
        An interval expression
    """
    if value is not None:
        if isinstance(value, datetime.timedelta):
            unit = 's'
            value = int(value.total_seconds())
        elif not isinstance(value, int):
            raise ValueError('Interval value must be an integer')
    else:
        kwds = [
            ('Y', years),
            ('Q', quarters),
            ('M', months),
            ('W', weeks),
            ('D', days),
            ('h', hours),
            ('m', minutes),
            ('s', seconds),
            ('ms', milliseconds),
            ('us', microseconds),
            ('ns', nanoseconds),
        ]
        defined_units = [(k, v) for k, v in kwds if v is not None]

        if len(defined_units) != 1:
            raise ValueError('Exactly one argument is required')

        unit, value = defined_units[0]

    value_type = literal(value).type()
    type = dt.Interval(unit, value_type)

    return literal(value, type=type).op().to_expr()


def case() -> bl.SearchedCaseBuilder:
    """Begin constructing a case expression.

    Notes
    -----
    Use the `.when` method on the resulting object followed by .end to create a
    complete case.

    Examples
    --------
    >>> import ibis
    >>> cond1 = ibis.literal(1) == 1
    >>> cond2 = ibis.literal(2) == 1
    >>> result1 = 3
    >>> result2 = 4
    >>> expr = (ibis.case()
    ...         .when(cond1, result1)
    ...         .when(cond2, result2).end())

    Returns
    -------
    bl.SearchedCaseBuilder
        A builder object to use for constructing a case expression.
    """
    return bl.SearchedCaseBuilder()


def now() -> ir.TimestampScalar:
    """Return an expression that will compute the current timestamp.

    Returns
    -------
    TimestampScalar
        A "now" expression
    """
    return ops.TimestampNow().to_expr()


def row_number() -> ir.IntegerColumn:
    """Return an analytic function expression for the current row number.

    Returns
    -------
    IntegerColumn
        A column expression enumerating rows
    """
    return ops.RowNumber().to_expr()


e = ops.E().to_expr()

pi = ops.Pi().to_expr()


def _add_methods(klass, method_table):
    for k, v in method_table.items():
        setattr(klass, k, v)


def _unary_op(name, klass, doc=None):
    def f(arg):
        return klass(arg).to_expr()

    f.__name__ = name
    if doc is not None:
        f.__doc__ = doc
    else:
        f.__doc__ = klass.__doc__
    return f


def negate(arg: ir.NumericValue) -> ir.NumericValue:
    """Negate a numeric expression.

    Parameters
    ----------
    arg
        A numeric value to negate

    Returns
    -------
    N
        A numeric value expression
    """
    op = arg.op()
    if hasattr(op, 'negate'):
        result = op.negate()
    else:
        result = ops.Negate(arg)

    return result.to_expr()


def count(
    expr: ir.TableExpr | ir.ColumnExpr,
    where: ir.BooleanValue | None = None,
) -> ir.IntegerScalar:
    """Compute the number of rows in an expression.

    For column expressions the count excludes nulls.

    For tables the number of rows in the table are computed.

    Parameters
    ----------
    expr
        Expression to count
    where
        Filter expression

    Returns
    -------
    IntegerScalar
        Number of elements in an expression
    """
    op = expr.op()
    if isinstance(op, ops.DistinctColumn):
        result = ops.CountDistinct(op.args[0], where).to_expr()
    else:
        result = ops.Count(expr, where).to_expr()

    return result.name('count')


def group_concat(
    arg: ir.StringValue,
    sep: str = ',',
    where: ir.BooleanValue | None = None,
) -> ir.StringValue:
    """Concatenate values using the indicated separator to produce a string.

    Parameters
    ----------
    arg
        A column of strings
    sep
        Separator will be used to join strings
    where
        Filter expression

    Returns
    -------
    S
        Concatenate string expression
    """
    return ops.GroupConcat(arg, sep=sep, where=where).to_expr()


def arbitrary(
    arg: ir.ColumnExpr,
    where: ir.BooleanValue | None = None,
    how: str | None = None,
) -> ir.ScalarExpr:
    """Select an arbitrary value in a column.

    Parameters
    ----------
    arg
        An expression
    where
        A filter expression
    how
      Heavy selects a frequently occurring value using the heavy hitters
      algorithm. Heavy is only supported by Clickhouse backend.

    Returns
    -------
    V
        An expression
    """
    return ops.Arbitrary(arg, how=how, where=where).to_expr()


def _binop_expr(name, klass):
    def f(self, other):
        try:
            other = rlz.any(other)
            op = klass(self, other)
            return op.to_expr()
        except (com.IbisTypeError, NotImplementedError):
            return NotImplemented

    f.__name__ = name

    return f


def _rbinop_expr(name, klass):
    # For reflexive binary ops, like radd, etc.
    def f(self, other):
        other = rlz.any(other)
        op = klass(other, self)
        return op.to_expr()

    f.__name__ = name
    return f


def _boolean_binary_op(name, klass):
    def f(self, other):
        other = rlz.any(other)

        if not isinstance(other, ir.BooleanValue):
            raise TypeError(other)

        op = klass(self, other)
        return op.to_expr()

    f.__name__ = name

    return f


def _boolean_unary_op(name, klass):
    def f(self):
        return klass(self).to_expr()

    f.__name__ = name
    return f


def _boolean_binary_rop(name, klass):
    def f(self, other):
        other = rlz.any(other)

        if not isinstance(other, ir.BooleanValue):
            raise TypeError(other)

        op = klass(other, self)
        return op.to_expr()

    f.__name__ = name
    return f


def _agg_function(name, klass, assign_default_name=True):
    def f(self, where=None):
        expr = klass(self, where).to_expr()
        if assign_default_name:
            expr = expr.name(name)
        return expr

    f.__name__ = name
    f.__doc__ = klass.__doc__
    return f


def _extract_field(name, klass):
    def f(self):
        expr = klass(self).to_expr()
        return expr.name(name)

    f.__name__ = name
    return f


# ---------------------------------------------------------------------
# Generic value API


def cast(arg: ir.ValueExpr, target_type: dt.DataType) -> ir.ValueExpr:
    """Cast value(s) to indicated data type.

    Parameters
    ----------
    arg
        Expression to cast
    target_type
        Type to cast to

    Returns
    -------
    ValueExpr
        Casted expression
    """
    # validate
    op = ops.Cast(arg, to=target_type)

    if op.to.equals(arg.type()):
        # noop case if passed type is the same
        return arg

    if isinstance(op.to, (dt.Geography, dt.Geometry)):
        from_geotype = arg.type().geotype or 'geometry'
        to_geotype = op.to.geotype
        if from_geotype == to_geotype:
            return arg

    result = op.to_expr()
    if not arg.has_name():
        return result
    expr_name = f'cast({arg.get_name()}, {op.to})'
    return result.name(expr_name)


def typeof(arg: ir.ValueExpr) -> ir.StringValue:
    """Return the data type of the argument according to the current backend.

    Parameters
    ----------
    arg
        An expression

    Returns
    -------
    StringValue
        A string indicating the type of the value
    """
    return ops.TypeOf(arg).to_expr()


def hash(arg: ir.ValueExpr, how: str = 'fnv') -> ir.IntegerValue:
    """Compute an integer hash value for the indicated value expression.

    Parameters
    ----------
    arg
        An expression
    how
        Hash algorithm to use

    Returns
    -------
    IntegerValue
        The hash value of `arg`
    """
    return ops.Hash(arg, how).to_expr()


def fillna(arg: ir.ValueExpr, fill_value: ir.ScalarExpr) -> ir.ValueExpr:
    """Replace any null values with the indicated fill value.

    Parameters
    ----------
    arg
        An expression
    fill_value
        Value to replace `NA` values in `arg` with

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('col', 'int64'), ('other_col', 'int64')])
    >>> result = table.col.fillna(5)
    >>> result2 = table.col.fillna(table.other_col * 3)

    Returns
    -------
    ValueExpr
        `arg` filled with `fill_value` where it is `NA`
    """
    return ops.IfNull(arg, fill_value).to_expr()


def coalesce(*args: ir.ValueExpr) -> ir.ValueExpr:
    """Compute the first non-null value(s) from the passed arguments.

    Parameters
    ----------
    args
        Arguments to choose from

    Examples
    --------
    >>> import ibis
    >>> expr1 = None
    >>> expr2 = 4
    >>> result = ibis.coalesce(expr1, expr2, 5)

    Returns
    -------
    ValueExpr
        Coalesced expression

    See Also
    --------
    pandas.DataFrame.combine_first
    """
    op = ops.Coalesce(args)
    return op.to_expr()


def greatest(*args: ir.ValueExpr) -> ir.ValueExpr:
    """Compute the largest value among the supplied arguments.

    Parameters
    ----------
    args
        Arguments to choose from

    Returns
    -------
    ValueExpr
        Maximum of the passed arguments
    """
    op = ops.Greatest(args)
    return op.to_expr()


def least(*args: ir.ValueExpr) -> ir.ValueExpr:
    """Compute the smallest value among the supplied arguments.

    Parameters
    ----------
    args
        Arguments to choose from

    Returns
    -------
    ValueExpr
        Minimum of the passed arguments
    """
    op = ops.Least(args)
    return op.to_expr()


def where(
    boolean_expr: ir.BooleanValue,
    true_expr: ir.ValueExpr,
    false_null_expr: ir.ValueExpr,
) -> ir.ValueExpr:
    """Return `true_expr` if `boolean_expr` is `True` else `false_null_expr`.

    Parameters
    ----------
    boolean_expr
        A boolean expression
    true_expr
        Value returned if `boolean_expr` is `True`
    false_null_expr
        Value returned if `boolean_expr` is `False` or `NULL`

    Returns
    -------
    ir.ValueExpr
        An expression
    """
    op = ops.Where(boolean_expr, true_expr, false_null_expr)
    return op.to_expr()


def over(expr: ir.ValueExpr, window: win.Window) -> ir.ValueExpr:
    """Construct a window expression.

    Parameters
    ----------
    expr
        A value expression
    window
        Window specification

    Returns
    -------
    ValueExpr
        A window function expression

    See Also
    --------
    ibis.window
    """
    prior_op = expr.op()

    if isinstance(prior_op, ops.WindowOp):
        op = prior_op.over(window)
    else:
        op = ops.WindowOp(expr, window)

    result = op.to_expr()

    try:
        name = expr.get_name()
    except com.ExpressionError:
        pass
    else:
        result = result.name(name)

    return result


def value_counts(
    arg: ir.ValueExpr, metric_name: str = 'count'
) -> ir.TableExpr:
    """Compute a frequency table for `arg`.

    Parameters
    ----------
    arg
        An expression

    Returns
    -------
    TableExpr
        Frequency table expression
    """
    base = ir.relations.find_base_table(arg)
    metric = base.count().name(metric_name)

    try:
        arg.get_name()
    except com.ExpressionError:
        arg = arg.name('unnamed')

    return base.group_by(arg).aggregate(metric)


def nullif(value: ir.ValueExpr, null_if_expr: ir.ValueExpr) -> ir.ValueExpr:
    """Set values to null if they equal the values `null_if_expr`.

    Commonly use to avoid divide-by-zero problems by replacing zero with NULL
    in the divisor.

    Parameters
    ----------
    value
        Value expression
    null_if_expr
        Expression indicating what values should be NULL

    Returns
    -------
    ir.ValueExpr
        Value expression
    """
    return ops.NullIf(value, null_if_expr).to_expr()


def between(
    arg: ir.ValueExpr, lower: ir.ValueExpr, upper: ir.ValueExpr
) -> ir.BooleanValue:
    """Check if `arg` is between `lower` and `upper`, inclusive.

    Parameters
    ----------
    arg
        Expression
    lower
        Lower bound
    upper
        Upper bound

    Returns
    -------
    BooleanValue
        Expression indicating membership in the provided range
    """
    lower, upper = rlz.any(lower), rlz.any(upper)
    op = ops.Between(arg, lower, upper)
    return op.to_expr()


def isin(
    arg: ir.ValueExpr, values: ir.ValueExpr | Sequence[ir.ValueExpr]
) -> ir.BooleanValue:
    """Check whether `arg`'s values are contained within `values`.

    Parameters
    ----------
    arg
        Expression
    values
        Values or expression to check for membership

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('string_col', 'string')])
    >>> table2 = ibis.table([('other_string_col', 'string')])
    >>> expr = table.string_col.isin(['foo', 'bar', 'baz'])
    >>> expr2 = table.string_col.isin(table2.other_string_col)

    Returns
    -------
    BooleanValue
        Expression indicating membership
    """
    op = ops.Contains(arg, values)
    return op.to_expr()


def notin(
    arg: ir.ValueExpr, values: ir.ValueExpr | Sequence[ir.ValueExpr]
) -> ir.BooleanValue:
    """Check whether `arg`'s values are not contained in `values`.

    Parameters
    ----------
    arg
        Expression
    values
        Values or expression to check for lack of membership

    Returns
    -------
    BooleanValue
        Whether `arg`'s values are not contained in `values`
    """
    op = ops.NotContains(arg, values)
    return op.to_expr()


add = _binop_expr('__add__', ops.Add)
sub = _binop_expr('__sub__', ops.Subtract)
mul = _binop_expr('__mul__', ops.Multiply)
div = _binop_expr('__div__', ops.Divide)
floordiv = _binop_expr('__floordiv__', ops.FloorDivide)
pow = _binop_expr('__pow__', ops.Power)
mod = _binop_expr('__mod__', ops.Modulus)

radd = _rbinop_expr('__radd__', ops.Add)
rsub = _rbinop_expr('__rsub__', ops.Subtract)
rdiv = _rbinop_expr('__rdiv__', ops.Divide)
rfloordiv = _rbinop_expr('__rfloordiv__', ops.FloorDivide)


def substitute(
    arg: ir.ValueExpr,
    value: ir.ValueExor,
    replacement=None,
    else_=None,
):
    """Replace one or more values in a value expression.

    Parameters
    ----------
    arg
        Value expression
    value
        Expression or mapping
    replacement
        Expression. If an expression is passed to value, this must be passed.
    else_
        Expression

    Returns
    -------
    ValueExpr
        Replaced values
    """
    expr = arg.case()
    if isinstance(value, dict):
        for k, v in sorted(value.items()):
            expr = expr.when(k, v)
    else:
        expr = expr.when(value, replacement)

    if else_ is not None:
        expr = expr.else_(else_)
    else:
        expr = expr.else_(arg)

    return expr.end()


def _case(arg):
    """Create a new SimpleCaseBuilder to chain multiple if-else statements.

    Add new search expressions with the `.when` method. These must be
    comparable with this column expression. Conclude by calling `.end()`

    Parameters
    ----------
    arg
        A value expression

    Returns
    -------
    bl.SimpleCaseBuilder
        A case builder

    Examples
    --------
    >>> import ibis
    >>> t = ibis.table([('string_col', 'string')], name='t')
    >>> expr = t.string_col
    >>> case_expr = (expr.case()
    ...              .when('a', 'an a')
    ...              .when('b', 'a b')
    ...              .else_('null or (not a and not b)')
    ...              .end())
    >>> case_expr  # doctest: +NORMALIZE_WHITESPACE
    ref_0
    UnboundTable[table]
      name: t
      schema:
        string_col : string
    <BLANKLINE>
    SimpleCase[string*]
      base:
        string_col = Column[string*] 'string_col' from table
          ref_0
      cases:
        Literal[string]
          a
        Literal[string]
          b
      results:
        Literal[string]
          an a
        Literal[string]
          a b
      default:
        Literal[string]
          null or (not a and not b)
    """
    return bl.SimpleCaseBuilder(arg)


def cases(arg, case_result_pairs, default=None) -> ir.ValueExpr:
    """Create a case expression in one shot.

    Returns
    -------
    ValueExpr
        Value expression
    """
    builder = arg.case()
    for case, result in case_result_pairs:
        builder = builder.when(case, result)
    if default is not None:
        builder = builder.else_(default)
    return builder.end()


_generic_value_methods = {
    'hash': hash,
    'cast': cast,
    'coalesce': coalesce,
    'typeof': typeof,
    'fillna': fillna,
    'nullif': nullif,
    'between': between,
    'isin': isin,
    'notin': notin,
    'isnull': _unary_op('isnull', ops.IsNull),
    'notnull': _unary_op('notnull', ops.NotNull),
    'over': over,
    'case': _case,
    'cases': cases,
    'substitute': substitute,
    '__eq__': _binop_expr('__eq__', ops.Equals),
    '__ne__': _binop_expr('__ne__', ops.NotEquals),
    '__ge__': _binop_expr('__ge__', ops.GreaterEqual),
    '__gt__': _binop_expr('__gt__', ops.Greater),
    '__le__': _binop_expr('__le__', ops.LessEqual),
    '__lt__': _binop_expr('__lt__', ops.Less),
    'collect': _unary_op('collect', ops.ArrayCollect),
    'identical_to': _binop_expr('identical_to', ops.IdenticalTo),
}


approx_nunique = _agg_function('approx_nunique', ops.HLLCardinality, True)
approx_median = _agg_function('approx_median', ops.CMSMedian, True)
max = _agg_function('max', ops.Max, True)
min = _agg_function('min', ops.Min, True)
nunique = _agg_function('nunique', ops.CountDistinct, True)


def lag(arg, offset=None, default=None):
    return ops.Lag(arg, offset, default).to_expr()


def lead(arg, offset=None, default=None):
    return ops.Lead(arg, offset, default).to_expr()


first = _unary_op('first', ops.FirstValue)
last = _unary_op('last', ops.LastValue)
rank = _unary_op('rank', ops.MinRank)
dense_rank = _unary_op('dense_rank', ops.DenseRank)
percent_rank = _unary_op('percent_rank', ops.PercentRank)
cummin = _unary_op('cummin', ops.CumulativeMin)
cummax = _unary_op('cummax', ops.CumulativeMax)


def ntile(arg, buckets):
    return ops.NTile(arg, buckets).to_expr()


def nth(arg, k):
    """
    Analytic operation computing nth value from start of sequence

    Parameters
    ----------
    arg : array expression
    k : int
        Desired rank value

    Returns
    -------
    nth : type of argument
    """
    return ops.NthValue(arg, k).to_expr()


def distinct(arg):
    """
    Compute set of unique values occurring in this array. Can not be used
    in conjunction with other array expressions from the same context
    (because it's a cardinality-modifying pseudo-reduction).
    """
    op = ops.DistinctColumn(arg)
    return op.to_expr()


def topk(
    arg: ir.ColumnExpr, k: int, by: ir.ValueExpr | None = None
) -> ir.TopKExpr:
    """Return a "top k" expression.

    Parameters
    ----------
    arg
        A column expression
    k
        Return this number of rows
    by
        An expression. Defaults to the count

    Returns
    -------
    TopKExpr
        A top-k expression
    """
    op = ops.TopK(arg, k, by=by if by is not None else arg.count())
    return op.to_expr()


def bottomk(arg, k, by=None):
    raise NotImplementedError


def _generic_summary(
    arg: ir.ValueExpr,
    exact_nunique: bool = False,
    prefix: str = "",
    suffix: str = "",
) -> list[ir.NumericScalar]:
    """Compute a set of summary metrics from the input value expression.

    Parameters
    ----------
    arg
        Value expression
    exact_nunique
        Compute the exact number of distinct values. Typically slower if
        `True`.
    prefix
        String prefix for metric names
    suffix
        String suffix for metric names

    Returns
    -------
    list[ir.NumericScalar]
        Metrics list
    """
    if exact_nunique:
        unique_metric = arg.nunique().name('uniques')
    else:
        unique_metric = arg.approx_nunique().name('uniques')

    metrics = [arg.count(), arg.isnull().sum().name('nulls'), unique_metric]
    metrics = [m.name(f"{prefix}{m.get_name()}{suffix}") for m in metrics]

    return metrics


def _numeric_summary(
    arg: ir.NumericColumn,
    exact_nunique: bool = False,
    prefix: str = "",
    suffix: str = "",
) -> list[ir.NumericScalar]:
    """Compute a set of summary metrics from the input numeric value expression.

    Parameters
    ----------
    arg
        Numeric expression
    exact_nunique
        Compute the exact number of distinct values. Typically slower if
        `True`.
    prefix
        String prefix for metric names
    suffix
        String suffix for metric names

    Returns
    -------
    list[ir.NumericScalar]
        Metrics list
    """
    if exact_nunique:
        unique_metric = arg.nunique().name('nunique')
    else:
        unique_metric = arg.approx_nunique().name('approx_nunique')

    metrics = [
        arg.count(),
        arg.isnull().sum().name('nulls'),
        arg.min(),
        arg.max(),
        arg.sum(),
        arg.mean(),
        unique_metric,
    ]
    metrics = [m.name(f"{prefix}{m.get_name()}{suffix}") for m in metrics]

    return metrics


_generic_column_methods = {
    'bottomk': bottomk,
    'distinct': distinct,
    'nunique': nunique,
    'topk': topk,
    'summary': _generic_summary,
    'count': count,
    'arbitrary': arbitrary,
    'min': min,
    'max': max,
    'approx_median': approx_median,
    'approx_nunique': approx_nunique,
    'group_concat': group_concat,
    'value_counts': value_counts,
    'first': first,
    'last': last,
    'dense_rank': dense_rank,
    'rank': rank,
    'percent_rank': percent_rank,
    # 'nth': nth,
    'ntile': ntile,
    'lag': lag,
    'lead': lead,
    'cummin': cummin,
    'cummax': cummax,
}


# TODO: should bound to AnyValue and AnyColumn instead, but that breaks
#       doc builds, because it checks methods on ColumnExpr
_add_methods(ir.ValueExpr, _generic_value_methods)
_add_methods(ir.ColumnExpr, _generic_column_methods)


# ---------------------------------------------------------------------
# Numeric API


def round(arg: ir.NumericValue, digits: int | None = None) -> ir.NumericValue:
    """Round values to an indicated number of decimal places.

    Returns
    -------
    rounded : type depending on digits argument
      digits None or 0
        decimal types: decimal
        other numeric types: bigint
      digits nonzero
        decimal types: decimal
        other numeric types: double
    """
    op = ops.Round(arg, digits)
    return op.to_expr()


def log(
    arg: ir.NumericValue, base: ir.NumericValue | None = None
) -> ir.NumericValue:
    """Return the logarithm using a specified base.

    Parameters
    ----------
    arg
        A numeric expression
    base
        The base of the logarithm. If `None`, base `e` is used.

    Returns
    -------
    NumericValue
        Logarithm of `arg` with base `base`
    """
    op = ops.Log(arg, base)
    return op.to_expr()


def clip(
    arg: ir.NumericValue,
    lower: ir.NumericValue | None = None,
    upper: ir.NumericValue | None = None,
) -> ir.NumericValue:
    """
    Trim values at input threshold(s).

    Parameters
    ----------
    arg
        Numeric expression
    lower
        Lower bound
    upper
        Upper bound

    Returns
    -------
    NumericValue
        Clipped input
    """
    if lower is None and upper is None:
        raise ValueError("at least one of lower and upper must be provided")

    op = ops.Clip(arg, lower, upper)
    return op.to_expr()


def quantile(
    arg: ir.NumericValue,
    quantile: ir.NumericValue,
    interpolation: Literal[
        'linear',
        'lower',
        'higher',
        'midpoint',
        'nearest',
    ] = 'linear',
) -> ir.NumericValue:
    """Return value at the given quantile.

    Parameters
    ----------
    arg
        Numeric expression
    quantile
        `0 <= quantile <= 1`, the quantile(s) to compute
    interpolation
        This optional parameter specifies the interpolation method to use,
        when the desired quantile lies between two data points `i` and `j`:

        * linear: `i + (j - i) * fraction`, where `fraction` is the
          fractional part of the index surrounded by `i` and `j`.
        * lower: `i`.
        * higher: `j`.
        * nearest: `i` or `j` whichever is nearest.
        * midpoint: (`i` + `j`) / 2.

    Returns
    -------
    NumericValue
        Quantile of the input
    """
    if isinstance(quantile, collections.abc.Sequence):
        op = ops.MultiQuantile(
            arg, quantile=quantile, interpolation=interpolation
        )
    else:
        op = ops.Quantile(arg, quantile=quantile, interpolation=interpolation)
    return op.to_expr()


def _integer_to_timestamp(
    arg: ir.IntegerValue, unit: Literal['s', 'ms', 'us'] = 's'
) -> ir.TimestampValue:
    """Convert integral UNIX timestamp to a timestamp.

    Parameters
    ----------
    arg
        Integral UNIX timestamp
    unit
        The resolution of `arg`

    Returns
    -------
    TimestampValue
        `arg` converted to a timestamp
    """
    op = ops.TimestampFromUNIX(arg, unit)
    return op.to_expr()


def _integer_to_interval(
    arg: ir.IntegerValue,
    unit: Literal['Y', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us', 'ns'] = 's',
) -> ir.IntervalValue:
    """
    Convert integer interval with the same inner type

    Parameters
    ----------
    arg
        Integer value
    unit
        Unit for the resulting interval

    Returns
    -------
    IntervalValue
        An interval in units of `unit`
    """
    op = ops.IntervalFromInteger(arg, unit)
    return op.to_expr()


abs = _unary_op('abs', ops.Abs)
ceil = _unary_op('ceil', ops.Ceil)
degrees = _unary_op('degrees', ops.Degrees)
exp = _unary_op('exp', ops.Exp)
floor = _unary_op('floor', ops.Floor)
log2 = _unary_op('log2', ops.Log2)
log10 = _unary_op('log10', ops.Log10)
ln = _unary_op('ln', ops.Ln)
radians = _unary_op('radians', ops.Radians)
sign = _unary_op('sign', ops.Sign)
sqrt = _unary_op('sqrt', ops.Sqrt)

# TRIGONOMETRIC OPERATIONS
acos = _unary_op('acos', ops.Acos)
asin = _unary_op('asin', ops.Asin)
atan = _unary_op('atan', ops.Atan)
atan2 = _binop_expr('atan2', ops.Atan2)
cos = _unary_op('cos', ops.Cos)
cot = _unary_op('cot', ops.Cot)
sin = _unary_op('sin', ops.Sin)
tan = _unary_op('tan', ops.Tan)


_numeric_value_methods = {
    '__neg__': negate,
    'abs': abs,
    'ceil': ceil,
    'degrees': degrees,
    'deg2rad': radians,
    'floor': floor,
    'radians': radians,
    'rad2deg': degrees,
    'sign': sign,
    'exp': exp,
    'sqrt': sqrt,
    'log': log,
    'ln': ln,
    'log2': log2,
    'log10': log10,
    'round': round,
    'nullifzero': _unary_op('nullifzero', ops.NullIfZero),
    'zeroifnull': _unary_op('zeroifnull', ops.ZeroIfNull),
    'clip': clip,
    '__add__': add,
    'add': add,
    '__sub__': sub,
    'sub': sub,
    '__mul__': mul,
    'mul': mul,
    '__div__': div,
    '__truediv__': div,
    '__floordiv__': floordiv,
    'div': div,
    'floordiv': floordiv,
    '__rdiv__': rdiv,
    '__rtruediv__': rdiv,
    '__rfloordiv__': rfloordiv,
    'rdiv': rdiv,
    'rfloordiv': rfloordiv,
    '__pow__': pow,
    'pow': pow,
    '__radd__': add,
    'radd': add,
    '__rsub__': rsub,
    'rsub': rsub,
    '__rmul__': _rbinop_expr('__rmul__', ops.Multiply),
    '__rpow__': _rbinop_expr('__rpow__', ops.Power),
    '__mod__': mod,
    '__rmod__': _rbinop_expr('__rmod__', ops.Modulus),
    # trigonometric operations
    'acos': acos,
    'asin': asin,
    'atan': atan,
    'atan2': atan2,
    'cos': cos,
    'cot': cot,
    'sin': sin,
    'tan': tan,
}


def convert_base(
    arg: ir.IntegerValue | ir.StringValue,
    from_base: ir.IntegerValue,
    to_base: ir.IntegerValue,
) -> ir.IntegerValue:
    """Convert an integer or string from one base to another.

    Parameters
    ----------
    arg
        Integer or string expression
    from_base
        Base of `arg`
    to_base
        New base

    Returns
    -------
    IntegerValue
        Converted expression
    """
    return ops.BaseConvert(arg, from_base, to_base).to_expr()


_integer_value_methods = {
    'to_timestamp': _integer_to_timestamp,
    'to_interval': _integer_to_interval,
    'convert_base': convert_base,
}


bit_and = _agg_function('bit_and', ops.BitAnd, True)
bit_or = _agg_function('bit_or', ops.BitOr, True)
bit_xor = _agg_function('bit_xor', ops.BitXor, True)

mean = _agg_function('mean', ops.Mean, True)
cummean = _unary_op('cummean', ops.CumulativeMean)

sum = _agg_function('sum', ops.Sum, True)
cumsum = _unary_op('cumsum', ops.CumulativeSum)


def std(
    arg: ir.NumericColumn,
    where: ir.BooleanValue | None = None,
    how: Literal['sample', 'pop'] = 'sample',
) -> ir.NumericScalar:
    """Return the standard deviation of a numeric column.

    Parameters
    ----------
    arg
        Numeric column
    how
        Sample or population standard deviation

    Returns
    -------
    NumericScalar
        Standard deviation of `arg`
    """
    expr = ops.StandardDev(arg, how=how, where=where).to_expr()
    expr = expr.name('std')
    return expr


def variance(
    arg: ir.NumericColumn,
    where: ir.BooleanValue | None = None,
    how: Literal['sample', 'pop'] = 'sample',
) -> ir.NumericScalar:
    """Return the variance of a numeric column.

    Parameters
    ----------
    arg
        Numeric column
    how
        Sample or population variance

    Returns
    -------
    NumericScalar
        Standard deviation of `arg`
    """
    expr = ops.Variance(arg, how=how, where=where).to_expr()
    expr = expr.name('var')
    return expr


def correlation(
    left: ir.NumericColumn,
    right: ir.NumericColumn,
    where: ir.BooleanValue | None = None,
    how: Literal['sample', 'pop'] = 'sample',
) -> ir.NumericScalar:
    """Return the correlation of two numeric columns.

    Parameters
    ----------
    left
        Numeric column
    right
        Numeric column
    how
        Population or sample correlation

    Returns
    -------
    NumericScalar
        The correlation of `left` and `right`
    """
    expr = ops.Correlation(left, right, how=how, where=where).to_expr()
    return expr


def covariance(
    left: ir.NumericColumn,
    right: ir.NumericColumn,
    where: ir.BooleanValue | None = None,
    how: Literal['sample', 'pop'] = 'sample',
):
    """Return the covariance of two numeric columns.

    Parameters
    ----------
    left
        Numeric column
    right
        Numeric column
    how
        Population or sample covariance

    Returns
    -------
    NumericScalar
        The covariance of `left` and `right`
    """
    expr = ops.Covariance(left, right, how=how, where=where).to_expr()
    return expr


def bucket(
    arg: ir.NumericValue,
    buckets: Sequence[int],
    closed: Literal['left', 'right'] = 'left',
    close_extreme: bool = True,
    include_under: bool = False,
    include_over: bool = False,
) -> ir.CategoryColumn:
    """
    Compute a discrete binning of a numeric array

    Parameters
    ----------
    arg
        Numeric array expression
    buckets
        List of buckets
    closed
        Which side of each interval is closed. For example:

        ```python
        buckets = [0, 100, 200]
        closed = 'left': 100 falls in 2nd bucket
        closed = 'right': 100 falls in 1st bucket
        ```
    close_extreme
        Whether the extreme values fall in the last bucket

    Returns
    -------
    CategoryColumn
        A categorical column expression
    """
    op = ops.Bucket(
        arg,
        buckets,
        closed=closed,
        close_extreme=close_extreme,
        include_under=include_under,
        include_over=include_over,
    )
    return op.to_expr()


def histogram(
    arg: ir.NumericColumn,
    nbins: int | None = None,
    binwidth: float | None = None,
    base: float | None = None,
    closed: Literal['left', 'right'] = 'left',
    aux_hash: str | None = None,
) -> ir.CategoryColumn:
    """Compute a histogram with fixed width bins.

    Parameters
    ----------
    arg
        Numeric column
    nbins
        If supplied, will be used to compute the binwidth
    binwidth
        If not supplied, computed from the data (actual max and min values)
    base
        Histogram base
    closed
        Which side of each interval is closed
    aux_hash
        Auxiliary hash value to add to bucket names

    Returns
    -------
    CategoryColumn
        Coded value expression
    """
    op = ops.Histogram(
        arg, nbins, binwidth, base, closed=closed, aux_hash=aux_hash
    )
    return op.to_expr()


def category_label(
    arg: ir.CategoryValue,
    labels: Sequence[str],
    nulls: str | None = None,
) -> ir.StringValue:
    """Format a known number of categories as strings.

    Parameters
    ----------
    arg
        A category value
    labels
        Labels to use for formatting categories
    nulls
        How to label any null values among the categories

    Returns
    -------
    StringValue
        Labeled categories
    """
    op = ops.CategoryLabel(arg, labels, nulls)
    return op.to_expr()


_numeric_column_methods = {
    'mean': mean,
    'cummean': cummean,
    'sum': sum,
    'cumsum': cumsum,
    'quantile': quantile,
    'std': std,
    'var': variance,
    'corr': correlation,
    'cov': covariance,
    'bucket': bucket,
    'histogram': histogram,
    'summary': _numeric_summary,
}

_integer_column_methods = {
    'bit_and': bit_and,
    'bit_or': bit_or,
    'bit_xor': bit_xor,
}

_floating_value_methods = {
    'isnan': _unary_op('isnull', ops.IsNan),
    'isinf': _unary_op('isinf', ops.IsInf),
}

_add_methods(ir.NumericValue, _numeric_value_methods)
_add_methods(ir.IntegerValue, _integer_value_methods)
_add_methods(ir.FloatingValue, _floating_value_methods)

_add_methods(ir.NumericColumn, _numeric_column_methods)
_add_methods(ir.IntegerColumn, _integer_column_methods)

# ----------------------------------------------------------------------
# GeoSpatial API


def geo_area(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Compute the area of a geospatial value.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    FloatingValue
        The area of `arg`
    """
    op = ops.GeoArea(arg)
    return op.to_expr()


def geo_as_binary(arg: ir.GeoSpatialValue) -> ir.BinaryValue:
    """Get the geometry as well-known bytes (WKB) without the SRID data.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    BinaryValue
        Binary value
    """
    op = ops.GeoAsBinary(arg)
    return op.to_expr()


def geo_as_ewkt(arg: ir.GeoSpatialValue) -> ir.StringValue:
    """Get the geometry as well-known text (WKT) with the SRID data.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    StringValue
        String value
    """
    op = ops.GeoAsEWKT(arg)
    return op.to_expr()


def geo_as_text(arg: ir.GeoSpatialValue) -> ir.StringValue:
    """Get the geometry as well-known text (WKT) without the SRID data.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    StringValue
        String value
    """
    op = ops.GeoAsText(arg)
    return op.to_expr()


def geo_as_ewkb(arg: ir.GeoSpatialValue) -> ir.BinaryValue:
    """Get the geometry as well-known bytes (WKB) with the SRID data.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    BinaryValue
        WKB value
    """
    op = ops.GeoAsEWKB(arg)
    return op.to_expr()


def geo_contains(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the `left` geometry contains the `right` one.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether left contains right
    """
    op = ops.GeoContains(left, right)
    return op.to_expr()


def geo_contains_properly(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """
    Check if the first geometry contains the second one,
    with no common border points.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether left contains right, properly.
    """
    op = ops.GeoContainsProperly(left, right)
    return op.to_expr()


def geo_covers(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the first geometry covers the second one.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether `left` covers `right`
    """
    op = ops.GeoCovers(left, right)
    return op.to_expr()


def geo_covered_by(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the first geometry is covered by the second one.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether `left` is covered by `right`
    """
    op = ops.GeoCoveredBy(left, right)
    return op.to_expr()


def geo_crosses(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the geometries have at least one interior point in common.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether `left` and `right` have at least one common interior point.
    """
    op = ops.GeoCrosses(left, right)
    return op.to_expr()


def geo_d_fully_within(
    left: ir.GeoSpatialValue,
    right: ir.GeoSpatialValue,
    distance: ir.FloatingValue,
) -> ir.BooleanValue:
    """Check if the `left` is entirely within `distance` from `right`.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry
    distance
        Distance to check

    Returns
    -------
    BooleanValue
        Whether `left` is within a specified distance from `right`.
    """
    op = ops.GeoDFullyWithin(left, right, distance)
    return op.to_expr()


def geo_disjoint(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the geometries have no points in common.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether `left` and `right` are disjoin
    """
    op = ops.GeoDisjoint(left, right)
    return op.to_expr()


def geo_d_within(
    left: ir.GeoSpatialValue,
    right: ir.GeoSpatialValue,
    distance: ir.FloatingValue,
) -> ir.BooleanValue:
    """Check if `left` is partially within `distance` from `right`.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry
    distance
        Distance to check

    Returns
    -------
    BooleanValue
        Whether `left` is partially within `distance` from `right`.
    """
    op = ops.GeoDWithin(left, right, distance)
    return op.to_expr()


def geo_equals(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the geometries are equal.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether `left` equals `right`
    """
    op = ops.GeoEquals(left, right)
    return op.to_expr()


def geo_geometry_n(
    arg: ir.GeoSpatialValue, n: int | ir.IntegerValue
) -> ir.GeoSpatialValue:
    """Get the 1-based Nth geometry of a multi geometry.

    Parameters
    ----------
    arg
        Geometry expression
    n
        Nth geometry index

    Returns
    -------
    GeoSpatialValue
        Geometry value
    """
    op = ops.GeoGeometryN(arg, n)
    return op.to_expr()


def geo_geometry_type(arg: ir.GeoSpatialValue) -> ir.StringValue:
    """Get the type of a geometry.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    StringValue
        String representing the type of `arg`.
    """
    op = ops.GeoGeometryType(arg)
    return op.to_expr()


def geo_intersects(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the geometries share any points.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether `left` intersects `right`
    """
    op = ops.GeoIntersects(left, right)
    return op.to_expr()


def geo_is_valid(arg: ir.GeoSpatialValue) -> ir.BooleanValue:
    """Check if the geometry is valid.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    BooleanValue
        Whether `arg` is valid
    """
    op = ops.GeoIsValid(arg)
    return op.to_expr()


def geo_line_locate_point(
    left: ir.LineStringValue, right: ir.PointValue
) -> ir.FloatingValue:
    """Locate the distance a point falls along the length of a line.

    Returns a float between zero and one representing the location of the
    closest point on the linestring to the given point, as a fraction of the
    total 2d line length.

    Parameters
    ----------
    left
        Linestring geometry
    right
        Point geometry

    Returns
    -------
    FloatingValue
        Fraction of the total line length
    """
    op = ops.GeoLineLocatePoint(left, right)
    return op.to_expr()


def geo_line_merge(arg: ir.GeoSpatialValue) -> ir.GeoSpatialValue:
    """Merge a `MultiLineString` into a `LineString`.

    Returns a (set of) LineString(s) formed by sewing together the
    constituent line work of a MultiLineString. If a geometry other than
    a LineString or MultiLineString is given, this will return an empty
    geometry collection.

    Parameters
    ----------
    arg
        Multiline string

    Returns
    -------
    ir.GeoSpatialValue
        Merged linestrings
    """
    op = ops.GeoLineMerge(arg)
    return op.to_expr()


def geo_line_substring(
    arg: ir.LineStringValue, start: ir.FloatingValue, end: ir.FloatingValue
) -> ir.LineStringValue:
    """Clip a substring from a LineString.

    Returns a linestring that is a substring of the input one, starting
    and ending at the given fractions of the total 2d length. The second
    and third arguments are floating point values between zero and one.
    This only works with linestrings.

    Parameters
    ----------
    arg
        Linestring value
    start
        Start value
    end
        End value

    Returns
    -------
    LineStringValue
        Clipped linestring
    """
    op = ops.GeoLineSubstring(arg, start, end)
    return op.to_expr()


def geo_ordering_equals(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if two geometries are equal and have the same point ordering.

    Returns true if the two geometries are equal and the coordinates
    are in the same order.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether points and orderings are equal.
    """
    op = ops.GeoOrderingEquals(left, right)
    return op.to_expr()


def geo_overlaps(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the geometries share space, have the same dimension, and are
    not completely contained by each other.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Overlaps indicator
    """
    op = ops.GeoOverlaps(left, right)
    return op.to_expr()


def geo_point(
    left: NumericValue | int | float,
    right: NumericValue | int | float,
) -> ir.PointValue:
    """Return a point constructed from the coordinate values.

    Constant coordinates result in construction of a POINT literal.

    Parameters
    ----------
    left
        X coordinate
    right
        Y coordinate

    Returns
    -------
    PointValue
        Points
    """
    op = ops.GeoPoint(left, right)
    return op.to_expr()


def geo_touches(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the geometries have at least one point in common, but do not
    intersect.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether left and right are touching
    """
    op = ops.GeoTouches(left, right)
    return op.to_expr()


def geo_distance(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.FloatingValue:
    """Compute the distance between two geospatial expressions.

    Parameters
    ----------
    left
        Left geometry or geography
    right
        Right geometry or geography

    Returns
    -------
    FloatingValue
        Distance between `left` and `right`
    """
    op = ops.GeoDistance(left, right)
    return op.to_expr()


def geo_length(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Compute the length of a geospatial expression.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    FloatingValue
        Length of `arg`
    """
    op = ops.GeoLength(arg)
    return op.to_expr()


def geo_perimeter(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Compute the perimeter of a geospatial expression.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    FloatingValue
        Perimeter of `arg`
    """
    op = ops.GeoPerimeter(arg)
    return op.to_expr()


def geo_max_distance(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.FloatingValue:
    """Returns the 2-dimensional maximum distance between two geometries in
    projected units.

    If `left` and `right` are the same geometry the function will return the
    distance between the two vertices most far from each other in that
    geometry.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    FloatingValue
        Maximum distance
    """
    op = ops.GeoMaxDistance(left, right)
    return op.to_expr()


def geo_unary_union(arg: ir.GeoSpatialValue) -> ir.GeoSpatialScalar:
    """Aggregate a set of geometries into a union.

    This corresponds to the aggregate version of the PostGIS ST_Union.
    We give it a different name (following the corresponding method
    in GeoPandas) to avoid name conflicts with the non-aggregate version.

    Parameters
    ----------
    arg
        Geometry expression column

    Returns
    -------
    GeoSpatialScalar
        Union of geometries
    """
    expr = ops.GeoUnaryUnion(arg).to_expr()
    expr = expr.name('union')
    return expr


def geo_union(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.GeoSpatialValue:
    """Merge two geometries into a union geometry.

    Returns the pointwise union of the two geometries.
    This corresponds to the non-aggregate version the PostGIS ST_Union.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    GeoSpatialValue
        Union of geometries
    """
    op = ops.GeoUnion(left, right)
    return op.to_expr()


def geo_x(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Return the X coordinate of `arg`, or NULL if not available.

    Input must be a point.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    FloatingValue
        X coordinate of `arg`
    """
    op = ops.GeoX(arg)
    return op.to_expr()


def geo_y(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Return the Y coordinate of `arg`, or NULL if not available.

    Input must be a point.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    FloatingValue
        Y coordinate of `arg`
    """
    op = ops.GeoY(arg)
    return op.to_expr()


def geo_x_min(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Return the X minima of a geometry.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    FloatingValue
        X minima
    """
    op = ops.GeoXMin(arg)
    return op.to_expr()


def geo_x_max(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Return the X maxima of a geometry.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    FloatingValue
        X maxima
    """
    op = ops.GeoXMax(arg)
    return op.to_expr()


def geo_y_min(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Return the Y minima of a geometry.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    FloatingValue
        Y minima
    """
    op = ops.GeoYMin(arg)
    return op.to_expr()


def geo_y_max(arg: ir.GeoSpatialValue) -> ir.FloatingValue:
    """Return the Y maxima of a geometry.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    FloatingValue
        Y maxima
    YMax : double scalar
    """
    op = ops.GeoYMax(arg)
    return op.to_expr()


def geo_start_point(arg: ir.GeoSpatialValue) -> ir.PointValue:
    """Return the first point of a `LINESTRING` geometry as a `POINT`.

    Return NULL if the input parameter is not a `LINESTRING`

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    PointValue
        Start point
    """
    op = ops.GeoStartPoint(arg)
    return op.to_expr()


def geo_end_point(arg: ir.GeoSpatialValue) -> ir.PointValue:
    """Return the last point of a `LINESTRING` geometry as a `POINT`.

    Return NULL if the input parameter is not a LINESTRING

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    PointValue
        End point
    """
    op = ops.GeoEndPoint(arg)
    return op.to_expr()


def geo_point_n(arg: ir.GeoSpatialValue, n: ir.IntegerValue) -> ir.PointValue:
    """Return the Nth point in a single linestring in the geometry.
    Negative values are counted backwards from the end of the LineString,
    so that -1 is the last point. Returns NULL if there is no linestring in
    the geometry

    Parameters
    ----------
    arg
        Geometry expression
    n
        Nth point index

    Returns
    -------
    PointValue
        Nth point in `arg`
    """
    op = ops.GeoPointN(arg, n)
    return op.to_expr()


def geo_n_points(arg: ir.GeoSpatialValue) -> ir.IntegerValue:
    """Return the number of points in a geometry. Works for all geometries

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    IntegerValue
        Number of points
    """
    op = ops.GeoNPoints(arg)
    return op.to_expr()


def geo_n_rings(arg: ir.GeoSpatialValue) -> ir.IntegerValue:
    """Return the number of rings for polygons and multipolygons.

    Outer rings are counted as well.

    Parameters
    ----------
    arg
        Geometry or geography

    Returns
    -------
    IntegerValue
        Number of rings
    """
    op = ops.GeoNRings(arg)
    return op.to_expr()


def geo_srid(arg: ir.GeoSpatialValue) -> ir.IntegerValue:
    """Return the spatial reference identifier for the ST_Geometry.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    IntegerValue
        SRID
    """
    op = ops.GeoSRID(arg)
    return op.to_expr()


def geo_set_srid(
    arg: ir.GeoSpatialValue, srid: ir.IntegerValue
) -> ir.GeoSpatialValue:
    """Set the spatial reference identifier for the ST_Geometry

    Parameters
    ----------
    arg
        Geometry expression
    srid
        SRID integer value

    Returns
    -------
    GeoSpatialValue
        `arg` with SRID set to `srid`
    """
    op = ops.GeoSetSRID(arg, srid)
    return op.to_expr()


def geo_buffer(
    arg: ir.GeoSpatialValue, radius: float | ir.FloatingValue
) -> ir.GeoSpatialValue:
    """Returns a geometry that represents all points whose distance from this
    Geometry is less than or equal to distance. Calculations are in the
    Spatial Reference System of this Geometry.

    Parameters
    ----------
    arg
        Geometry expression
    radius
        Floating expression

    Returns
    -------
    ir.GeoSpatialValue
        Geometry expression
    """
    op = ops.GeoBuffer(arg, radius)
    return op.to_expr()


def geo_centroid(arg: ir.GeoSpatialValue) -> ir.PointValue:
    """Returns the centroid of the geometry.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    PointValue
        The centroid
    """
    op = ops.GeoCentroid(arg)
    return op.to_expr()


def geo_envelope(arg: ir.GeoSpatialValue) -> ir.PolygonValue:
    """Returns a geometry representing the bounding box of the arg.

    Parameters
    ----------
    arg
        Geometry expression

    Returns
    -------
    PolygonValue
        A polygon
    """
    op = ops.GeoEnvelope(arg)
    return op.to_expr()


def geo_within(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.BooleanValue:
    """Check if the first geometry is completely inside of the second.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    BooleanValue
        Whether `left` is in `right`.
    """
    op = ops.GeoWithin(left, right)
    return op.to_expr()


def geo_azimuth(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.FloatingValue:
    """Return the angle in radians from the horizontal of the vector defined by
    `left` and `right`.

    Angle is computed clockwise from down-to-up on the clock:
    12=0; 3=PI/2; 6=PI; 9=3PI/2.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    FloatingValue
        azimuth
    """
    op = ops.GeoAzimuth(left, right)
    return op.to_expr()


def geo_intersection(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.GeoSpatialValue:
    """Return the intersection of two geometries.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    GeoSpatialValue
        Intersection of `left` and `right`
    """
    op = ops.GeoIntersection(left, right)
    return op.to_expr()


def geo_difference(
    left: ir.GeoSpatialValue, right: ir.GeoSpatialValue
) -> ir.GeoSpatialValue:
    """Return the difference of two geometries.

    Parameters
    ----------
    left
        Left geometry
    right
        Right geometry

    Returns
    -------
    GeoSpatialValue
        Difference of `left` and `right`
    """
    op = ops.GeoDifference(left, right)
    return op.to_expr()


def geo_simplify(
    arg: ir.GeoSpatialValue,
    tolerance: ir.FloatingValue,
    preserve_collapsed: ir.BooleanValue,
) -> ir.GeoSpatialValue:
    """Simplify a given geometry.

    Parameters
    ----------
    arg
        Geometry expression
    tolerance
        Tolerance
    preserve_collapsed
        Whether to preserve collapsed geometries

    Returns
    -------
    GeoSpatialValue
        Simplified geometry
    """
    op = ops.GeoSimplify(arg, tolerance, preserve_collapsed)
    return op.to_expr()


def geo_transform(
    arg: ir.GeoSpatialValue, srid: ir.IntegerValue
) -> ir.GeoSpatialValue:
    """Transform a geometry into a new SRID.

    Parameters
    ----------
    arg
        Geometry expression
    srid
        Integer expression

    Returns
    -------
    GeoSpatialValue
        Transformed geometry
    """
    op = ops.GeoTransform(arg, srid)
    return op.to_expr()


_geospatial_value_methods = {
    'area': geo_area,
    'as_binary': geo_as_binary,
    'as_ewkb': geo_as_ewkb,
    'as_ewkt': geo_as_ewkt,
    'as_text': geo_as_text,
    'azimuth': geo_azimuth,
    'buffer': geo_buffer,
    'centroid': geo_centroid,
    'contains': geo_contains,
    'contains_properly': geo_contains_properly,
    'covers': geo_covers,
    'covered_by': geo_covered_by,
    'crosses': geo_crosses,
    'd_fully_within': geo_d_fully_within,
    'difference': geo_difference,
    'disjoint': geo_disjoint,
    'distance': geo_distance,
    'd_within': geo_d_within,
    'end_point': geo_end_point,
    'envelope': geo_envelope,
    'geo_equals': geo_equals,
    'geometry_n': geo_geometry_n,
    'geometry_type': geo_geometry_type,
    'intersection': geo_intersection,
    'intersects': geo_intersects,
    'is_valid': geo_is_valid,
    'line_locate_point': geo_line_locate_point,
    'line_merge': geo_line_merge,
    'line_substring': geo_line_substring,
    'length': geo_length,
    'max_distance': geo_max_distance,
    'n_points': geo_n_points,
    'n_rings': geo_n_rings,
    'ordering_equals': geo_ordering_equals,
    'overlaps': geo_overlaps,
    'perimeter': geo_perimeter,
    'point_n': geo_point_n,
    'set_srid': geo_set_srid,
    'simplify': geo_simplify,
    'srid': geo_srid,
    'start_point': geo_start_point,
    'touches': geo_touches,
    'transform': geo_transform,
    'union': geo_union,
    'within': geo_within,
    'x': geo_x,
    'x_max': geo_x_max,
    'x_min': geo_x_min,
    'y': geo_y,
    'y_max': geo_y_max,
    'y_min': geo_y_min,
}
_geospatial_column_methods = {'unary_union': geo_unary_union}

_add_methods(ir.GeoSpatialValue, _geospatial_value_methods)
_add_methods(ir.GeoSpatialColumn, _geospatial_column_methods)

# ----------------------------------------------------------------------
# Boolean API


# TODO: logical binary operators for BooleanValue


def ifelse(
    arg: ir.ValueExpr, true_expr: ir.ValueExpr, false_expr: ir.ValueExpr
) -> ir.ValueExpr:
    """Construct a ternary conditional expression.

    Examples
    --------
    bool_expr.ifelse(0, 1)
    e.g., in SQL: CASE WHEN bool_expr THEN 0 else 1 END

    Returns
    -------
    ValueExpr
        The value of `true_expr` if `arg` is `True` else `false_expr`
    """
    # Result will be the result of promotion of true/false exprs. These
    # might be conflicting types; same type resolution as case expressions
    # must be used.
    case = bl.SearchedCaseBuilder()
    return case.when(arg, true_expr).else_(false_expr).end()


_boolean_value_methods = {
    'ifelse': ifelse,
    '__and__': _boolean_binary_op('__and__', ops.And),
    '__or__': _boolean_binary_op('__or__', ops.Or),
    '__xor__': _boolean_binary_op('__xor__', ops.Xor),
    '__rand__': _boolean_binary_rop('__rand__', ops.And),
    '__ror__': _boolean_binary_rop('__ror__', ops.Or),
    '__rxor__': _boolean_binary_rop('__rxor__', ops.Xor),
    '__invert__': _boolean_unary_op('__invert__', ops.Not),
}


_boolean_column_methods = {
    'any': _unary_op('any', ops.Any),
    'notany': _unary_op('notany', ops.NotAny),
    'all': _unary_op('all', ops.All),
    'notall': _unary_op('notany', ops.NotAll),
    'cumany': _unary_op('cumany', ops.CumulativeAny),
    'cumall': _unary_op('cumall', ops.CumulativeAll),
}


_add_methods(ir.BooleanValue, _boolean_value_methods)
_add_methods(ir.BooleanColumn, _boolean_column_methods)


# ---------------------------------------------------------------------
# Binary API


def hashbytes(
    arg: ir.BinaryValue | ir.StringValue,
    how: Literal['md5', 'sha1', 'sha256', 'sha512'] = 'sha256',
) -> ir.BinaryValue:
    """Compute the binary hash value of `arg`.

    Parameters
    ----------
    arg
        Expression to hash
    how
        Hash algorithm to use

    Returns
    -------
    BinaryValue
        Binary expression
    """
    return ops.HashBytes(arg, how).to_expr()


_binary_value_methods = {'hashbytes': hashbytes}
_add_methods(ir.BinaryValue, _binary_value_methods)


# ---------------------------------------------------------------------
# String API


def _string_substr(
    self: ir.StringValue,
    start: int | ir.IntegerValue,
    length: int | ir.IntegerValue | None = None,
) -> ir.StringValue:
    """Pull substrings out by position and maximum length.

    Parameters
    ----------
    self
        String expression
    start
        First character to start splitting, indices start at 0
    length
        Maximum length of each substring. If not supplied, searches the entire
        string

    Returns
    -------
    StringValue
        Found substring
    """
    op = ops.Substring(self, start, length)
    return op.to_expr()


def _string_left(
    self: ir.StringValue, nchars: int | ir.IntegerValue
) -> ir.StringValue:
    """Return the `nchars` left-most characters each string in `arg`.

    Parameters
    ----------
    self
        String expression
    nchars
        Maximum number of characters to return

    Returns
    -------
    StringValue
        Characters
    """
    return self.substr(0, length=nchars)


def _string_right(
    self: ir.StringValue, nchars: int | ir.IntegerValue
) -> ir.StringValue:
    """Return up to `nchars` from the end of each string in `arg`.

    Parameters
    ----------
    self
        String expression
    nchars
        Maximum number of characters to return

    Returns
    -------
    StringValue
        Characters
    """
    return ops.StrRight(self, nchars).to_expr()


def repeat(self: ir.StringValue, n: int | ir.IntegerValue) -> ir.StringValue:
    """Repeat the string `self` `n` times.

    Parameters
    ----------
    self
        String to repeat
    n
        Number of repetitions

    Returns
    -------
    StringValue
        Repeated string
    """
    return ops.Repeat(self, n).to_expr()


def _translate(
    self: ir.StringValue, from_str: ir.StringValue, to_str: ir.StringValue
) -> ir.StringValue:
    """Replace `from_str` characters in `self` characters in `to_str`.

    To avoid unexpected behavior, `from_str` should be shorter than `to_str`.

    Parameters
    ----------
    self
        String expression
    from_str
        Characters in `arg` to replace
    to_str
        Characters to use for replacement

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('string_col', 'string')])
    >>> expr = table.string_col.translate('a', 'b')
    >>> expr = table.string_col.translate('a', 'bc')

    Returns
    -------
    StringValue
        Translated string
    """
    return ops.Translate(self, from_str, to_str).to_expr()


def _string_find(
    self: ir.StringValue,
    substr: str | ir.StringValue,
    start: int | ir.IntegerValue | None = None,
    end: int | ir.IntegerValue | None = None,
) -> ir.IntegerValue:
    """Return the position of the first occurence of substring.

    Parameters
    ----------
    self
        String expression
    substr
        Substring to search for
    start
        Zero based index of where to start the search
    end
        Zero based index of where to stop the search. Currently not
        implemented.

    Returns
    -------
    IntegerValue
        Position of `substr` in `arg` starting from `start`
    """
    if end is not None:
        raise NotImplementedError
    return ops.StringFind(self, substr, start, end).to_expr()


def _lpad(
    self: ir.StringValue,
    length: int | ir.IntegerValue,
    pad: str | ir.StringValue = ' ',
) -> ir.StringValue:
    """Pad `arg` by truncating on the right or padding on the left.

    Parameters
    ----------
    self
        String to pad
    length : int
        Length of output string
    pad
        Pad character

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('strings', 'string')])
    >>> expr = table.strings.lpad(5, '-')
    >>> expr = ibis.literal('a').lpad(5, '-')  # 'a' becomes '----a'
    >>> expr = ibis.literal('abcdefg').lpad(5, '-')  # 'abcdefg' becomes 'abcde'  # noqa: E501

    Returns
    -------
    StringValue
        Padded string
    """
    return ops.LPad(self, length, pad).to_expr()


def _rpad(
    self: ir.StringValue,
    length: int | ir.IntegerValue,
    pad: str | ir.StringValue = ' ',
) -> ir.StringValue:
    """Pad `self` by truncating or padding on the right.

    Parameters
    ----------
    self
        String to pad
    length : int
        Length of output string
    pad
        Pad character

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('string_col', 'string')])
    >>> expr = table.string_col.rpad(5, '-')
    >>> expr = ibis.literal('a').rpad(5, '-')  # 'a' becomes 'a----'
    >>> expr = ibis.literal('abcdefg').rpad(5, '-')  # 'abcdefg' becomes 'abcde'  # noqa: E501

    Returns
    -------
    StringValue
        Padded string
    """
    return ops.RPad(self, length, pad).to_expr()


def _find_in_set(
    self: ir.StringValue, str_list: Sequence[str]
) -> ir.IntegerValue:
    """Find the first occurence of `str_list` within a list of strings.

    No string in list can have a comma.

    Parameters
    ----------
    self
        String expression to search
    str_list
        Sequence of strings

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('strings', 'string')])
    >>> result = table.strings.find_in_set(['a', 'b'])

    Returns
    -------
    IntegerValue
        Position of `str_list` in `arg`. Returns -1 if `arg` isn't found or if
        `arg` contains `','`.
    """
    return ops.FindInSet(self, str_list).to_expr()


def _string_join(
    self: str | ir.StringValue, strings: Sequence[str]
) -> ir.StringValue:
    """Join a list of strings using the `self` as the separator.

    Parameters
    ----------
    self
        String expression
    strings
        Strings to join with `arg`

    Examples
    --------
    >>> import ibis
    >>> sep = ibis.literal(',')
    >>> result = sep.join(['a', 'b', 'c'])

    Returns
    -------
    StringValue
        Joined string
    """
    return ops.StringJoin(self, strings).to_expr()


def _startswith(
    self: str | ir.StringValue, start: str | ir.StringValue
) -> ir.BooleanValue:
    """Determine whether `self` starts with `end`.

    Parameters
    ----------
    self
        String expression
    start
        prefix to check for

    Examples
    --------
    >>> import ibis
    >>> text = ibis.literal('Ibis project')
    >>> text.startswith('Ibis')

    Returns
    -------
    BooleanValue
        Boolean indicating whether `self` starts with `start`
    """
    return ops.StartsWith(self, start).to_expr()


def _endswith(
    self: str | ir.StringValue, end: str | ir.StringValue
) -> ir.BooleanValue:
    """Determine if `self` ends with `end`.

    Parameters
    ----------
    self
        String expression
    end
        Suffix to check for

    Examples
    --------
    >>> import ibis
    >>> text = ibis.literal('Ibis project')
    >>> text.endswith('project')

    Returns
    -------
    BooleanValue
        Boolean indicating whether `self` ends with `end`
    """
    return ops.EndsWith(self, end).to_expr()


def _string_like(
    self: ir.StringValue,
    patterns: str | ir.StringValue | Sequence[str | ir.StringValue],
) -> ir.BooleanValue:
    """Match `patterns` against `self`, case-sensitive.

    This function is modeled after the SQL `LIKE` directive. Use `%` as a
    multiple-character wildcard or `_` as a single-character wildcard.

    Use `re_search` or `rlike` for regular expression-based matching.

    Parameters
    ----------
    self
        String expression
    patterns
        If `pattern` is a list, then if any pattern matches the input then
        the corresponding row in the output is `True`.

    Returns
    -------
    BooleanValue
        Column indicating matches
    """
    return functools.reduce(
        operator.or_,
        (
            ops.StringSQLLike(self, pattern).to_expr()
            for pattern in util.promote_list(patterns)
        ),
    )


def _string_ilike(
    self: ir.StringValue,
    patterns: str | ir.StringValue | Sequence[str | ir.StringValue],
) -> ir.BooleanValue:
    """Match `patterns` against `self`, case-insensitive.

    This function is modeled after the SQL `ILIKE` directive. Use `%` as a
    multiple-character wildcard or `_` as a single-character wildcard.

    Use `re_search` or `rlike` for regular expression-based matching.

    Parameters
    ----------
    self
        String expression
    patterns
        If `pattern` is a list, then if any pattern matches the input then
        the corresponding row in the output is `True`.

    Returns
    -------
    BooleanValue
        Column indicating matches
    """
    return functools.reduce(
        operator.or_,
        (
            ops.StringSQLILike(self, pattern).to_expr()
            for pattern in util.promote_list(patterns)
        ),
    )


def re_search(
    arg: str | ir.StringValue, pattern: str | ir.StringValue
) -> ir.BooleanValue:
    """Return whether the values in `arg` match `pattern`.

    Returns `True` if the regex matches a string and `False` otherwise.

    Parameters
    ----------
    arg
        String expression to check for matches
    pattern
        Regular expression use for searching

    Returns
    -------
    BooleanValue
        Indicator of matches
    """
    return ops.RegexSearch(arg, pattern).to_expr()


def regex_extract(
    arg: str | ir.StringValue,
    pattern: str | ir.StringValue,
    index: int | ir.IntegerValue,
) -> ir.StringValue:
    """Return the specified match from a regular expression `pattern`.

    Parameters
    ----------
    arg
        String expression
    pattern
        Reguar expression string
    index
        Zero-based index of match to return

    Returns
    -------
    StringValue
        Extracted match
    """
    return ops.RegexExtract(arg, pattern, index).to_expr()


def regex_replace(
    arg: str | ir.StringValue,
    pattern: str | ir.StringValue,
    replacement: str | ir.StringValue,
) -> ir.StringValue:
    """Replace match found by regex `pattern` with `replacement`.

    `replacement` can also be a regex

    Parameters
    ----------
    arg
        String expression
    pattern
        Regular expression string
    replacement
        Replacement string; can be a regular expression

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('strings', 'string')])
    >>> result = table.strings.replace('(b+)', r'<\1>')  # 'aaabbbaa' becomes 'aaa<bbb>aaa'  # noqa: E501

    Returns
    -------
    StringValue
        Modified string
    """
    return ops.RegexReplace(arg, pattern, replacement).to_expr()


def _string_replace(
    arg: str | ir.StringValue,
    pattern: ir.StringValue,
    replacement: ir.StringValue,
) -> ir.StringValue:
    """Replace each exact match of `pattern` with `replacement`.
    string.

    Like Python built-in [`str.replace`][str.replace]

    Parameters
    ----------
    arg
        String expression
    pattern
        String pattern
    replacement
        String replacement

    Examples
    --------
    >>> import ibis
    >>> table = ibis.table([('strings', 'string')])
    >>> result = table.strings.replace('aaa', 'foo')  # 'aaabbbaaa' becomes 'foobbbfoo'  # noqa: E501

    Returns
    -------
    StringVulae
        Replaced string
    """
    return ops.StringReplace(arg, pattern, replacement).to_expr()


def to_timestamp(
    arg: ir.StringValue, format_str: str, timezone: str | None = None
) -> ir.TimestampValue:
    """Parse a string and return a timestamp.

    Parameters
    ----------
    format_str
        Format string in `strptime` format
    timezone
        A string indicating the timezone. For example `'America/New_York'`

    Examples
    --------
    >>> import ibis
    >>> date_as_str = ibis.literal('20170206')
    >>> result = date_as_str.to_timestamp('%Y%m%d')

    Returns
    -------
    TimestampValue
        Parsed timestamp value
    """
    return ops.StringToTimestamp(arg, format_str, timezone).to_expr()


def parse_url(
    arg: str | ir.StringValue,
    extract: Literal[
        "PROTOCOL",
        "HOST",
        "PATH",
        "REF",
        "AUTHORITY",
        "FILE",
        "USERINFO",
        "QUERY",
    ],
    key: str | None = None,
) -> ir.StringValue:
    """Parse a URL and extract its components.

    `key` can be used to extract query values when `extract == 'QUERY'`

    Parameters
    ----------
    arg
        URL to extract from
    extract : str
        Component of URL to extract
    key
        Query component to extract

    Examples
    --------
    >>> url = "https://www.youtube.com/watch?v=kEuEcWfewf8&t=10"
    >>> parse_url(url, 'QUERY', 'v')  # doctest: +SKIP
    'kEuEcWfewf8'

    Returns
    -------
    StringValue
        Extracted string value
    """
    return ops.ParseURL(arg, extract, key).to_expr()


def _string_contains(
    arg: str | ir.StringValue, substr: str | ir.StringValue
) -> ir.BooleanValue:
    """Determine if `arg` contains `substr`.

    Parameters
    ----------
    arg
        String value expression
    substr
        Substring to check `arg` for

    Returns
    -------
    BooleanValue
        Boolean value indicating the presence of `substr` in `arg`
    """
    return arg.find(substr) >= 0


def _string_split(
    arg: str | ir.StringValue, delimiter: str | ir.StringValue
) -> ir.ArrayValue:
    """Split `arg` on `delimiter`.

    Parameters
    ----------
    arg
        String value to split
    delimiter
        Value to split by

    Returns
    -------
    ArrayValue
        The string `arg` split by `delimiter`
    """
    return ops.StringSplit(arg, delimiter).to_expr()


def _string_concat(*args):
    return ops.StringConcat(args).to_expr()


def _string_dunder_contains(arg, substr):
    raise TypeError('Use val.contains(arg)')


def _string_getitem(
    self: str | ir.StringValue, key: slice | int
) -> ir.StringValue:
    if isinstance(key, slice):
        start, stop, step = key.start, key.stop, key.step

        if step is not None and not isinstance(step, ir.Expr) and step != 1:
            raise ValueError('Step can only be 1')

        if not isinstance(start, ir.Expr):
            if start is not None and start < 0:
                raise ValueError(
                    'Negative slicing not yet supported, got start value of '
                    '{:d}'.format(start)
                )
            if start is None:
                start = 0

        if not isinstance(stop, ir.Expr):
            if stop is not None and stop < 0:
                raise ValueError(
                    'Negative slicing not yet supported, got stop value of '
                    '{:d}'.format(stop)
                )
            if stop is None:
                stop = self.length()

        return self.substr(start, stop - start)
    elif isinstance(key, int):
        return self.substr(key, 1)
    raise NotImplementedError(f'string __getitem__[{type(key).__name__}]')


_string_value_methods = {
    '__getitem__': _string_getitem,
    'length': _unary_op('length', ops.StringLength),
    'lower': _unary_op('lower', ops.Lowercase),
    'upper': _unary_op('upper', ops.Uppercase),
    'reverse': _unary_op('reverse', ops.Reverse),
    'ascii_str': _unary_op('ascii', ops.StringAscii),
    'strip': _unary_op('strip', ops.Strip),
    'lstrip': _unary_op('lstrip', ops.LStrip),
    'rstrip': _unary_op('rstrip', ops.RStrip),
    'capitalize': _unary_op('initcap', ops.Capitalize),
    'convert_base': convert_base,
    '__contains__': _string_dunder_contains,
    'contains': _string_contains,
    'hashbytes': hashbytes,
    'like': _string_like,
    'ilike': _string_ilike,
    'rlike': re_search,
    'replace': _string_replace,
    're_search': re_search,
    're_extract': regex_extract,
    're_replace': regex_replace,
    'to_timestamp': to_timestamp,
    'parse_url': parse_url,
    'substr': _string_substr,
    'left': _string_left,
    'right': _string_right,
    'repeat': repeat,
    'find': _string_find,
    'translate': _translate,
    'find_in_set': _find_in_set,
    'split': _string_split,
    'join': _string_join,
    'startswith': _startswith,
    'endswith': _endswith,
    'lpad': _lpad,
    'rpad': _rpad,
    '__add__': _string_concat,
    '__radd__': lambda *args: _string_concat(*args[::-1]),
    '__mul__': mul,
    '__rmul__': mul,
}


_add_methods(ir.StringValue, _string_value_methods)


# ---------------------------------------------------------------------
# Array API


def _array_slice(
    array: ir.ArrayValue, index: int | ir.IntegerValue | slice
) -> ir.ValueExpr:
    """Slice or index `array` at `index`.

    Parameters
    ----------
    array
        Array expression
    index
        Indexer into `array`

    Returns
    -------
    ibis.expr.types.ValueExpr
        If `index` is an ``int`` or :class:`~ibis.expr.types.IntegerValue` then
        the return type is the element type of `array`. If `index` is a
        ``slice`` then the return type is the same type as the input.
    """
    if isinstance(index, slice):
        start = index.start
        stop = index.stop
        step = index.step

        if step is not None and step != 1:
            raise NotImplementedError('step can only be 1')

        op = ops.ArraySlice(array, start if start is not None else 0, stop)
    else:
        op = ops.ArrayIndex(array, index)
    return op.to_expr()


_array_column_methods = {
    'length': _unary_op('length', ops.ArrayLength),
    '__getitem__': _array_slice,
    '__add__': _binop_expr('__add__', ops.ArrayConcat),
    '__radd__': toolz.flip(_binop_expr('__radd__', ops.ArrayConcat)),
    '__mul__': _binop_expr('__mul__', ops.ArrayRepeat),
    '__rmul__': _binop_expr('__rmul__', ops.ArrayRepeat),
}

_add_methods(ir.ArrayValue, _array_column_methods)


# ---------------------------------------------------------------------
# Map API


def get(
    expr: ir.MapValue, key: ir.ValueExpr, default: ir.ValueExpr | None = None
) -> ir.ValueExpr:
    """Return the value for `key` from `expr`, or the default if `key` is not in the map.

    Parameters
    ----------
    expr
        A map expression
    key
        Expression to use for key
    default
        Expression to return if `key` is not a key in `expr`
    """  # noqa: E501
    return ops.MapValueOrDefaultForKey(expr, key, default).to_expr()


_map_column_methods = {
    'get': get,
    'length': _unary_op('length', ops.MapLength),
    '__getitem__': _binop_expr('__getitem__', ops.MapValueForKey),
    'keys': _unary_op('keys', ops.MapKeys),
    'values': _unary_op('values', ops.MapValues),
    '__add__': _binop_expr('__add__', ops.MapConcat),
    '__radd__': toolz.flip(_binop_expr('__radd__', ops.MapConcat)),
}

_add_methods(ir.MapValue, _map_column_methods)

# ---------------------------------------------------------------------
# Struct API


def _struct_get_field(expr: StructValue, field_name: str) -> ValueExpr:
    """Extract the `field_name` field from the ``StructValue`` expression `expr`.

    Parameters
    ----------
    expr
        A struct valued expression
    field_name
        The name of the field to access from the ``Struct`` typed expression
        `expr`. Must be a Python ``str`` type; programmatic struct field
        access is not yet supported.

    Examples
    --------
    >>> import ibis
    >>> from collections import OrderedDict
    >>> struct_expr = ibis.literal(
    ...     OrderedDict([("fruit", "pear"), ("weight", 0)])
    ... )
    >>> struct_expr['fruit']  # doctest: +NORMALIZE_WHITESPACE
    fruit = StructField[string]
      Literal[struct<fruit: string, weight: int8>]
        OrderedDict([('fruit', 'pear'), ('weight', 0)])
      field:
        fruit

    Returns
    -------
    ValueExpr
        An expression with the type of the field being accessed.
    """
    return ops.StructField(expr, field_name).to_expr().name(field_name)


def _destructure(expr: StructValue) -> DestructValue:
    """Destructure a ``StructValue`` into a corresponding ``DestructValue``.

    Each subclass of ``StructValue`` will be destructed accordingly. For
    example, a ``StructColumn`` will be destructed into a ``DestructColumn``.

    When assigned, a destruct column will destructured and assigned to multiple
    columns.

    Parameters
    ----------
    expr
        The struct column to destructure.

    Returns
    -------
    DestructValue
        A destruct value expression.
    """
    # Set name to empty string here so that we can detect and error when
    # user set name for a destruct column.
    if isinstance(expr, StructScalar):
        return DestructScalar(expr._arg, expr._dtype).name("")
    elif isinstance(expr, StructColumn):
        return DestructColumn(expr._arg, expr._dtype).name("")
    elif isinstance(expr, StructValue):
        return DestructValue(expr._arg, expr._dtype).name("")
    else:
        raise AssertionError()


_struct_value_methods = {
    'destructure': _destructure,
    '__getitem__': _struct_get_field,
}

_add_methods(ir.StructValue, _struct_value_methods)


# ---------------------------------------------------------------------
# Timestamp API


def _timestamp_truncate(
    arg: ir.TimestampValue,
    unit: Literal["Y", "Q", "M", "W", "D", "h", "m", "s", "ms", "us", "ns"],
) -> ir.TimestampValue:
    """Truncate `arg` to units of `unit`.

    Parameters
    ----------
    arg
        Timestamp expression
    unit
        Unit to truncate to

    Returns
    -------
    TimestampValue
        Truncated timestamp expression
    """
    return ops.TimestampTruncate(arg, unit).to_expr()


def _timestamp_strftime(
    arg: ir.TimestampValue, format_str: str
) -> ir.StringValue:
    """Format timestamp according to the passed format string.

    Format string may depend on backend, but we try to conform to ANSI
    `strftime`.

    Parameters
    ----------
    arg
        Timestamp expression
    format_str
        `strftime` format string

    Returns
    -------
    StringValue
        Formatted version of `arg`
    """
    return ops.Strftime(arg, format_str).to_expr()


def _timestamp_time(arg: ir.TimestampValue) -> ir.TimeValue:
    """Return the time component of `arg`.

    Parameters
    ----------
    arg
        A timestamp expression

    Returns
    -------
    TimeValue
        The time component of `arg`
    """
    return ops.Time(arg).to_expr()


def _timestamp_date(arg: ir.TimestampValue) -> ir.DateValue:
    """Return the date component of `arg`.

    Parameters
    ----------
    arg
        A timestamp expression

    Returns
    -------
    DateValue
        The date component of `arg`
    """
    return ops.Date(arg).to_expr()


def _timestamp_sub(left, right):
    right = rlz.any(right)

    if isinstance(right, ir.TimestampValue):
        op = ops.TimestampDiff(left, right)
    else:
        op = ops.TimestampSub(left, right)  # let the operation validate

    return op.to_expr()


_timestamp_add = _binop_expr('__add__', ops.TimestampAdd)
_timestamp_radd = _binop_expr('__radd__', ops.TimestampAdd)


_day_of_week = property(
    lambda self: ops.DayOfWeekNode(self).to_expr(),
    doc="""\
Return a namespace containing methods for extracting day of week information.

Returns
-------
DayOfWeek
    An namespace expression containing methods to use to extract information.
""",
)


_timestamp_value_methods = {
    'strftime': _timestamp_strftime,
    'year': _extract_field('year', ops.ExtractYear),
    'month': _extract_field('month', ops.ExtractMonth),
    'day': _extract_field('day', ops.ExtractDay),
    'day_of_week': _day_of_week,
    'day_of_year': _extract_field('day_of_year', ops.ExtractDayOfYear),
    'quarter': _extract_field('quarter', ops.ExtractQuarter),
    'epoch_seconds': _extract_field('epoch', ops.ExtractEpochSeconds),
    'week_of_year': _extract_field('week_of_year', ops.ExtractWeekOfYear),
    'hour': _extract_field('hour', ops.ExtractHour),
    'minute': _extract_field('minute', ops.ExtractMinute),
    'second': _extract_field('second', ops.ExtractSecond),
    'millisecond': _extract_field('millisecond', ops.ExtractMillisecond),
    'truncate': _timestamp_truncate,
    'time': _timestamp_time,
    'date': _timestamp_date,
    '__sub__': _timestamp_sub,
    'sub': _timestamp_sub,
    '__add__': _timestamp_add,
    'add': _timestamp_add,
    '__radd__': _timestamp_radd,
    'radd': _timestamp_radd,
    '__rsub__': _timestamp_sub,
    'rsub': _timestamp_sub,
}

_add_methods(ir.TimestampValue, _timestamp_value_methods)


# ---------------------------------------------------------------------
# Date API


def _date_truncate(
    arg: ir.DateValue, unit: Literal["Y", "Q", "M", "W", "D"]
) -> ir.DateValue:
    """Truncate date expression `arg` to unit `unit`.

    Parameters
    ----------
    arg
        Date value expression
    unit
        Unit to truncate `arg` to

    Returns
    -------
    DateValue
        Truncated date value expression
    """
    return ops.DateTruncate(arg, unit).to_expr()


def _date_sub(left, right):
    right = rlz.one_of([rlz.date, rlz.interval], right)

    if isinstance(right, ir.DateValue):
        op = ops.DateDiff(left, right)
    else:
        op = ops.DateSub(left, right)  # let the operation validate

    return op.to_expr()


_date_add = _binop_expr('__add__', ops.DateAdd)

_date_value_methods = {
    'strftime': _timestamp_strftime,
    'year': _extract_field('year', ops.ExtractYear),
    'month': _extract_field('month', ops.ExtractMonth),
    'day': _extract_field('day', ops.ExtractDay),
    'day_of_week': _day_of_week,
    'day_of_year': _extract_field('day_of_year', ops.ExtractDayOfYear),
    'quarter': _extract_field('quarter', ops.ExtractQuarter),
    'epoch_seconds': _extract_field('epoch', ops.ExtractEpochSeconds),
    'week_of_year': _extract_field('week_of_year', ops.ExtractWeekOfYear),
    'truncate': _date_truncate,
    '__sub__': _date_sub,
    'sub': _date_sub,
    '__rsub__': _date_sub,
    'rsub': _date_sub,
    '__add__': _date_add,
    'add': _date_add,
    '__radd__': _date_add,
    'radd': _date_add,
}

_add_methods(ir.DateValue, _date_value_methods)


def _to_unit(arg, target_unit):
    if arg._dtype.unit != target_unit:
        arg = util.convert_unit(arg, arg._dtype.unit, target_unit)
        arg.type().unit = target_unit
    return arg


def _interval_property(target_unit, name):
    return property(
        functools.partial(_to_unit, target_unit=target_unit),
        doc=f"""Extract the number of {name}s from an IntervalValue expression.

Returns
-------
IntegerValue
    The number of {name}s in the expression
""",
    )


_interval_add = _binop_expr('__add__', ops.IntervalAdd)
_interval_radd = _binop_expr('__radd__', ops.IntervalAdd)
_interval_sub = _binop_expr('__sub__', ops.IntervalSubtract)
_interval_mul = _binop_expr('__mul__', ops.IntervalMultiply)
_interval_rmul = _binop_expr('__rmul__', ops.IntervalMultiply)
_interval_floordiv = _binop_expr('__floordiv__', ops.IntervalFloorDivide)

_interval_value_methods = {
    'to_unit': _to_unit,
    'years': _interval_property('Y', 'year'),
    'quarters': _interval_property('Q', 'quarter'),
    'months': _interval_property('M', 'month'),
    'weeks': _interval_property('W', 'week'),
    'days': _interval_property('D', 'day'),
    'hours': _interval_property('h', 'hour'),
    'minutes': _interval_property('m', 'minute'),
    'seconds': _interval_property('s', 'second'),
    'milliseconds': _interval_property('ms', 'millisecond'),
    'microseconds': _interval_property('us', 'microsecond'),
    'nanoseconds': _interval_property('ns', 'nanosecond'),
    '__add__': _interval_add,
    'add': _interval_add,
    '__sub__': _interval_sub,
    'sub': _interval_sub,
    '__radd__': _interval_radd,
    'radd': _interval_radd,
    '__mul__': _interval_mul,
    'mul': _interval_mul,
    '__rmul__': _interval_rmul,
    'rmul': _interval_rmul,
    '__floordiv__': _interval_floordiv,
    'floordiv': _interval_floordiv,
    '__neg__': negate,
    'negate': negate,
}

_add_methods(ir.IntervalValue, _interval_value_methods)


# ---------------------------------------------------------------------
# Time API


def between_time(
    arg: ir.TimestampValue | ir.TimeValue,
    lower: str | datetime.datetime | ir.TimestampValue,
    upper: str | datetime.datetime | ir.TimestampValue,
    timezone: str | None = None,
) -> ir.BooleanValue:
    """Check if the input expr falls between the lower/upper bounds passed.
    Bounds are inclusive. All arguments must be comparable.

    Parameters
    ----------
    arg
        Timestamp or time expression
    lower
        Lower bound
    upper
        Upper bound
    timezone
        Time zone

    Returns
    -------
    BooleanValue
        Whether `arg` is between `lower` and `upper` adjusting `timezone` as
        needed.
    """
    op = arg.op()
    if isinstance(op, ops.Time):
        # Here we pull out the first argument to the underlying Time operation
        # which is by definition (in _timestamp_value_methods) a
        # TimestampValue. We do this so that we can potentially specialize the
        # "between time" operation for timestamp_value_expr.time().between().
        # A similar mechanism is triggered when creating expressions like
        # t.column.distinct().count(), which is turned into t.column.nunique().
        arg = op.arg
        if timezone is not None:
            arg = arg.cast(dt.Timestamp(timezone=timezone))
        op = ops.BetweenTime(arg, lower, upper)
    else:
        op = ops.Between(arg, lower, upper)

    return op.to_expr()


def _time_truncate(
    arg: ir.TimeValue,
    unit: Literal['h', 'm', 's', 'ms', 'us', 'ns'],
) -> ir.TimeValue:
    """Truncate `arg` to time with unit `unit`.

    Notes
    -----
    Commonly used for time series resampling.

    Parameters
    ----------
    arg
        Time column or scalar
    unit
        The time unit to truncate to

    Returns
    -------
    TimeValue
        `arg` truncated to `unit`
    """
    return ops.TimeTruncate(arg, unit).to_expr()


def _time_sub(left, right):
    right = rlz.any(right)

    if isinstance(right, ir.TimeValue):
        op = ops.TimeDiff(left, right)
    else:
        op = ops.TimeSub(left, right)  # let the operation validate

    return op.to_expr()


_time_add = _binop_expr('__add__', ops.TimeAdd)


_time_value_methods = {
    'between': between_time,
    'truncate': _time_truncate,
    'hour': _extract_field('hour', ops.ExtractHour),
    'minute': _extract_field('minute', ops.ExtractMinute),
    'second': _extract_field('second', ops.ExtractSecond),
    'millisecond': _extract_field('millisecond', ops.ExtractMillisecond),
    '__sub__': _time_sub,
    'sub': _time_sub,
    '__rsub__': _time_sub,
    'rsub': _time_sub,
    '__add__': _time_add,
    'add': _time_add,
    '__radd__': _time_add,
    'radd': _time_add,
}

_add_methods(ir.TimeValue, _time_value_methods)


# ---------------------------------------------------------------------
# Decimal API


def _precision(arg: ir.DecimalValue) -> ir.IntegerValue:
    """Return the precision of `arg`.

    Parameters
    ----------
    arg
        Decimal expression

    Returns
    -------
    IntegerValue
        The precision of `arg`.
    """
    return ops.DecimalPrecision(arg).to_expr()


def _scale(arg: ir.DecimalValue) -> ir.IntegerValue:
    """Return the scale of `arg`.

    Parameters
    ----------
    arg
        Decimal expression

    Returns
    -------
    IntegerValue
        The scale of `arg`.
    """
    return ops.DecimalScale(arg).to_expr()


_decimal_value_methods = {
    'precision': _precision,
    'scale': _scale,
}


_add_methods(ir.DecimalValue, _decimal_value_methods)


# ----------------------------------------------------------------------
# Category API


_category_value_methods = {'label': category_label}

_add_methods(ir.CategoryValue, _category_value_methods)


# ---------------------------------------------------------------------
# Table API

_join_classes = {
    'inner': ops.InnerJoin,
    'left': ops.LeftJoin,
    'any_inner': ops.AnyInnerJoin,
    'any_left': ops.AnyLeftJoin,
    'outer': ops.OuterJoin,
    'right': ops.RightJoin,
    'left_semi': ops.LeftSemiJoin,
    'semi': ops.LeftSemiJoin,
    'anti': ops.LeftAntiJoin,
    'cross': ops.CrossJoin,
}


def join(
    left: ir.TableExpr,
    right: ir.TableExpr,
    predicates: str
    | Sequence[
        str
        | tuple[str | ir.ColumnExpr, str | ir.ColumnExpr]
        | ir.BooleanColumn
    ] = (),
    how: Literal[
        'inner',
        'left',
        'outer',
        'right',
        'semi',
        'anti',
        'any_inner',
        'any_left',
        'left_semi',
    ] = 'inner',
    *,
    suffixes: tuple[str, str] = ("_x", "_y"),
) -> ir.TableExpr:
    """Perform a join between two tables.

    Parameters
    ----------
    left
        Left table to join
    right
        Right table to join
    predicates
        Boolean or column names to join on
    how
        Join method
    suffixes
        Left and right suffixes that will be used to rename overlapping
        columns.
    """
    klass = _join_classes[how.lower()]
    if isinstance(predicates, ir.Expr):
        predicates = _L.flatten_predicate(predicates)

    expr = klass(left, right, predicates).to_expr()

    # semi/anti join only give access to the left table's fields, so
    # there's never overlap
    if how in ("semi", "anti"):
        return expr

    return ops.relations._dedup_join_columns(
        expr,
        left=left,
        right=right,
        suffixes=suffixes,
    )


def asof_join(
    left: ir.TableExpr,
    right: ir.TableExpr,
    predicates: str | ir.BooleanColumn | Sequence[str | ir.BooleanColumn] = (),
    by: str | ir.ColumnExpr | Sequence[str | ir.ColumnExpr] = (),
    tolerance: str | ir.IntervalScalar | None = None,
    *,
    suffixes: tuple[str, str] = ("_x", "_y"),
) -> ir.TableExpr:
    """Perform an "as-of" join between `left` and `right`.

    Similar to a left join except that the match is done on nearest key rather
    than equal keys.

    Optionally, match keys with `by` before joining with `predicates`.

    Parameters
    ----------
    left
        Table expression
    right
        Table expression
    predicates
        Join expressions
    by
        column to group by before joining
    tolerance
        Amount of time to look behind when joining
    suffixes
        Left and right suffixes that will be used to rename overlapping
        columns.

    Returns
    -------
    TableExpr
        Table expression
    """
    expr = ops.AsOfJoin(left, right, predicates, by, tolerance).to_expr()
    return ops.relations._dedup_join_columns(
        expr,
        left=left,
        right=right,
        suffixes=suffixes,
    )


def cross_join(
    left: ir.TableExpr,
    right: ir.TableExpr,
    *rest: ir.TableExpr,
    suffixes: tuple[str, str] = ("_x", "_y"),
) -> ir.TableExpr:
    """Compute the cross join of a sequence of tables.

    Parameters
    ----------
    left
        Left table
    right
        Right table
    rest
        Additional tables to cross join
    suffixes
        Left and right suffixes that will be used to rename overlapping
        columns.

    Returns
    -------
    TableExpr
        Cross join of `left`, `right` and `rest`

    Examples
    --------
    >>> import ibis
    >>> schemas = [(name, 'int64') for name in 'abcde']
    >>> a, b, c, d, e = [
    ...     ibis.table([(name, type)], name=name) for name, type in schemas
    ... ]
    >>> joined1 = ibis.cross_join(a, b, c, d, e)
    >>> joined1  # doctest: +NORMALIZE_WHITESPACE
    ref_0
    UnboundTable[table]
      name: a
      schema:
        a : int64
    ref_1
    UnboundTable[table]
      name: b
      schema:
        b : int64
    ref_2
    UnboundTable[table]
      name: c
      schema:
        c : int64
    ref_3
    UnboundTable[table]
      name: d
      schema:
        d : int64
    ref_4
    UnboundTable[table]
      name: e
      schema:
        e : int64
    CrossJoin[table]
      left:
        Table: ref_0
      right:
        CrossJoin[table]
          left:
            CrossJoin[table]
              left:
                CrossJoin[table]
                  left:
                    Table: ref_1
                  right:
                    Table: ref_2
              right:
                Table: ref_3
          right:
            Table: ref_4
    """
    expr = ops.CrossJoin(
        left,
        functools.reduce(ir.TableExpr.cross_join, rest, right),
        [],
    ).to_expr()
    return ops.relations._dedup_join_columns(
        expr,
        left=left,
        right=right,
        suffixes=suffixes,
    )


def _table_count(self: ir.TableExpr) -> ir.IntegerScalar:
    """Compute the number of rows in `self`.

    Parameters
    ----------
    self
        Table expression

    Returns
    -------
    IntegerScalar
        Count of the number of rows in `self`
    """
    return ops.Count(self, None).to_expr().name('count')


def _table_dropna(
    self: ir.TableExpr,
    subset: Sequence[str] | None = None,
    how: Literal['any', 'all'] = 'any',
) -> ir.TableExpr:
    """Remove rows with null values from the table.

    Parameters
    ----------
    subset
        Columns names to consider when dropping nulls. By default all columns
        are considered.
    how
        Determine whether a row is removed if there is at least one null
        value in the row ('any'), or if all row values are null ('all').
        Options are 'any' or 'all'. Default is 'any'.

    Examples
    --------
    >>> import ibis
    >>> t = ibis.table([('a', 'int64'), ('b', 'string')])
    >>> t = t.dropna()  # Drop all rows where any values are null
    >>> t = t.dropna(how='all')  # Only drop rows where all values are null
    >>> t = t.dropna(subset=['a'], how='all')  # Only drop rows where all values in column 'a' are null  # noqa: E501

    Returns
    -------
    TableExpr
        Table expression
    """
    if subset is None:
        subset = []
    subset = util.promote_list(subset)
    return ops.DropNa(self, how, subset).to_expr()


def _table_fillna(
    self: ir.TableExpr,
    replacements: ir.ScalarExpr | Mapping[str, ir.ScalarExpr],
) -> ir.TableExpr:
    """Fill null values in a table expression.

    Parameters
    ----------
    self
        Table expression
    replacements
        Value with which to fill the nulls. If passed as a mapping, the keys
        are column names that map to their replacement value. If passed
        as a scalar, all columns are filled with that value.

    Notes
    -----
    There is potential lack of type stability with the `fillna` API. For
    example, different library versions may impact whether or not a given
    backend promotes integer replacement values to floats.

    Examples
    --------
    >>> import ibis
    >>> t = ibis.table([('a', 'int64'), ('b', 'string')])
    >>> t = t.fillna(0.0)  # Replace nulls in all columns with 0.0
    >>> t.fillna({c: 0.0 for c, t in t.schema().items() if t == dt.float64})  # Replace all na values in all columns of a given type with the same value  # noqa: E501

    Returns
    -------
    TableExpr
        Table expression
    """
    if isinstance(replacements, collections.abc.Mapping):
        columns = replacements.keys()
        table_columns = self.schema().names
        invalid = set(columns) - set(table_columns)
        if invalid:
            raise com.IbisTypeError(
                f'value {list(invalid)} is not a field in {table_columns}.'
            )
    return ops.FillNa(self, replacements).to_expr()


def _table_info(self: ir.TableExpr, buf: IO[str] | None = None) -> None:
    """Show column names, types, and null counts.

    Output to stdout by default.

    Parameters
    ----------
    self
        Table expression
    buf
        A writable buffer
    """
    metrics = [self.count().name('nrows')]
    for col in self.columns:
        metrics.append(self[col].count().name(col))

    metrics = self.aggregate(metrics).execute().loc[0]

    names = ['Column', '------'] + self.columns
    types = ['Type', '----'] + [repr(x) for x in self.schema().types]
    counts = ['Non-null #', '----------'] + [str(x) for x in metrics[1:]]
    col_metrics = util.adjoin(2, names, types, counts)
    result = f'Table rows: {metrics[0]}\n\n{col_metrics}'

    print(result, file=buf)


def _table_set_column(table: ir.TableExpr, name: str, expr: ir.ValueExpr):
    """Replace an existing column with a new expression.

    Parameters
    ----------
    table
        Table expression
    name
        Column name to replace
    expr
        New data for column

    Returns
    -------
    TableExpr
        Table expression
    """
    expr = table._ensure_expr(expr)

    if expr._name != name:
        expr = expr.name(name)

    if name not in table:
        raise KeyError(f'{name} is not in the table')

    # TODO: This assumes that projection is required; may be backend-dependent
    proj_exprs = []
    for key in table.columns:
        if key == name:
            proj_exprs.append(expr)
        else:
            proj_exprs.append(table[key])

    return table.projection(proj_exprs)


def _regular_join_method(
    name: str,
    how: Literal[
        'inner',
        'left',
        'outer',
        'right',
        'semi',
        'anti',
        'any_inner',
        'any_left',
    ],
):
    def f(
        self: ir.TableExpr,
        other: ir.TableExpr,
        predicates: str
        | Sequence[
            str
            | tuple[str | ir.ColumnExpr, str | ir.ColumnExpr]
            | ir.BooleanValue
        ] = (),
        suffixes: tuple[str, str] = ("_x", "_y"),
    ) -> ir.TableExpr:
        f"""Perform a{'n' * how.startswith(tuple("aeiou"))} {how} join between two tables.

        Parameters
        ----------
        left
            Left table to join
        right
            Right table to join
        predicates
            Boolean or column names to join on
        suffixes
            Left and right suffixes that will be used to rename overlapping
            columns.

        Returns
        -------
        TableExpr
            Joined `left` and `right`
        """  # noqa: E501
        return self.join(other, predicates, how=how)

    f.__name__ = name
    return f


def filter(
    table: ir.TableExpr,
    predicates: ir.BooleanValue | Sequence[ir.BooleanValue],
) -> ir.TableExpr:
    """Select rows from `table` based on `predicates`.

    Parameters
    ----------
    table
        Table expression
    predicates
        Boolean value expressions used to select rows in `table`.

    Returns
    -------
    TableExpr
        Filtered table expression
    """
    resolved_predicates = _resolve_predicates(table, predicates)
    return _L.apply_filter(table, resolved_predicates)


def _resolve_predicates(
    table: ir.TableExpr, predicates
) -> list[ir.BooleanValue]:
    if isinstance(predicates, Expr):
        predicates = _L.flatten_predicate(predicates)
    predicates = util.promote_list(predicates)
    predicates = [ir.relations.bind_expr(table, x) for x in predicates]
    resolved_predicates = []
    for pred in predicates:
        if isinstance(pred, ir.AnalyticExpr):
            pred = pred.to_filter()
        resolved_predicates.append(pred)

    return resolved_predicates


def aggregate(
    table: ir.TableExpr,
    metrics: Sequence[ir.ScalarExpr] | None = None,
    by: Sequence[ir.ValueExpr] | None = None,
    having: Sequence[ir.BooleanValue] | None = None,
    **kwargs: ir.ValueExpr,
) -> ir.TableExpr:
    """Aggregate a table with a given set of reductions grouping by `by`.

    Parameters
    ----------
    table
        Table to compute aggregates from
    metrics
        Aggregate expressions
    by
        Grouping expressions
    having
        Post-aggregation filters
    kwargs
        Named aggregate expressions

    Returns
    -------
    TableExpr
        An aggregate table expression
    """
    metrics = [] if metrics is None else util.promote_list(metrics)
    metrics.extend(
        table._ensure_expr(expr).name(name)
        for name, expr in sorted(kwargs.items(), key=operator.itemgetter(0))
    )

    op = table.op().aggregate(
        table,
        metrics,
        by=util.promote_list(by if by is not None else []),
        having=util.promote_list(having if having is not None else []),
    )
    return op.to_expr()


def _table_distinct(self: ir.TableExpr) -> ir.TableExpr:
    """Compute the set of unique rows in the table."""
    op = ops.Distinct(self)
    return op.to_expr()


def _table_limit(table: ir.TableExpr, n: int, offset: int = 0) -> ir.TableExpr:
    """Select the first `n` rows at beginning of table starting at `offset`.

    Parameters
    ----------
    table
        Table expression
    n
        Number of rows to include
    offset
        Number of rows to skip first

    Returns
    -------
    TableExpr
        The first `n` rows of `table` starting at `offset`
    """
    op = ops.Limit(table, n, offset=offset)
    return op.to_expr()


def _head(table: ir.TableExpr, n: int = 5) -> ir.TableExpr:
    """Select the first `n` rows of a table.

    Notes
    -----
    The result set is not deterministic without a sort.

    Parameters
    ----------
    table
        Table expression
    n
        Number of rows to include, defaults to 5

    Returns
    -------
    TableExpr
        `table` limited to `n` rows

    See Also
    --------
    ibis.expr.types.TableExpr.limit
    """
    return _table_limit(table, n=n)


def _table_sort_by(
    table: ir.TableExpr,
    sort_exprs: str
    | ir.ColumnExpr
    | ir.SortKey
    | tuple[str | ir.ColumnExpr, bool]
    | Sequence[tuple[str | ir.ColumnExpr, bool]],
) -> ir.TableExpr:
    """Sort `table` by `sort_exprs`

    Parameters
    ----------
    table
        Table expression
    sort_exprs
        Sort specifications

    Examples
    --------
    >>> import ibis
    >>> t = ibis.table([('a', 'int64'), ('b', 'string')])
    >>> ab_sorted = t.sort_by([('a', True), ('b', False)])

    Returns
    -------
    TableExpr
        Sorted `table`
    """
    return (
        table.op()
        .sort_by(
            table,
            [] if sort_exprs is None else util.promote_list(sort_exprs),
        )
        .to_expr()
    )


def _table_union(
    left: ir.TableExpr,
    right: ir.TableExpr,
    distinct: bool = False,
) -> ir.TableExpr:
    """Compute the set union of two table expressions.

    The input tables must have identical schemas.

    Parameters
    ----------
    left
        Table expression
    right
        Table expression
    distinct
        Only union distinct rows not occurring in the calling table (this
        can be very expensive, be careful)

    Returns
    -------
    TableExpr
        Union of `left` and `right`
    """
    return ops.Union(left, right, distinct=distinct).to_expr()


def _table_intersect(left: ir.TableExpr, right: ir.TableExpr) -> ir.TableExpr:
    """Compute the set intersection of two table expressions.

    The input tables must have identical schemas.

    Parameters
    ----------
    left
        Table expression
    right
        Table expression

    Returns
    -------
    TableExpr
        The rows common amongst `left` and `right`.
    """
    return ops.Intersection(left, right).to_expr()


def _table_difference(left: TableExpr, right: TableExpr) -> ir.TableExpr:
    """Compute the set difference of two table expressions.

    The input tables must have identical schemas.

    Parameters
    ----------
    left
        Table expression
    right
        Table expression

    Returns
    -------
    TableExpr
        The rows present in `left` that are not present in `right`.
    """
    return ops.Difference(left, right).to_expr()


def _table_to_array(self: ir.TableExpr) -> ir.ColumnExpr:
    """View a single column table as an array.

    Parameters
    ----------
    self
        Table expression

    Returns
    -------
    ValueExpr
        A single column view of a table
    """

    schema = self.schema()
    if len(schema) != 1:
        raise com.ExpressionError(
            'Table must have exactly one column when viewed as array'
        )

    return ops.TableArrayView(self).to_expr()


def _safe_get_name(expr):
    try:
        return expr.get_name()
    except com.ExpressionError:
        return None


def mutate(
    table: ir.TableExpr,
    exprs: Sequence[ir.Expr] | None = None,
    **mutations: ir.ValueExpr,
) -> ir.TableExpr:
    """Add columns to a table expression.

    Parameters
    ----------
    table
        Table expression to add columns to
    exprs
        List of named expressions to add as columns
    mutations
        Named expressions using keyword arguments

    Returns
    -------
    TableExpr
        Table expression with additional columns

    Examples
    --------
    Using keywords arguments to name the new columns

    >>> import ibis
    >>> table = ibis.table([('foo', 'double'), ('bar', 'double')], name='t')
    >>> expr = table.mutate(qux=table.foo + table.bar, baz=5)
    >>> expr  # doctest: +NORMALIZE_WHITESPACE
    ref_0
    UnboundTable[table]
      name: t
      schema:
        foo : float64
        bar : float64
    <BLANKLINE>
    Selection[table]
      table:
        Table: ref_0
      selections:
        Table: ref_0
        baz = Literal[int8]
          5
        qux = Add[float64*]
          left:
            foo = Column[float64*] 'foo' from table
              ref_0
          right:
            bar = Column[float64*] 'bar' from table
              ref_0

    Using the :meth:`ibis.expr.types.Expr.name` method to name the new columns

    >>> new_columns = [ibis.literal(5).name('baz',),
    ...                (table.foo + table.bar).name('qux')]
    >>> expr2 = table.mutate(new_columns)
    >>> expr.equals(expr2)
    True

    """
    exprs = [] if exprs is None else util.promote_list(exprs)
    for name, expr in sorted(mutations.items(), key=operator.itemgetter(0)):
        if util.is_function(expr):
            value = expr(table)
        else:
            value = rlz.any(expr)
        exprs.append(value.name(name))

    mutation_exprs = _L.get_mutation_exprs(exprs, table)
    return table.projection(mutation_exprs)


def projection(
    table: ir.TableExpr,
    exprs: ir.ValueExpr | str | Sequence[ir.ValueExpr | str],
) -> ir.TableExpr:
    """Compute a new table expression using `exprs`.

    Parameters
    ----------
    exprs
        Column expression, string, or list of column expressions and strings.

    Returns
    -------
    TableExpr
        Table expression

    Notes
    -----
    Passing an aggregate function to this method will broadcast the aggregate's
    value over the number of rows in the table and automatically constructs
    a window function expression. See the examples section for more details.

    Examples
    --------
    Simple projection

    >>> import ibis
    >>> fields = [('a', 'int64'), ('b', 'double')]
    >>> t = ibis.table(fields, name='t')
    >>> proj = t.projection([t.a, (t.b + 1).name('b_plus_1')])
    >>> proj  # doctest: +NORMALIZE_WHITESPACE
    ref_0
    UnboundTable[table]
      name: t
      schema:
        a : int64
        b : float64
    <BLANKLINE>
    Selection[table]
      table:
        Table: ref_0
      selections:
        a = Column[int64*] 'a' from table
          ref_0
        b_plus_1 = Add[float64*]
          left:
            b = Column[float64*] 'b' from table
              ref_0
          right:
            Literal[int8]
              1
    >>> proj2 = t[t.a, (t.b + 1).name('b_plus_1')]
    >>> proj.equals(proj2)
    True

    Aggregate projection

    >>> agg_proj = t[t.a.sum().name('sum_a'), t.b.mean().name('mean_b')]
    >>> agg_proj  # doctest: +NORMALIZE_WHITESPACE, +ELLIPSIS
    ref_0
    UnboundTable[table]
      name: t
      schema:
        a : int64
        b : float64
    <BLANKLINE>
    Selection[table]
      table:
        Table: ref_0
      selections:
        sum_a = WindowOp[int64*]
          sum_a = Sum[int64]
            a = Column[int64*] 'a' from table
              ref_0
            where:
              None
          <ibis.expr.window.Window object at 0x...>
        mean_b = WindowOp[float64*]
          mean_b = Mean[float64]
            b = Column[float64*] 'b' from table
              ref_0
            where:
              None
          <ibis.expr.window.Window object at 0x...>

    Note the ``<ibis.expr.window.Window>`` objects here, their existence means
    that the result of the aggregation will be broadcast across the number of
    rows in the input column. The purpose of this expression rewrite is to make
    it easy to write column/scalar-aggregate operations like

    .. code-block:: python

       t[(t.a - t.a.mean()).name('demeaned_a')]
    """
    import ibis.expr.analysis as L

    if isinstance(exprs, (Expr, str)):
        exprs = [exprs]

    projector = L.Projector(table, exprs)
    op = projector.get_result()
    return op.to_expr()


def _table_relabel(
    table: ir.TableExpr, substitutions: Mapping[str, str]
) -> ir.TableExpr:
    """Change table column names, otherwise leaving table unaltered.

    Parameters
    ----------
    table
        Table expression
    substitutions
        Name mapping

    Returns
    -------
    TableExpr
        A relabeled table expression
    """
    observed = set()

    exprs = []
    for c in table.columns:
        expr = table[c]
        if c in substitutions:
            expr = expr.name(substitutions[c])
            observed.add(c)
        exprs.append(expr)

    for c in substitutions:
        if c not in observed:
            raise KeyError(f'{c!r} is not an existing column')

    return table.projection(exprs)


def _table_view(self) -> ir.TableExpr:
    """Create a new table expression distinct from the current one..

    Parameters
    ----------
    self
        Table expression

    Returns
    -------
    TableExpr
        Table expression

    Notes
    -----
    For doing any self-referencing operations, like a self-join, you will use
    this operation to create a reference to the current table expression.
    """
    new_view = ops.SelfReference(self)
    return new_view.to_expr()


def _table_drop(
    self: ir.TableExpr, fields: str | Sequence[str]
) -> ir.TableExpr:
    """Remove fields from a table.

    Parameters
    ----------
    self
        Table expression
    fields
        Fields to drop

    Returns
    -------
    TableExpr
        Expression without `fields`
    """

    if not fields:
        # no-op if nothing to be dropped
        return self

    if isinstance(fields, str):
        #  We want to drop just one attribute.
        fields = [fields]

    schema = self.schema()
    field_set = frozenset(fields)
    missing_fields = field_set.difference(schema)

    if missing_fields:
        raise KeyError(f'Fields not in table: {missing_fields!s}')

    return self[[field for field in schema if field not in field_set]]


def _rowid(self) -> ir.IntegerValue:
    """An autonumbering expression representing the row number of the results.

    It can be 0 or 1 indexed depending on the backend. Check the backend
    documentation for specifics.

    Notes
    -----
    This function is different from the window function `row_number`
    (even if they are conceptually the same), and different from `rowid` in
    backends where it represents the physical location
    (e.g. Oracle or PostgreSQL's ctid).

    Returns
    -------
    IntegerColumn
        An integer column

    Examples
    --------
    >>> my_table[my_table.rowid(), my_table.name].execute()
    1|Ibis
    2|pandas
    3|Dask
    """
    return ops.RowID().to_expr()


_table_methods = {
    'aggregate': aggregate,
    'count': _table_count,
    'distinct': _table_distinct,
    'drop': _table_drop,
    'dropna': _table_dropna,
    'fillna': _table_fillna,
    'info': _table_info,
    'limit': _table_limit,
    'head': _head,
    'set_column': _table_set_column,
    'filter': filter,
    'mutate': mutate,
    'projection': projection,
    'select': projection,
    'relabel': _table_relabel,
    'join': join,
    'cross_join': cross_join,
    'inner_join': _regular_join_method('inner_join', 'inner'),
    'left_join': _regular_join_method('left_join', 'left'),
    'any_inner_join': _regular_join_method('any_inner_join', 'any_inner'),
    'any_left_join': _regular_join_method('any_left_join', 'any_left'),
    'outer_join': _regular_join_method('outer_join', 'outer'),
    'semi_join': _regular_join_method('semi_join', 'semi'),
    'anti_join': _regular_join_method('anti_join', 'anti'),
    'asof_join': asof_join,
    'sort_by': _table_sort_by,
    'to_array': _table_to_array,
    'union': _table_union,
    'intersect': _table_intersect,
    'difference': _table_difference,
    'view': _table_view,
    'rowid': _rowid,
}


_add_methods(ir.TableExpr, _table_methods)


def prevent_rewrite(expr, client=None):
    """Prevent optimization from happening below `expr`.

    Parameters
    ----------
    expr : ir.TableExpr
        Any table expression whose optimization you want to prevent
    client : ibis.backends.base.Client, optional, default None
        A client to use to create the SQLQueryResult operation. This is useful
        if you're compiling an expression that derives from an
        :class:`~ibis.expr.operations.UnboundTable` operation.

    Returns
    -------
    sql_query_result : ir.TableExpr
    """
    if client is None:
        client = expr._find_backend()
    query = client.compile(expr)
    return ops.SQLQueryResult(query, expr.schema(), client).to_expr()
