import pandas as pd
import pytest
from pytest import param

import ibis.common.exceptions as exc

# add here backends that passes join tests
all_db_join_supported = [
    'csv',
    'dask',
    'hdf5',
    'pandas',
    'parquet',
    'pyspark',
]


@pytest.mark.parametrize(
    'how',
    [
        'inner',
        'left',
        'right',
        'outer',
        param(
            'semi',
            marks=pytest.mark.xfail(
                raises=(exc.OperationNotDefinedError, NotImplementedError),
                reason='Semi join not implemented',
            ),
        ),
        param(
            'anti',
            marks=pytest.mark.xfail(
                raises=(exc.OperationNotDefinedError, NotImplementedError),
                reason='Anti join not implemented',
            ),
        ),
    ],
)
@pytest.mark.only_on_backends(all_db_join_supported)
def test_join_project_left_table(backend, con, batting, awards_players, how):

    left = batting[batting.yearID == 2015]
    right = awards_players[awards_players.lgID == 'NL'].drop(
        ['yearID', 'lgID']
    )

    left_df = left.execute()
    right_df = right.execute()
    predicate = ['playerID']
    result_order = ['playerID', 'yearID', 'lgID', 'stint']
    expr = left.join(right, predicate, how=how)[left]
    result = expr.execute().sort_values(result_order)

    joined = pd.merge(
        left_df, right_df, how=how, on=predicate, suffixes=('', '_y')
    ).sort_values(result_order)
    expected = joined[list(left.columns)]

    backend.assert_frame_equal(
        result[expected.columns], expected, check_like=True
    )
