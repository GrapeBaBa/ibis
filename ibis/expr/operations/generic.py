import datetime
import decimal
import enum
import functools
import itertools
import uuid

import numpy as np
import pandas as pd
from public import public

from ...common import exceptions as com
from .. import datatypes as dt
from .. import rules as rlz
from .. import types as ir
from .core import UnaryOp, ValueOp, distinct_roots

try:
    import shapely
except ImportError:
    BaseGeometry = type(None)
else:
    BaseGeometry = shapely.geometry.base.BaseGeometry


@public
class TableColumn(ValueOp):
    """Selects a column from a `TableExpr`."""

    table = rlz.table
    name = rlz.instance_of((str, int))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        name = self.name
        table = self.table

        schema = table.schema()

        if isinstance(name, int):
            self.name = name = schema.name_at_position(name)

        if name not in schema:
            raise com.IbisTypeError(
                f"value {name!r} is not a field in {table.columns}"
            )

    def parent(self):
        return self.table

    def resolve_name(self):
        return self.name

    def has_resolved_name(self):
        return True

    def root_tables(self):
        return self.table.op().root_tables()

    def _make_expr(self):
        dtype = self.table._get_type(self.name)
        klass = dtype.column_type()
        return klass(self, name=self.name)


@public
class RowID(ValueOp):
    """The row number (an autonumeric) of the returned result."""

    def output_type(self):
        return dt.int64.column_type()

    def resolve_name(self):
        return 'rowid'

    def has_resolved_name(self):
        return True


@public
def find_all_base_tables(expr, memo=None):
    if memo is None:
        memo = {}

    node = expr.op()

    if isinstance(expr, ir.TableExpr) and node.blocks():
        if expr not in memo:
            memo[node] = expr
        return memo

    for arg in expr.op().flat_args():
        if isinstance(arg, ir.Expr):
            find_all_base_tables(arg, memo)

    return memo


@public
class TableArrayView(ValueOp):

    """
    (Temporary?) Helper operation class for SQL translation (fully formed table
    subqueries to be viewed as arrays)
    """

    table = rlz.table

    @property
    def name(self):
        return self.table.schema().names[0]

    def _make_expr(self):
        ctype = self.table._get_type(self.name)
        klass = ctype.column_type()
        return klass(self, name=self.name)


@public
class Cast(ValueOp):
    arg = rlz.any
    to = rlz.datatype

    # see #396 for the issue preventing an implementation of resolve_name

    def output_type(self):
        return rlz.shape_like(self.arg, dtype=self.to)


@public
class TypeOf(UnaryOp):
    output_type = rlz.shape_like('arg', dt.string)


@public
class IsNull(UnaryOp):
    """Return true if values are null.

    Returns
    -------
    ir.BooleanValue
        Value expression indicating whether values are null
    """

    output_type = rlz.shape_like('arg', dt.boolean)


@public
class NotNull(UnaryOp):
    """Returns true if values are not null

    Returns
    -------
    ir.BooleanValue
        Value expression indicating whether values are not null
    """

    output_type = rlz.shape_like('arg', dt.boolean)


@public
class ZeroIfNull(UnaryOp):
    output_type = rlz.typeof('arg')


@public
class IfNull(ValueOp):
    """Equivalent to (but perhaps implemented differently):

    case().when(expr.notnull(), expr)
          .else_(null_substitute_expr)
    """

    arg = rlz.any
    ifnull_expr = rlz.any
    output_type = rlz.shape_like('args')


@public
class NullIf(ValueOp):
    """Set values to NULL if they equal the null_if_expr"""

    arg = rlz.any
    null_if_expr = rlz.any
    output_type = rlz.shape_like('args')


@public
class CoalesceLike(ValueOp):

    # According to Impala documentation:
    # Return type: same as the initial argument value, except that integer
    # values are promoted to BIGINT and floating-point values are promoted to
    # DOUBLE; use CAST() when inserting into a smaller numeric column
    arg = rlz.value_list_of(rlz.any)

    def output_type(self):
        first = self.arg[0]
        ty = first.type()
        dtype = getattr(ty, "largest", ty)
        # self.arg is a list of value expressions
        return rlz.shape_like(self.arg, dtype)


@public
class Coalesce(CoalesceLike):
    pass


@public
class Greatest(CoalesceLike):
    pass


@public
class Least(CoalesceLike):
    pass


@public
class Literal(ValueOp):
    value = rlz.one_of(
        (
            rlz.instance_of(
                (
                    BaseGeometry,
                    bytes,
                    datetime.date,
                    datetime.datetime,
                    datetime.time,
                    datetime.timedelta,
                    dict,
                    enum.Enum,
                    float,
                    frozenset,
                    int,
                    list,
                    np.generic,
                    np.ndarray,
                    pd.Timedelta,
                    pd.Timestamp,
                    set,
                    str,
                    tuple,
                    type(None),
                    uuid.UUID,
                    decimal.Decimal,
                )
            ),
            rlz.is_computable_input,
        )
    )
    dtype = rlz.datatype

    def __repr__(self):
        return '{}({})'.format(
            type(self).__name__, ', '.join(map(repr, self.args))
        )

    def equals(self, other, cache=None):
        # Check types
        if not (
            isinstance(other, Literal)
            and isinstance(other.value, type(self.value))
            and self.dtype == other.dtype
        ):
            return False

        # Check values
        if isinstance(self.value, np.ndarray):
            return np.array_equal(self.value, other.value)
        else:
            return self.value == other.value

    def output_type(self):
        return self.dtype.scalar_type()

    def root_tables(self):
        return []

    def __hash__(self) -> int:
        """Return the hash of a literal value.

        We override this method to make sure that we can handle things that
        aren't eminently hashable like an ``array<array<int64>>``.

        """
        return hash(self.dtype._literal_value_hash_key(self.value))


@public
class NullLiteral(Literal):
    """Typeless NULL literal"""

    value = rlz.optional(type(None))
    dtype = rlz.optional(rlz.instance_of(dt.Null), default=dt.null)


@public
class ScalarParameter(ValueOp):
    _counter = itertools.count()

    dtype = rlz.datatype
    counter = rlz.optional(
        rlz.instance_of(int), default=lambda: next(ScalarParameter._counter)
    )

    def resolve_name(self):
        return f'param_{self.counter:d}'

    def __repr__(self):
        return f'{type(self).__name__}(type={self.dtype})'

    def __hash__(self):
        return hash((self.dtype, self.counter))

    def output_type(self):
        return self.dtype.scalar_type()

    def equals(self, other, cache=None):
        return (
            isinstance(other, ScalarParameter)
            and self.counter == other.counter
            and self.dtype.equals(other.dtype, cache=cache)
        )

    @property
    def inputs(self):
        return ()

    def root_tables(self):
        return []


@public
class ValueList(ValueOp):
    """Data structure for a list of value expressions"""

    values = rlz.tuple_of(rlz.any)
    display_argnames = False  # disable showing argnames in repr

    def output_type(self):
        dtype = rlz.highest_precedence_dtype(self.values)
        return functools.partial(ir.ListExpr, dtype=dtype)

    def root_tables(self):
        return distinct_roots(*self.values)


@public
class Constant(ValueOp):
    pass


@public
class TimestampNow(Constant):
    def output_type(self):
        return dt.timestamp.scalar_type()


@public
class FloatConstant(Constant):
    def output_type(self):
        return dt.float64.scalar_type()


@public
class RandomScalar(FloatConstant):
    pass


@public
class E(FloatConstant):
    pass


@public
class Pi(FloatConstant):
    pass


@public
class StructField(ValueOp):
    arg = rlz.struct
    field = rlz.instance_of(str)

    def output_type(self):
        struct_dtype = self.arg.type()
        value_dtype = struct_dtype[self.field]
        return rlz.shape_like(self.arg, value_dtype)


@public
class DecimalUnaryOp(UnaryOp):
    arg = rlz.decimal


@public
class DecimalPrecision(UnaryOp):
    output_type = rlz.shape_like('arg', dt.int32)


@public
class DecimalScale(DecimalUnaryOp):
    output_type = rlz.shape_like('arg', dt.int32)


@public
class Hash(ValueOp):
    arg = rlz.any
    how = rlz.isin({'fnv', 'farm_fingerprint'})
    output_type = rlz.shape_like('arg', dt.int64)


@public
class HashBytes(ValueOp):
    arg = rlz.one_of({rlz.value(dt.string), rlz.value(dt.binary)})
    how = rlz.isin({'md5', 'sha1', 'sha256', 'sha512'})
    output_type = rlz.shape_like('arg', dt.binary)


@public
class SummaryFilter(ValueOp):
    expr = rlz.instance_of(ir.TopKExpr)

    def output_type(self):
        return dt.boolean.column_type()


@public
class TopK(ValueOp):
    arg = rlz.column(rlz.any)
    k = rlz.non_negative_integer
    by = rlz.one_of(
        (
            rlz.function_of("arg", preprocess=ir.relations.find_base_table),
            rlz.any,
        )
    )

    def output_type(self):
        return ir.TopKExpr

    def blocks(self):
        return True


@public
class SimpleCase(ValueOp):
    base = rlz.any
    cases = rlz.value_list_of(rlz.any)
    results = rlz.value_list_of(rlz.any)
    default = rlz.any

    def _validate(self):
        assert len(self.cases) == len(self.results)

    def root_tables(self):
        return distinct_roots(*self.flat_args())

    def output_type(self):
        values = self.results + [self.default]
        dtype = rlz.highest_precedence_dtype(values)
        return rlz.shape_like(self.base, dtype=dtype)


@public
class SearchedCase(ValueOp):
    cases = rlz.value_list_of(rlz.boolean)
    results = rlz.value_list_of(rlz.any)
    default = rlz.any

    def _validate(self):
        assert len(self.cases) == len(self.results)

    def root_tables(self):
        return distinct_roots(*self.flat_args())

    def output_type(self):
        exprs = self.results + [self.default]
        dtype = rlz.highest_precedence_dtype(exprs)
        return rlz.shape_like(self.cases, dtype)


@public
class DistinctColumn(ValueOp):

    """
    COUNT(DISTINCT ...) is really just syntactic suger, but we provide a
    distinct().count() nicety for users nonetheless.

    For all intents and purposes, like Distinct, but can be distinguished later
    for evaluation if the result should be array-like versus table-like. Also
    for calling count()
    """

    arg = rlz.column(rlz.any)
    output_type = rlz.typeof('arg')

    def count(self):
        """Only valid if the distinct contains a single column"""
        from .reductions import CountDistinct

        return CountDistinct(self.arg)
