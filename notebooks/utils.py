import polars as pl
import pandas as pd
import duckdb
import pyspark.sql
from pyspark.sql import SparkSession

import numpy as np
import timeit
from memory_profiler import memory_usage
from typing import Callable, Any


# Part 3    ## Task 1

### Queries:

AGGREGATION_QUERY = """
-- Select device types and its technical information averages
SELECT
    device, COUNT(*) AS device_count,
    AVG(latency) AS avg_latency, AVG(error_rate) AS avg_error_rate
FROM
    %s
GROUP BY
    device
"""

WINDOWFUNCTION_QUERY = """
SELECT
    post_id,
    category,
    DATE(timestamp) AS post_date,
    likes,
    views,
    RANK() OVER (
        PARTITION BY category, DATE(timestamp)
        ORDER BY likes DESC
    ) AS daily_like_rank,
    AVG(views) OVER (
        PARTITION BY category
        ORDER BY timestamp
        ROWS BETWEEN 100 PRECEDING AND CURRENT ROW
    ) AS rolling_avg_views
FROM
    %s
"""

JOIN_QUERY = """
-- Select all post_ids and get previous post_id of the 1st post uploader (user_id)
WITH posts_ranked AS (
    SELECT
        post_id
        , user_id
        , ROW_NUMBER() OVER (
            PARTITION BY user_id
            ORDER BY timestamp DESC
        ) AS userpost_history
    FROM
        %s
)
SELECT
    cur.user_id as user_id
    , cur.post_id as post_id
    , prev.post_id as prevoius_post_id
FROM
    posts_ranked cur
LEFT JOIN
    posts_ranked prev
ON
    cur.user_id = prev.user_id
    AND cur.userpost_history = prev.userpost_history - 1
"""


### Benchmark:

N_REPEATS = 5


### Data tables

DEFAULT_DATA_TABLE_NAME = "db_table"


#  -- -- -- -- --  PANDAS -- -- -- -- --


def benchmark_pandas():
    pass


#  -- -- -- -- --  POLARS -- -- -- -- --


def benchmark_polars():
    pass


#  -- -- -- -- --  DUCKDB -- -- -- -- --


def benchmark_duckdb_memory(
    table_location: str,
    query: str,
    db_connection: duckdb.DuckDBPyConnection | None = None,
    verbose: bool = True,
) -> list[float]:
    if not db_connection:
        db_connection = duckdb.connect(":memeory:")

    peak_memory = memory_usage(
        (lambda: db_connection.sql(query % f"'{table_location}'").fetchall(), ()),
        max_usage=True,
    )
    if verbose:
        print(f"Peak Memory Usage: {peak_memory:.3f} MiB")

    return peak_memory


def benchmark_duckdb_time(
    table_location: str,
    query: str,
    db_connection: duckdb.DuckDBPyConnection | None = None,
    verbose: bool = True,
) -> list[float]:
    if verbose:
        print(f"Repeats number: {N_REPEATS}")

    if not db_connection:
        db_connection = duckdb.connect(":memory:")  # This lowers time and memory usage

    times = timeit.repeat(
        lambda: db_connection.sql(query % f"'{table_location}'").fetchall(),
        number=1,
        repeat=N_REPEATS,
    )
    if verbose:
        print(f"Execution times: {[round(t, 3) for t in times]}")
        print(f"First time: {times[0]:.3f}s")
        print(f"Mean  time: {np.mean(times):.3f}s")
        print(f"Best  time: {min(times):.3f}s")

    return times


#  -- -- -- -- --  SPARK -- -- -- -- --


class SparkBenchmarkObject:
    def __init__(self, session:SparkSession, df: pyspark.sql.DataFrame):
        self.__spark_session: SparkSession = session
        self.__spark_df: pyspark.sql.DataFrame = df

    def session(self) -> SparkSession:
        return self.__spark_session

    def df(self) -> pyspark.sql.DataFrame:
        return self.__spark_df

    def get_items(self) -> tuple[SparkSession, pyspark.sql.DataFrame]:
        return self.__spark_session,  self.__spark_df


def run_spark_query(spark_session: pyspark.sql.SparkSession, query: str) -> None:
    spark_query: pyspark.sql.DataFrame = spark_session.sql(
        sqlQuery=query % DEFAULT_DATA_TABLE_NAME
    )
    spark_query.collect()


def benchmark_spark_time(
    spark_benchmark_obj: SparkBenchmarkObject,
    query: str,
    verbose: bool = True,
) -> list[float]:
    if verbose:
        print(f"Repeats number: {N_REPEATS}")
    spark_session, df_spark = spark_benchmark_obj.get_items()

    # Clearing Cache and sql views to have similar conditions:
    spark_session.catalog.dropTempView(DEFAULT_DATA_TABLE_NAME)
    spark_session.catalog.clearCache()

    # Core functionality:
    df_spark.createOrReplaceTempView(name=DEFAULT_DATA_TABLE_NAME)
    times = timeit.repeat(
        lambda: run_spark_query(spark_session, query), number=1, repeat=N_REPEATS
    )

    if verbose:
        print(f"Execution times: {[round(t, 3) for t in times]}")
        print(f"First time: {times[0]:.3f}s")
        print(f"Mean  time: {np.mean(times):.3f}s")
        print(f"Best  time: {min(times):.3f}s")

    return times


def benchmark_spark_memory(
    spark_benchmark_obj: SparkBenchmarkObject,
    query: str,
    verbose: bool = True,
) -> Any:
    spark_session, df_spark = spark_benchmark_obj.get_items()

    # Clearing Cache and sql views to have similar conditions:
    spark_session.catalog.dropTempView(DEFAULT_DATA_TABLE_NAME)
    spark_session.catalog.clearCache()

    # Core functionality:
    df_spark.createOrReplaceTempView(name=DEFAULT_DATA_TABLE_NAME)
    peak_memory = memory_usage((run_spark_query, (spark_session, query,)), max_usage=True)

    if verbose:
        print(f"Peak Memory Usage: {peak_memory} MiB")

    return peak_memory


### Scalability


def scalability_pandas():
    pass


def scalability_polars():
    pass


def scalability_duckdb(
    table_location, querry, max_number_of_threads: int = 10
) -> dict[int, float]:
    db_connection = duckdb.connect(":memeory:")
    times_for_each_thread = {}
    for n_threads in range(1, max_number_of_threads + 1):
        db_connection.execute(f"PRAGMA threads={n_threads};")
        times_for_each_thread[n_threads] = np.mean(
            benchmark_duckdb_time(table_location, querry, db_connection, verbose=False)
        )

    return times_for_each_thread


def scalability_spark():
    pass
