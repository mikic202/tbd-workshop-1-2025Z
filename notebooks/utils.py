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
    db_table
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
    db_table
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
        db_table
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


#  -- -- -- -- --  PANDAS -- -- -- -- --


def benchmark_pandas():
    pass


#  -- -- -- -- --  POLARS -- -- -- -- --


def benchmark_polars():
    pass


#  -- -- -- -- --  DUCKDB -- -- -- -- --


def benchmark_duckdb():
    pass


#  -- -- -- -- --  SPARK -- -- -- -- --

def benchmark_spark_time(spark_session: SparkSession, df_spark: pyspark.sql.DataFrame, run_query_func: Callable) -> list[float]:
    print(f"Repeats number: {N_REPEATS}")

    # Clearing Cache and sql views to have similar conditions:
    spark_session.catalog.dropTempView("db_table")
    spark_session.catalog.clearCache()

    # Core functionality:
    df_spark.createOrReplaceTempView(name="db_table")

    times = timeit.repeat(
        lambda: run_query_func(spark_session),
        number=1,
        repeat=N_REPEATS
    )

    print(f"Execution times: {[round(t, 3) for t in times]}")
    print(f"First time: {times[0]:.3f}s")
    print(f"Mean  time: {np.mean(times):.3f}s")
    print(f"Best  time: {min(times):.3f}s")

    return times


def benchmark_spark_memory(spark_session: SparkSession, df_spark: pyspark.sql.DataFrame, run_query_func: Callable) -> Any:
    # Clearing Cache and sql views to have similar conditions:
    spark_session.catalog.dropTempView("db_table")
    spark_session.catalog.clearCache()

    # Core functionality:
    df_spark.createOrReplaceTempView(name="db_table")

    peak_memory = memory_usage((run_query_func, (spark_session,)), max_usage=True)

    print(f"Peak Memory Usage: {peak_memory} MiB")

    return peak_memory


def run_spark_query_aggregation(spark_session: pyspark.sql.SparkSession) -> None:
    query: pyspark.sql.DataFrame = spark_session.sql(sqlQuery=AGGREGATION_QUERY)
    query.collect()

def run_spark_query_windowfunc(spark_session: pyspark.sql.SparkSession) -> None:
    query: pyspark.sql.DataFrame = spark_session.sql(sqlQuery=WINDOWFUNCTION_QUERY)
    query.collect()

def run_spark_query_join(spark_session: pyspark.sql.SparkSession) -> None:
    query: pyspark.sql.DataFrame = spark_session.sql(sqlQuery=JOIN_QUERY)
    query.collect()


### Scalability


def scalability_pandas():
    pass

def scalability_polars():
    pass

def scalability_duckdb():
    pass

def scalability_spark():
    pass
