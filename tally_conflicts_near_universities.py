#!/usr/bin/env python3
"""
Tally UCDP-style conflict events within radius buffers around Myanmar universities.

The script intentionally counts all types of violence together. It also keeps
geographic precision breakouts, because 5 km and 10 km buffers are very sensitive
to whether an event was coded to an exact point, a nearby place, or an admin centroid.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional


DEFAULT_CONFLICT_CSV = (
    "/Users/gabriellwin/Desktop/GS Project Data/conflict_data_mmr.csv"
)
DEFAULT_UNIVERSITY_CSV = (
    "/Users/gabriellwin/Desktop/GS Project Data/f69741e4-937e-42a3-a867-cfce6b053e6c.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count conflict events within km radii of universities."
    )
    parser.add_argument("--conflicts", default=DEFAULT_CONFLICT_CSV)
    parser.add_argument("--universities", default=DEFAULT_UNIVERSITY_CSV)
    parser.add_argument(
        "--radii-km",
        nargs="+",
        type=float,
        default=[5.0, 10.0],
        help="One or more buffer radii in kilometers.",
    )
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument(
        "--max-where-prec",
        type=int,
        default=None,
        help=(
            "Optional maximum UCDP where_prec value to include. Lower is more precise; "
            "leaving this blank includes all events."
        ),
    )
    parser.add_argument(
        "--summary-out",
        default="outputs/university_conflict_radius_counts.csv",
    )
    parser.add_argument(
        "--matches-out",
        default="outputs/university_conflict_radius_matches.csv",
    )
    return parser.parse_args()


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def to_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def radius_label(radius: float) -> str:
    if radius.is_integer():
        return str(int(radius))
    return str(radius).replace(".", "p")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_earth_km = 6371.0088
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius_earth_km * math.asin(math.sqrt(a))


def year_allowed(year: Optional[int], start_year: Optional[int], end_year: Optional[int]) -> bool:
    if year is None:
        return False
    if start_year is not None and year < start_year:
        return False
    if end_year is not None and year > end_year:
        return False
    return True


def event_allowed(
    event: Dict[str, str],
    start_year: Optional[int],
    end_year: Optional[int],
    max_where_prec: Optional[int],
) -> bool:
    if not year_allowed(to_int(event.get("year", "")), start_year, end_year):
        return False
    where_prec = to_int(event.get("where_prec", ""))
    if max_where_prec is not None and (where_prec is None or where_prec > max_where_prec):
        return False
    return (
        to_float(event.get("latitude", "")) is not None
        and to_float(event.get("longitude", "")) is not None
    )


def precision_bucket(where_prec: Optional[int]) -> str:
    if where_prec == 1:
        return "geoprec_1_exact"
    if where_prec == 2:
        return "geoprec_2_nearby"
    if where_prec is not None and where_prec >= 3:
        return "geoprec_3plus_centroid_or_broad"
    return "geoprec_unknown"


def initialize_summary_row(university: Dict[str, str], radii: Iterable[float]) -> Dict[str, object]:
    row: Dict[str, object] = {
        "university_id": university.get("_id", ""),
        "university_name": university.get("University_Name", ""),
        "state_region": university.get("State/Region", ""),
        "latitude": university.get("Latitude", ""),
        "longitude": university.get("Longitude", ""),
    }
    for radius in radii:
        label = radius_label(radius)
        row[f"conflicts_within_{label}km"] = 0
        row[f"best_deaths_within_{label}km"] = 0
        row[f"conflicts_within_{label}km_geoprec_1_exact"] = 0
        row[f"conflicts_within_{label}km_geoprec_2_nearby"] = 0
        row[f"conflicts_within_{label}km_geoprec_3plus_centroid_or_broad"] = 0
        row[f"conflicts_within_{label}km_geoprec_unknown"] = 0
    return row


def write_rows(path: str, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    radii = sorted(set(args.radii_km))
    max_radius = max(radii)

    universities = read_csv(args.universities)
    conflicts = [
        event
        for event in read_csv(args.conflicts)
        if event_allowed(event, args.start_year, args.end_year, args.max_where_prec)
    ]

    summary_rows: List[Dict[str, object]] = []
    match_rows: List[Dict[str, object]] = []

    for university in universities:
        uni_lat = to_float(university.get("Latitude", ""))
        uni_lon = to_float(university.get("Longitude", ""))
        if uni_lat is None or uni_lon is None:
            continue

        summary = initialize_summary_row(university, radii)

        for event in conflicts:
            event_lat = to_float(event.get("latitude", ""))
            event_lon = to_float(event.get("longitude", ""))
            if event_lat is None or event_lon is None:
                continue

            distance = haversine_km(uni_lat, uni_lon, event_lat, event_lon)
            if distance > max_radius:
                continue

            where_prec = to_int(event.get("where_prec", ""))
            bucket = precision_bucket(where_prec)
            best_deaths = to_int(event.get("best", "")) or 0

            for radius in radii:
                if distance <= radius:
                    label = radius_label(radius)
                    summary[f"conflicts_within_{label}km"] += 1
                    summary[f"best_deaths_within_{label}km"] += best_deaths
                    summary[f"conflicts_within_{label}km_{bucket}"] += 1

            match_rows.append(
                {
                    "university_id": university.get("_id", ""),
                    "university_name": university.get("University_Name", ""),
                    "state_region": university.get("State/Region", ""),
                    "university_latitude": uni_lat,
                    "university_longitude": uni_lon,
                    "event_id": event.get("id", ""),
                    "event_year": event.get("year", ""),
                    "event_date_start": event.get("date_start", ""),
                    "event_date_end": event.get("date_end", ""),
                    "distance_km": round(distance, 4),
                    "within_radius_km": min(radius for radius in radii if distance <= radius),
                    "where_prec": event.get("where_prec", ""),
                    "where_coordinates": event.get("where_coordinates", ""),
                    "adm_1": event.get("adm_1", ""),
                    "adm_2": event.get("adm_2", ""),
                    "best_deaths": best_deaths,
                    "conflict_name": event.get("conflict_name", ""),
                    "dyad_name": event.get("dyad_name", ""),
                    "side_a": event.get("side_a", ""),
                    "side_b": event.get("side_b", ""),
                }
            )

        summary_rows.append(summary)

    summary_fields = list(summary_rows[0].keys()) if summary_rows else []
    match_fields = [
        "university_id",
        "university_name",
        "state_region",
        "university_latitude",
        "university_longitude",
        "event_id",
        "event_year",
        "event_date_start",
        "event_date_end",
        "distance_km",
        "within_radius_km",
        "where_prec",
        "where_coordinates",
        "adm_1",
        "adm_2",
        "best_deaths",
        "conflict_name",
        "dyad_name",
        "side_a",
        "side_b",
    ]

    write_rows(args.summary_out, summary_rows, summary_fields)
    write_rows(args.matches_out, match_rows, match_fields)

    print(f"Universities processed: {len(summary_rows):,}")
    print(f"Conflict events included: {len(conflicts):,}")
    print(f"University-event matches within {max_radius:g} km: {len(match_rows):,}")
    print(f"Summary written: {Path(args.summary_out).resolve()}")
    print(f"Matches written: {Path(args.matches_out).resolve()}")


if __name__ == "__main__":
    main()
