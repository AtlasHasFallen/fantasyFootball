import marimo

__generated_with = "0.15.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import polars.selectors as cs
    from great_tables import GT
    from plotnine import ggplot, aes, geom_histogram, theme_minimal
    return GT, aes, cs, geom_histogram, ggplot, mo, pl, theme_minimal


@app.cell
def _(pl):
    df = (
        pl.scan_parquet("data/clean/weekly_player_stats.parquet")
        .select(
            pl.col.season,
            pl.col.player_name,
            pl.col.fantasy_points_league,
            pl.col.week,
            pl.col.position,
        )
        .drop_nulls()
        .group_by("player_name")
        .agg(
            pl.col.position.first(),
            pl.col.fantasy_points_league.mean().alias("avg_points"),
            pl.col.fantasy_points_league.std().alias("std_dev"),
            pl.col.fantasy_points_league,
        )
        .with_columns(
            pl.col.fantasy_points_league.list.reverse()
            .list.slice(0, 10)
            .list.reverse()
            .cast(pl.List(pl.String))
            .list.join(" ")
        )
        .sort("avg_points", descending=True)
    ).collect()
    return (df,)


@app.cell
def _():
    # headshots = pl.scan_parquet("data/headshots.parquet").collect()
    return


@app.cell
def _(df, pl):
    pos_avg = df.group_by('position').agg(pl.col('avg_points').mean().alias('position_avg'))
    return (pos_avg,)


@app.cell(hide_code=True)
def _(mo, pl, pos_avg):
    mo.md(
        rf"""
    # Quarterback - QB
    Average: {round(pos_avg.filter(pl.col.position == "QB").select("position_avg").item())}
    """
    )
    return


@app.cell
def _(create_position_plot, create_position_table, df, mo):
    _table = create_position_table(df, "QB", "Quarterback")
    _plot = create_position_plot(df, "QB").draw()
    mo.hstack([_table, _plot],align='start')
    return


@app.cell
def _(mo, pl, pos_avg):
    mo.md(
        rf"""
    # Running Back - RB
    Average: {round(pos_avg.filter(pl.col.position == "RB").select("position_avg").item())}
    """
    )
    return


@app.cell
def _(create_position_plot, create_position_table, df, mo):
    _table = create_position_table(df, "RB", "Running Back")
    _plot = create_position_plot(df, "RB").draw()
    mo.hstack([_table, _plot],align='start')
    return


@app.cell
def _(mo, pl, pos_avg):
    mo.md(
        rf"""
    # Wide Receiver - WR
    Average: {round(pos_avg.filter(pl.col.position == "WR").select("position_avg").item())}
    """
    )
    return


@app.cell
def _(create_position_plot, create_position_table, df, mo):
    _table = create_position_table(df, "WR", "Wide Receiver")
    _plot = create_position_plot(df, "WR").draw()
    mo.hstack([_table, _plot],align='start')
    return


@app.cell
def _(mo, pl, pos_avg):
    mo.md(
        rf"""
    # Tight End - TE
    Average: {round(pos_avg.filter(pl.col.position == "TE").select("position_avg").item())}
    """
    )
    return


@app.cell
def _(create_position_plot, create_position_table, df, mo):
    _table = create_position_table(df, "TE", "Tight End")
    _plot = create_position_plot(df, "TE").draw()
    mo.hstack([_table, _plot],align='start')
    return


@app.cell
def _(mo, pl, pos_avg):
    mo.md(
        rf"""
    # Kicker - K
    Average: {round(pos_avg.filter(pl.col.position == "K").select("position_avg").item())}
    """
    )
    return


@app.cell
def _(create_position_plot, create_position_table, df, mo):
    _table = create_position_table(df, "K", "Kicker")
    _plot = create_position_plot(df, "K").draw()
    mo.hstack([_table, _plot],align='start')
    return


@app.cell
def _(mo, pl, pos_avg):
    mo.md(
        rf"""
    # Punter - P
    Average: {round(pos_avg.filter(pl.col.position == "P").select("position_avg").item())}
    """
    )
    return


@app.cell
def _(create_position_plot, create_position_table, df, mo):
    _table = create_position_table(df, "P", "Punter")
    _plot = create_position_plot(df, "P").draw()
    mo.hstack([_table, _plot],align='start')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Functions""")
    return


@app.cell
def _(GT, cs, pl):
    def create_position_table(
        df: pl.DataFrame, position: str, position_title: str
    ):
        df = df.filter(pl.col.position == position).drop("position")
        table = (
            GT(df)
            .tab_header(title=f"{position_title} Player Statistics")
            .tab_stub(rowname_col="player_name")
            .tab_stubhead(label="Player")
            .fmt_number(columns=["avg_points", "std_dev"], decimals=1)
            .cols_align(align="center", columns=cs.exclude("player_name"))
            .fmt_nanoplot(columns="fantasy_points_league")
        )
        return table
    return (create_position_table,)


@app.cell
def _(aes, geom_histogram, ggplot, pl, theme_minimal):
    def create_position_plot(df: pl.DataFrame, position: str):
        df = df.filter(pl.col.position == position).drop("position")
        plot = (
            ggplot(df, aes(x="avg_points"))
            + geom_histogram(bins=10, fill='lightblue', color='grey', alpha=0.4)  # specify the number of bins
        ) + theme_minimal()
        return plot
    '''df2 = df.filter(pl.col.position == "QB").drop("position")

    plot = (
        ggplot(df2, aes(x="avg_points"))
        + geom_histogram(bins=10, fill='lightblue', color='grey', alpha=0.4)  # specify the number of bins
    ) + theme_minimal()

    plot.show()'''
    return (create_position_plot,)


if __name__ == "__main__":
    app.run()
