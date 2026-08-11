import unittest
from datetime import date, timedelta

from margin_model.features import build_candidates
from margin_model.quarter import FiscalQuarter, load_fiscal_quarters, weighted_quarter_average
from margin_model.selection import rolling_origin_scores


class ModelTests(unittest.TestCase):
    def test_candidates_are_asof_and_use_observation_windows(self):
        origin = date(2024, 1, 1)
        wholesale = [(origin + timedelta(days=i), float(i)) for i in range(30) if i not in (12, 13)]
        row = build_candidates([origin + timedelta(days=20)], wholesale)[0]
        self.assertEqual(row["same_day"], 20.0)
        self.assertAlmostEqual(row["trailing_3d"], 19.0)
        self.assertAlmostEqual(row["trailing_7d"], 17.0)
        self.assertEqual(row["lag_1w"], 11.0)  # day 13 is absent: as-of day 11
        self.assertEqual(row["lag_2w"], 6.0)

    def test_quarter_average_weights_partial_weeks(self):
        quarter = FiscalQuarter("test", date(2024, 1, 3), date(2024, 1, 12))
        rows = [(date(2024, 1, 1), 10.0), (date(2024, 1, 8), 20.0)]
        self.assertEqual(weighted_quarter_average(rows, quarter), 15.0)

    def test_reported_fiscal_calendar_is_loaded(self):
        quarters = load_fiscal_quarters("data/musa_fiscal_quarters.csv")
        self.assertEqual(quarters["2024Q1"].end, date(2024, 3, 31))

    def test_rolling_selection_prefers_true_two_week_lag(self):
        rows = []
        for i in range(24):
            rows.append({"same_day": float((i * 7) % 13), "trailing_3d": float(i % 5), "trailing_7d": float(i % 7), "lag_1w": float((i * 3) % 11), "lag_2w": float(i)})
        target = [5.0 + 2.0 * float(row["lag_2w"]) for row in rows]
        scores = rolling_origin_scores(rows, target, min_train=8, horizon=2)
        self.assertEqual(scores["selection"]["winner"], "lag_2w")
        self.assertAlmostEqual(scores["lag_2w"]["rmse"], 0.0)


if __name__ == "__main__":
    unittest.main()
