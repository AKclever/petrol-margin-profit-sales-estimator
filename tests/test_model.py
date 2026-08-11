import unittest

import model


class GeographicModelTest(unittest.TestCase):
    def test_every_quarter_has_each_state_once(self):
        rows = model.load_exposure()
        keys = {(row["quarter"], row["state"]) for row in rows}
        self.assertEqual(len(keys), len(rows))
        self.assertEqual(len(rows), 12 * 27)

    def test_sensitivity_is_nonzero_and_matches_range(self):
        _, summary = model.run()
        low, high = summary["geographic_weight_range_cpg"]
        self.assertGreater(summary["geographic_weight_uncertainty_cpg"], 0)
        self.assertAlmostEqual(summary["geographic_weight_uncertainty_cpg"], high - low, places=4)

    def test_all_volume_weights_are_marked_estimated(self):
        self.assertTrue(all(row["volume_weight_estimated"] == "true" for row in model.load_exposure()))


if __name__ == "__main__":
    unittest.main()
