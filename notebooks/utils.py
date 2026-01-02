import polars as pl
import pandas as pd
import duckdb
import pyspark.sql
from pyspark.sql import SparkSession

import numpy as np
import timeit
from memory_profiler import memory_usage
from typing import Callable, Any

import matplotlib.pyplot as plt

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


#### Data tables

DEFAULT_DATA_TABLE_NAME = "db_table"


#  -- -- -- -- --  PANDAS -- -- -- -- --


# --- Query A: AGGREGATION ---
def query_aggregation_pandas(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("device")
        .agg(
            device_count=("device", "count"),
            avg_latency=("latency", "mean"),
            avg_error_rate=("error_rate", "mean"),
        )
        .reset_index()
    )


# --- Query B: WINDOW FUNCTION ---
def query_window_pandas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["post_date"] = pd.to_datetime(df["timestamp"]).dt.date

    df["daily_like_rank"] = df.groupby(["category", "post_date"])["likes"].rank(
        method="first", ascending=False
    )

    df = df.sort_values(["category", "timestamp"])
    df["rolling_avg_views"] = (
        df.groupby("category")["views"]
        .rolling(100, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    return df


# --- Query C: JOIN previous post per user ---
def query_join_pandas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values(["user_id", "timestamp"], ascending=[True, False])
    df["userpost_history"] = df.groupby("user_id").cumcount() + 1

    df_prev = df[["user_id", "post_id", "userpost_history"]].copy()
    df_prev["userpost_history"] += 1
    df_prev = df_prev.rename(columns={"post_id": "previous_post_id"})

    result = df.merge(df_prev, on=["user_id", "userpost_history"], how="left")
    return result[["user_id", "post_id", "previous_post_id"]]


def benchmark_pandas_time(
    df: pd.DataFrame,
    query_fn: Callable[[pd.DataFrame], Any],
    verbose: bool = True,
) -> list[float]:

    if verbose:
        print(f"Repeats number: {N_REPEATS}")

    times = timeit.repeat(
        lambda: query_fn(df),
        number=1,
        repeat=N_REPEATS,
    )

    if verbose:
        print(f"Execution times: {[round(t, 3) for t in times]}")
        print(f"First time: {times[0]:.3f}s")
        print(f"Mean  time: {np.mean(times):.3f}s")
        print(f"Best  time: {min(times):.3f}s")

    return times


def benchmark_pandas_memory(df: pd.DataFrame, query_fn, verbose: bool = True) -> float:

    peak_memory = memory_usage((lambda: query_fn(df), ()), max_usage=True)

    if verbose:
        print(f"Peak Memory Usage: {peak_memory:.3f} MiB")

    return peak_memory


#  -- -- -- -- --  POLARS -- -- -- -- --


# --- Query A: AGGREGATION ---
def query_aggregation_polars(df: pl.DataFrame) -> pl.DataFrame:
    return df.group_by("device").agg(
        [
            pl.count("device").alias("device_count"),
            pl.col("latency").mean().alias("avg_latency"),
            pl.col("error_rate").mean().alias("avg_error_rate"),
        ]
    )


def query_aggregation_polars_lazy(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.group_by("device")
        .agg(
            [
                pl.count("device").alias("device_count"),
                pl.col("latency").mean().alias("avg_latency"),
                pl.col("error_rate").mean().alias("avg_error_rate"),
            ]
        )
        .collect()
    )


def query_aggregation_polars_lazy_streaming(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.group_by("device")
        .agg(
            [
                pl.count("device").alias("device_count"),
                pl.col("latency").mean().alias("avg_latency"),
                pl.col("error_rate").mean().alias("avg_error_rate"),
            ]
        )
        .collect(streaming=True)
    )


# --- Query B: WINDOW FUNCTION ---
def query_window_polars(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns(
        [pl.col("timestamp").cast(pl.Datetime).dt.date().alias("post_date")]
    )

    df = df.sort(["category", "post_date", "likes"], descending=[False, False, True])
    df = df.with_columns(
        [
            pl.col("likes")
            .rank(method="ordinal")
            .over(["category", "post_date"])
            .alias("daily_like_rank")
        ]
    )

    df = df.sort(["category", "timestamp"])
    df = df.with_columns(
        [
            pl.col("views")
            .rolling_mean(window_size=100)
            .over("category")
            .alias("rolling_avg_views")
        ]
    )

    return df


# --- Query C: JOIN previous post per user ---
def query_join_polars(df: pl.DataFrame) -> pl.DataFrame:
    df = df.sort(["user_id", "timestamp"], descending=[False, True])

    df = df.with_columns(
        pl.int_range(1, pl.len() + 1).over("user_id").alias("userpost_history")
    )

    df_prev = (
        df.select(["user_id", "post_id", "userpost_history"])
        .with_columns((pl.col("userpost_history") + 1).alias("userpost_history"))
        .rename({"post_id": "previous_post_id"})
    )

    result = df.join(df_prev, on=["user_id", "userpost_history"], how="left")

    return result.select(["user_id", "post_id", "previous_post_id"])


def benchmark_polars_time(
    df: pl.DataFrame, query_fn, verbose: bool = True
) -> list[float]:

    if verbose:
        print(f"Repeats number: {N_REPEATS}")

    times = timeit.repeat(lambda: query_fn(df), number=1, repeat=N_REPEATS)

    if verbose:
        print(f"Execution times: {[round(t, 3) for t in times]}")
        print(f"First time: {times[0]:.3f}s")
        print(f"Mean  time: {np.mean(times):.3f}s")
        print(f"Best  time: {min(times):.3f}s")

    return times


def benchmark_polars_memory(df: pl.DataFrame, query_fn, verbose: bool = True) -> float:

    peak_memory = memory_usage((lambda: query_fn(df), ()), max_usage=True)

    if verbose:
        print(f"Peak Memory Usage: {peak_memory:.3f} MiB")

    return peak_memory


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
    def __init__(self, session: SparkSession, df: pyspark.sql.DataFrame):
        self.__spark_session: SparkSession = session
        self.__spark_df: pyspark.sql.DataFrame = df

    def session(self) -> SparkSession:
        return self.__spark_session

    def df(self) -> pyspark.sql.DataFrame:
        return self.__spark_df

    def get_items(self) -> tuple[SparkSession, pyspark.sql.DataFrame]:
        return self.__spark_session, self.__spark_df


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
    peak_memory = memory_usage(
        proc=(
            run_spark_query,
            (
                spark_session,
                query,
            ),
        ),
        max_usage=True,
    )

    if verbose:
        print(f"Peak Memory Usage: {peak_memory} MiB")

    return peak_memory


### Scalability


def scalability_pandas():
    pass


def scalability_polars():
    pass


def scalability_duckdb(
    table_location, query, max_number_of_threads: int = 10
) -> dict[int, float]:
    db_connection = duckdb.connect(":memeory:")
    times_for_each_thread = {}
    threads_list = [1, 2, 4, 8, 16]
    # for n_threads in range(1, max_number_of_threads + 1):
    for n_threads in [t for t in threads_list if t <= max_number_of_threads]:
        db_connection.execute(f"PRAGMA threads={n_threads};")
        times_for_each_thread[n_threads] = np.mean(
            benchmark_duckdb_time(table_location, query, db_connection, verbose=False)
        )

    return times_for_each_thread


def scalability_spark(
    table_location: str, query: str, max_number_of_threads: int = 10
) -> dict[int, float]:
    times_for_each_thread = {}

    threads_list = [1, 2, 4, 8, 16]
    for n_threads in [t for t in threads_list if t <= max_number_of_threads]:
        spark = (
            SparkSession.builder.appName(f"TBD_Spark_Scalability_test_{n_threads}")
            .master(f"local[{n_threads}]")
            .config("spark.driver.memory", "4g")
            .config("spark.sql.shuffle.partitions", n_threads)
            .getOrCreate()
        )
        df_spark = spark.read.parquet(table_location).repartition(n_threads)

        spark_results = benchmark_spark_time(
            spark_benchmark_obj=SparkBenchmarkObject(spark, df_spark),
            query=query,
            verbose=False,
        )
        times_for_each_thread[n_threads] = np.mean(spark_results)

        spark.stop()

    return times_for_each_thread


def plot_scalability(times_per_core_query_dict: dict, title: str):
    plt.figure(figsize=(12, 6))
    plt.plot(
        list(times_per_core_query_dict.keys()),
        list(times_per_core_query_dict.values()),
        marker="o",
    )
    plt.title(title)
    plt.xlabel("Number of Cores")
    plt.ylabel("Execution Time (seconds)")
