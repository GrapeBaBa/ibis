import operator

import toolz
from public import public

from .. import datatypes as dt
from .. import rules as rlz
from .. import types as ir
from .core import BinaryOp, Node, UnaryOp, ValueOp
from .logical import Between


@public
class TemporalUnaryOp(UnaryOp):
    arg = rlz.temporal


@public
class TimestampUnaryOp(UnaryOp):
    arg = rlz.timestamp


_date_units = {
    'Y': 'Y',
    'y': 'Y',
    'year': 'Y',
    'YEAR': 'Y',
    'YYYY': 'Y',
    'SYYYY': 'Y',
    'YYY': 'Y',
    'YY': 'Y',
    'Q': 'Q',
    'q': 'Q',
    'quarter': 'Q',
    'QUARTER': 'Q',
    'M': 'M',
    'month': 'M',
    'MONTH': 'M',
    'w': 'W',
    'W': 'W',
    'week': 'W',
    'WEEK': 'W',
    'd': 'D',
    'D': 'D',
    'J': 'D',
    'day': 'D',
    'DAY': 'D',
}

_time_units = {
    'h': 'h',
    'H': 'h',
    'HH24': 'h',
    'hour': 'h',
    'HOUR': 'h',
    'm': 'm',
    'MI': 'm',
    'minute': 'm',
    'MINUTE': 'm',
    's': 's',
    'second': 's',
    'SECOND': 's',
    'ms': 'ms',
    'millisecond': 'ms',
    'MILLISECOND': 'ms',
    'us': 'us',
    'microsecond': 'ms',
    'MICROSECOND': 'ms',
    'ns': 'ns',
    'nanosecond': 'ns',
    'NANOSECOND': 'ns',
}

_timestamp_units = toolz.merge(_date_units, _time_units)


@public
class TimestampTruncate(ValueOp):
    arg = rlz.timestamp
    unit = rlz.isin(_timestamp_units)
    output_type = rlz.shape_like('arg', dt.timestamp)


@public
class DateTruncate(ValueOp):
    arg = rlz.date
    unit = rlz.isin(_date_units)
    output_type = rlz.shape_like('arg', dt.date)


@public
class TimeTruncate(ValueOp):
    arg = rlz.time
    unit = rlz.isin(_time_units)
    output_type = rlz.shape_like('arg', dt.time)


@public
class Strftime(ValueOp):
    arg = rlz.temporal
    format_str = rlz.string
    output_type = rlz.shape_like('arg', dt.string)


@public
class StringToTimestamp(ValueOp):
    arg = rlz.string
    format_str = rlz.string
    timezone = rlz.optional(rlz.string)
    output_type = rlz.shape_like('arg', dt.Timestamp(timezone='UTC'))


@public
class ExtractTemporalField(TemporalUnaryOp):
    output_type = rlz.shape_like('arg', dt.int32)


ExtractTimestampField = ExtractTemporalField


@public
class ExtractDateField(ExtractTemporalField):
    arg = rlz.one_of([rlz.date, rlz.timestamp])


@public
class ExtractTimeField(ExtractTemporalField):
    arg = rlz.one_of([rlz.time, rlz.timestamp])


@public
class ExtractYear(ExtractDateField):
    pass


@public
class ExtractMonth(ExtractDateField):
    pass


@public
class ExtractDay(ExtractDateField):
    pass


@public
class ExtractDayOfYear(ExtractDateField):
    pass


@public
class ExtractQuarter(ExtractDateField):
    pass


@public
class ExtractEpochSeconds(ExtractDateField):
    pass


@public
class ExtractWeekOfYear(ExtractDateField):
    pass


@public
class ExtractHour(ExtractTimeField):
    pass


@public
class ExtractMinute(ExtractTimeField):
    pass


@public
class ExtractSecond(ExtractTimeField):
    pass


@public
class ExtractMillisecond(ExtractTimeField):
    pass


@public
class DayOfWeekIndex(UnaryOp):
    arg = rlz.one_of([rlz.date, rlz.timestamp])
    output_type = rlz.shape_like('arg', dt.int16)


@public
class DayOfWeekName(UnaryOp):
    arg = rlz.one_of([rlz.date, rlz.timestamp])
    output_type = rlz.shape_like('arg', dt.string)


@public
class DayOfWeekNode(Node):
    arg = rlz.one_of([rlz.date, rlz.timestamp])

    def output_type(self):
        return ir.DayOfWeek


@public
class Time(UnaryOp):
    output_type = rlz.shape_like('arg', dt.time)


@public
class Date(UnaryOp):
    output_type = rlz.shape_like('arg', dt.date)


@public
class TimestampFromUNIX(ValueOp):
    arg = rlz.any
    # Only pandas-based backends support 'ns'
    unit = rlz.isin({'s', 'ms', 'us', 'ns'})
    output_type = rlz.shape_like('arg', dt.timestamp)


@public
class DateAdd(BinaryOp):
    left = rlz.date
    right = rlz.interval(units={'Y', 'Q', 'M', 'W', 'D'})
    output_type = rlz.shape_like('left')


@public
class DateSub(BinaryOp):
    left = rlz.date
    right = rlz.interval(units={'Y', 'Q', 'M', 'W', 'D'})
    output_type = rlz.shape_like('left')


@public
class DateDiff(BinaryOp):
    left = rlz.date
    right = rlz.date
    output_type = rlz.shape_like('left', dt.Interval('D'))


@public
class TimeAdd(BinaryOp):
    left = rlz.time
    right = rlz.interval(units={'h', 'm', 's', 'ms', 'us', 'ns'})
    output_type = rlz.shape_like('left')


@public
class TimeSub(BinaryOp):
    left = rlz.time
    right = rlz.interval(units={'h', 'm', 's', 'ms', 'us', 'ns'})
    output_type = rlz.shape_like('left')


@public
class TimeDiff(BinaryOp):
    left = rlz.time
    right = rlz.time
    output_type = rlz.shape_like('left', dt.Interval('s'))


@public
class TimestampAdd(BinaryOp):
    left = rlz.timestamp
    right = rlz.interval(
        units={'Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us', 'ns'}
    )
    output_type = rlz.shape_like('left')


@public
class TimestampSub(BinaryOp):
    left = rlz.timestamp
    right = rlz.interval(
        units={'Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us', 'ns'}
    )
    output_type = rlz.shape_like('left')


@public
class TimestampDiff(BinaryOp):
    left = rlz.timestamp
    right = rlz.timestamp
    output_type = rlz.shape_like('left', dt.Interval('s'))


@public
class IntervalBinaryOp(BinaryOp):
    def output_type(self):
        args = [
            arg.cast(arg.type().value_type)
            if isinstance(arg.type(), dt.Interval)
            else arg
            for arg in self.args
        ]
        expr = rlz.numeric_like(args, self.__class__.op)(self)
        left_dtype = self.left.type()
        dtype_type = type(left_dtype)
        additional_args = {
            attr: getattr(left_dtype, attr)
            for attr in dtype_type.__slots__
            if attr not in {'unit', 'value_type'}
        }
        dtype = dtype_type(left_dtype.unit, expr.type(), **additional_args)
        return rlz.shape_like(self.args, dtype=dtype)


@public
class IntervalAdd(IntervalBinaryOp):
    left = rlz.interval
    right = rlz.interval
    op = operator.add


@public
class IntervalSubtract(IntervalBinaryOp):
    left = rlz.interval
    right = rlz.interval
    op = operator.sub


@public
class IntervalMultiply(IntervalBinaryOp):
    left = rlz.interval
    right = rlz.numeric
    op = operator.mul


@public
class IntervalFloorDivide(IntervalBinaryOp):
    left = rlz.interval
    right = rlz.numeric
    op = operator.floordiv


@public
class IntervalFromInteger(ValueOp):
    arg = rlz.integer
    unit = rlz.isin({'Y', 'Q', 'M', 'W', 'D', 'h', 'm', 's', 'ms', 'us', 'ns'})

    @property
    def resolution(self):
        return dt.Interval(self.unit).resolution

    def output_type(self):
        dtype = dt.Interval(self.unit, self.arg.type())
        return rlz.shape_like(self.arg, dtype=dtype)


@public
class BetweenTime(Between):
    arg = rlz.one_of([rlz.timestamp, rlz.time])
    lower_bound = rlz.one_of([rlz.time, rlz.string])
    upper_bound = rlz.one_of([rlz.time, rlz.string])
