import csv
import tempfile
import unittest
from pathlib import Path

import tracker


class TrackerTests(unittest.TestCase):
    def test_catalog_documents_basis(self):
        specs = tracker.catalog("data/series_catalog.csv")
        self.assertEqual(specs["EIA_NYH_RBOB_REG_E0"]["ethanol_spec"], "E0 blendstock for oxygenate blending")

    def test_fallback_blend_and_adjustments_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "out.csv"
            tracker.build("data/example_prices.csv", "data/series_catalog.csv", out)
            with out.open() as handle:
                rows = list(csv.DictReader(handle))
            fallback = next(r for r in rows if r["region"] == "fallback")
            self.assertEqual(fallback["proxy_usd_per_gallon"], "1.9600")
            self.assertEqual(fallback["status"], "spot_fallback_explanatory")

    def test_validation_finds_known_relationship(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.csv"
            with path.open("w", newline="") as handle:
                writer = csv.writer(handle); writer.writerow(["quarter", "musa_reported_margin_cpg", "gulf_coast_spot_usd_per_gallon", "nyh_spot_usd_per_gallon"])
                margin = gc = nyh = 0
                for i in range(25):
                    if i: gc += (-1)**i * .1; nyh += ((i % 3)-1)*.07; margin += 4*(gc-prev_gc)-2*(nyh-prev_nyh)
                    writer.writerow([f"Q{i}", margin, gc, nyh]); prev_gc, prev_nyh = gc, nyh
            result = tracker.validation(path)
            self.assertEqual(result["gate"], "PASS")
            self.assertAlmostEqual(result["r2"], 1)

if __name__ == "__main__": unittest.main()
