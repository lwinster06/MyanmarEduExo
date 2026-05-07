#!/usr/bin/env python3
"""
Aggregate university-radius conflict tallies to UNDP Myanmar Youth Survey regions.

Two measures are reported:
1. university_event_exposures: sums the per-university counts, so the same event
   can count multiple times if it is near multiple universities.
2. unique_events_near_any_university: counts distinct conflict event IDs once per
   UNDP region/radius.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple


UNDP_REGIONS = [
    ("Kachin", 118, 1.64),
    ("Kayah", 57, 0.79),
    ("Kayin", 420, 5.84),
    ("Chin", 404, 5.62),
    ("Sagaing", 557, 7.75),
    ("Tanintharyi", 459, 6.39),
    ("Bago", 584, 8.13),
    ("Magway", 604, 8.40),
    ("Mandalay", 601, 8.36),
    ("Mon", 562, 7.82),
    ("Rakhine", 525, 7.30),
    ("Yangon", 605, 8.42),
    ("Shan", 572, 7.96),
    ("Ayeyarwady", 600, 8.35),
    ("Nay Pyi Taw", 519, 7.22),
]

REGION_NORMALIZATION = {
    "Naypyitaw": "Nay Pyi Taw",
    "Nay Pyi Taw": "Nay Pyi Taw",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate university conflict counts by UNDP state/region."
    )
    parser.add_argument("--summary", required=True)
    parser.add_argument("--matches", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def normalize_region(value: str) -> str:
    cleaned = (value or "").strip()
    return REGION_NORMALIZATION.get(cleaned, cleaned)


def read_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def to_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def event_key(match: Dict[str, str]) -> str:
    return match.get("event_id", "")


def main() -> None:
    args = parse_args()
    summary_rows = read_csv(args.summary)
    match_rows = read_csv(args.matches)

    by_region: Dict[str, Dict[str, object]] = {}
    for region, sample, pct in UNDP_REGIONS:
        by_region[region] = {
            "undp_state_region": region,
            "undp_survey_sample_n": sample,
            "undp_survey_sample_pct": pct,
            "universities_in_gazetteer": 0,
            "universities_with_conflicts_within_5km": 0,
            "universities_with_conflicts_within_10km": 0,
            "university_event_exposures_within_5km": 0,
            "university_event_exposures_within_10km": 0,
            "university_event_best_deaths_within_5km": 0,
            "university_event_best_deaths_within_10km": 0,
            "unique_events_near_any_university_within_5km": 0,
            "unique_events_near_any_university_within_10km": 0,
            "unique_event_best_deaths_within_5km": 0,
            "unique_event_best_deaths_within_10km": 0,
        }

    for row in summary_rows:
        region = normalize_region(row.get("state_region", ""))
        if region not in by_region:
            by_region[region] = {
                "undp_state_region": region,
                "undp_survey_sample_n": "",
                "undp_survey_sample_pct": "",
                "universities_in_gazetteer": 0,
                "universities_with_conflicts_within_5km": 0,
                "universities_with_conflicts_within_10km": 0,
                "university_event_exposures_within_5km": 0,
                "university_event_exposures_within_10km": 0,
                "university_event_best_deaths_within_5km": 0,
                "university_event_best_deaths_within_10km": 0,
                "unique_events_near_any_university_within_5km": 0,
                "unique_events_near_any_university_within_10km": 0,
                "unique_event_best_deaths_within_5km": 0,
                "unique_event_best_deaths_within_10km": 0,
            }

        target = by_region[region]
        count_5 = to_int(row.get("conflicts_within_5km", "0"))
        count_10 = to_int(row.get("conflicts_within_10km", "0"))
        target["universities_in_gazetteer"] += 1
        target["universities_with_conflicts_within_5km"] += int(count_5 > 0)
        target["universities_with_conflicts_within_10km"] += int(count_10 > 0)
        target["university_event_exposures_within_5km"] += count_5
        target["university_event_exposures_within_10km"] += count_10
        target["university_event_best_deaths_within_5km"] += to_int(
            row.get("best_deaths_within_5km", "0")
        )
        target["university_event_best_deaths_within_10km"] += to_int(
            row.get("best_deaths_within_10km", "0")
        )

    event_sets: Dict[Tuple[str, int], Set[str]] = {}
    event_deaths: Dict[Tuple[str, int, str], int] = {}

    for match in match_rows:
        region = normalize_region(match.get("state_region", ""))
        if not event_key(match):
            continue
        distance = to_float(match.get("distance_km", ""))
        best_deaths = to_int(match.get("best_deaths", "0"))
        for radius in (5, 10):
            if distance <= radius:
                event_sets.setdefault((region, radius), set()).add(event_key(match))
                death_key = (region, radius, event_key(match))
                event_deaths[death_key] = max(event_deaths.get(death_key, 0), best_deaths)

    for (region, radius), events in event_sets.items():
        if region not in by_region:
            continue
        by_region[region][f"unique_events_near_any_university_within_{radius}km"] = len(events)
        by_region[region][f"unique_event_best_deaths_within_{radius}km"] = sum(
            event_deaths.get((region, radius, event_id), 0) for event_id in events
        )

    fieldnames = list(next(iter(by_region.values())).keys())
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for region, _, _ in UNDP_REGIONS:
            writer.writerow(by_region[region])
        for region in sorted(set(by_region) - {name for name, _, _ in UNDP_REGIONS}):
            writer.writerow(by_region[region])

    print(f"Wrote {output_path.resolve()}")


if __name__ == "__main__":
    main()
