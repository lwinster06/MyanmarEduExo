#!/usr/bin/env python3
"""
Plot UNDP youth education-disengagement rates against university-adjacent conflict.

Dropout/disengagement rates are transcribed from Figure 12 of UNDP's
"A Generation on Hold: Youth Employment and Education in Myanmar" report.
The figure labels the measure as youth aged 18-24 "not engaged in education or
training"; this script uses that as the dropout-rate proxy requested for analysis.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DROPOUT_RATES = {
    "Kachin": 79.1,
    "Kayah": 63.7,
    "Kayin": 82.9,
    "Chin": 82.7,
    "Sagaing": 83.9,
    "Tanintharyi": 85.9,
    "Bago": 73.1,
    "Magway": 79.0,
    "Mandalay": 74.9,
    "Mon": 75.8,
    "Rakhine": 78.8,
    "Yangon": 66.8,
    "Shan": 77.4,
    "Ayeyarwady": 73.7,
    "Nay Pyi Taw": 73.8,
}


def build_plot_data(conflict_csv: str, output_csv: str) -> pd.DataFrame:
    conflicts = pd.read_csv(conflict_csv)
    dropout = pd.DataFrame(
        [{"region": region, "dropout_rate_pct": rate} for region, rate in DROPOUT_RATES.items()]
    )
    data = dropout.merge(conflicts, on="region", how="left")

    conflict_columns = [
        "universities_in_gazetteer",
        "unique_conflicts_5km",
        "unique_conflicts_10km",
        "university_event_exposures_5km",
        "university_event_exposures_10km",
    ]
    for column in conflict_columns:
        data[column] = data[column].fillna(0).astype(int)

    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_csv, index=False)
    return data


def plot(data: pd.DataFrame, output_png: str, title_suffix: str) -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), sharey=True)
    configs = [
        ("unique_conflicts_5km", "5 km"),
        ("unique_conflicts_10km", "10 km"),
    ]

    colors = data["universities_in_gazetteer"].map(lambda n: "#3E7CB1" if n > 0 else "#9B9B9B")
    regression_data = data[data["universities_in_gazetteer"] > 0].copy()

    for ax, (x_col, radius_label) in zip(axes, configs):
        ax.scatter(
            data[x_col],
            data["dropout_rate_pct"],
            s=95,
            c=colors,
            alpha=0.82,
            edgecolor="#2B2B2B",
            linewidth=0.7,
        )

        x = regression_data[x_col].to_numpy(dtype=float)
        y = regression_data["dropout_rate_pct"].to_numpy(dtype=float)
        if len(x) >= 2 and len(np.unique(x)) >= 2:
            slope, intercept = np.polyfit(x, y, 1)
            fitted = slope * x + intercept
            ss_res = float(np.sum((y - fitted) ** 2))
            ss_tot = float(np.sum((y - np.mean(y)) ** 2))
            r_squared = 1 - ss_res / ss_tot if ss_tot else np.nan

            line_x = np.linspace(0, max(data[x_col].max(), x.max()) * 1.02, 100)
            line_y = slope * line_x + intercept
            ax.plot(line_x, line_y, color="#B23A48", linewidth=2.2)
            ax.text(
                0.03,
                0.96,
                f"OLS: y = {intercept:.1f} + {slope:.3f}x\nR² = {r_squared:.2f}",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=9.5,
                bbox={
                    "boxstyle": "round,pad=0.35",
                    "facecolor": "white",
                    "edgecolor": "#CFCFCF",
                    "alpha": 0.9,
                },
            )

        for _, row in data.iterrows():
            x_offset = 2 if row[x_col] < data[x_col].max() * 0.85 else -8
            ha = "left" if x_offset > 0 else "right"
            ax.annotate(
                row["region"],
                (row[x_col], row["dropout_rate_pct"]),
                xytext=(x_offset, 3),
                textcoords="offset points",
                fontsize=8.5,
                ha=ha,
                va="bottom",
            )

        ax.set_title(f"{radius_label} radius")
        ax.set_xlabel("Unique conflict events near any university in region")
        ax.grid(True, linestyle=":", linewidth=0.8, alpha=0.55)

    axes[0].set_ylabel("Youth 18-24 not engaged in education/training (%)")
    fig.suptitle(
        "Regional youth education disengagement vs. university-adjacent conflict\n"
        f"{title_suffix}",
        fontsize=14,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.02,
        "Dropout proxy: UNDP Figure 12, 'not engaged in education or training'. "
        "Trend lines exclude grey regions with no universities in the attached gazetteer.",
        ha="center",
        fontsize=9,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.9))

    output_path = Path(output_png)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)


def ols_rows(data: pd.DataFrame, window: str) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    regression_data = data[data["universities_in_gazetteer"] > 0].copy()

    for radius, x_col in ((5, "unique_conflicts_5km"), (10, "unique_conflicts_10km")):
        x = regression_data[x_col].to_numpy(dtype=float)
        y = regression_data["dropout_rate_pct"].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        fitted = slope * x + intercept
        ss_res = float(np.sum((y - fitted) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r_squared = 1 - ss_res / ss_tot if ss_tot else np.nan
        correlation = float(np.corrcoef(x, y)[0, 1])
        rows.append(
            {
                "window": window,
                "radius_km": radius,
                "n_regions": len(regression_data),
                "intercept": intercept,
                "slope_dropout_pct_points_per_conflict": slope,
                "r_squared": r_squared,
                "correlation": correlation,
            }
        )
    return rows


def main() -> None:
    specs = [
        {
            "window": "2021-2024",
            "conflict_csv": "outputs/undp_region_university_conflict_counts_2021_2024_geoprec_le2_5km_10km_clean.csv",
            "plot_data_csv": "outputs/dropout_vs_conflicts_plot_data_2021_2024_geoprec_le2.csv",
            "output_png": "outputs/dropout_vs_conflicts_2021_2024_geoprec_le2.png",
            "title_suffix": "Conflict data: 2021-2024, UCDP where_prec <= 2",
        },
        {
            "window": "2023-2024",
            "conflict_csv": "outputs/undp_region_university_conflict_counts_2023_2024_geoprec_le2_5km_10km_clean.csv",
            "plot_data_csv": "outputs/dropout_vs_conflicts_plot_data_2023_2024_geoprec_le2.csv",
            "output_png": "outputs/dropout_vs_conflicts_2023_2024_geoprec_le2.png",
            "title_suffix": "Conflict data: 2023-2024, UCDP where_prec <= 2",
        },
    ]

    all_ols_rows = []
    for spec in specs:
        data = build_plot_data(spec["conflict_csv"], spec["plot_data_csv"])
        plot(data, spec["output_png"], spec["title_suffix"])
        all_ols_rows.extend(ols_rows(data, spec["window"]))
        print(f"Wrote {Path(spec['output_png']).resolve()}")
        print(f"Wrote {Path(spec['plot_data_csv']).resolve()}")

    ols_output = Path("outputs/dropout_conflict_ols_results.csv")
    pd.DataFrame(all_ols_rows).to_csv(ols_output, index=False)
    print(f"Wrote {ols_output.resolve()}")


if __name__ == "__main__":
    main()
