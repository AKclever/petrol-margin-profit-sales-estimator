#!/usr/bin/env python3
"""Create the auditable quarterly state exposure table from explicit assumptions."""

import csv
from pathlib import Path

# End-point counts are working estimates, not company-reported state gallon volumes.
# tuple: state, 2023Q1 stores, 2025Q4 stores, traffic, Express share, metro share,
# regional volume index, state wholesale/retail margin environment proxy (cpg).
STATES = [
    ("AL", 77, 85, .94, .31, .36, .98, 28.5), ("AR", 66, 72, .90, .25, .27, .97, 29.0),
    ("CO", 9, 14, 1.06, .71, .72, 1.05, 33.2), ("FL", 130, 146, 1.12, .48, .76, 1.08, 31.8),
    ("GA", 105, 119, 1.04, .43, .61, 1.04, 30.5), ("IA", 20, 23, .91, .30, .31, .95, 30.8),
    ("IL", 42, 46, 1.01, .37, .69, .98, 34.0), ("IN", 42, 46, .98, .34, .49, .99, 31.4),
    ("KS", 23, 27, .93, .37, .40, .98, 29.5), ("KY", 49, 55, .97, .33, .42, 1.00, 30.2),
    ("LA", 44, 49, .96, .28, .49, .99, 28.8), ("MI", 4, 9, .99, .78, .71, 1.02, 33.5),
    ("MN", 18, 20, .94, .35, .52, .96, 32.1), ("MO", 70, 77, .96, .33, .47, .99, 29.8),
    ("MS", 68, 73, .89, .23, .27, .96, 28.0), ("NC", 85, 95, 1.03, .41, .57, 1.03, 30.9),
    ("NE", 11, 14, .92, .43, .46, .96, 30.1), ("NM", 26, 29, .92, .31, .55, .98, 31.2),
    ("OH", 52, 57, 1.00, .39, .58, 1.01, 32.0), ("OK", 57, 63, .94, .29, .44, .98, 28.9),
    ("SC", 61, 69, 1.02, .40, .51, 1.03, 30.1), ("TN", 92, 102, 1.02, .39, .53, 1.02, 29.7),
    ("TX", 334, 368, 1.08, .42, .70, 1.07, 30.6), ("VA", 60, 68, 1.04, .43, .63, 1.03, 31.5),
    ("WI", 15, 18, .93, .39, .45, .96, 31.9), ("WV", 14, 17, .91, .35, .28, .97, 30.0),
    ("WY", 7, 9, .88, .56, .25, .94, 31.0),
]
QUARTERS = [f"{year}Q{q}" for year in range(2023, 2026) for q in range(1, 5)]


def main() -> None:
    target = Path(__file__).parent / "data" / "geographic_exposure.csv"
    target.parent.mkdir(exist_ok=True)
    fields = ["quarter", "state", "store_count", "traffic_index", "express_share", "metro_share",
              "regional_volume_index", "state_margin_cpg", "store_count_estimated", "volume_weight_estimated"]
    with target.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i, quarter in enumerate(QUARTERS):
            for state, start, end, traffic, express, metro, regional, margin in STATES:
                stores = round(start + (end - start) * i / (len(QUARTERS) - 1))
                writer.writerow(dict(quarter=quarter, state=state, store_count=stores,
                    traffic_index=traffic, express_share=express, metro_share=metro,
                    regional_volume_index=regional, state_margin_cpg=margin,
                    store_count_estimated="true", volume_weight_estimated="true"))


if __name__ == "__main__":
    main()
