import unittest
from fractions import Fraction

from app.engine import (
    Group,
    canonical_wiring,
    enumerate_wirings,
    parallel_curve,
    peak_power,
    select_best_wiring,
    string_curve,
)


def make_groups(values):
    return [Group(gid, Fraction(voc), Fraction(isc)) for gid, voc, isc in values]


class EngineTests(unittest.TestCase):
    def test_mismatched_string_has_bypass_knee(self):
        groups = make_groups([("A", "40", "10"), ("B", "40", "8")])
        curve = string_curve(groups)

        self.assertEqual(len(curve.segments), 2)
        self.assertEqual(curve.voc, Fraction(80))
        # At I=8 A, B reaches its Isc and is bypassed; A contributes 8 V.
        knee = curve.segments[0].v1
        self.assertEqual(knee, Fraction(8))
        self.assertEqual(curve.segments[0].a, Fraction(-1, 4))
        self.assertEqual(curve.segments[0].b, Fraction(10))
        peak = peak_power(curve)
        self.assertEqual(peak.power, Fraction(1600, 9))

    def test_parallel_curve_keeps_internal_bypass_knee(self):
        groups = make_groups([
            ("A", "40", "10"),
            ("B", "40", "8"),
            ("C", "40", "10"),
        ])
        mismatched_string = string_curve([groups[0], groups[1]])
        combined = parallel_curve([mismatched_string, string_curve([groups[2]])])

        self.assertEqual([segment.v0 for segment in combined.segments], [0, 8, 40])
        self.assertEqual(combined.segments[0].b, Fraction(20))
        self.assertEqual(combined.segments[1].v1, Fraction(40))
        self.assertEqual(combined.segments[2].a, Fraction(-1, 9))

    def test_parallel_mismatched_pair_is_better_than_series(self):
        groups = make_groups([("A", "40", "10"), ("B", "40", "8")])
        series = peak_power(string_curve(groups))
        parallel = peak_power(
            parallel_curve([string_curve([groups[0]]), string_curve([groups[1]])])
        )
        self.assertEqual(series.power, Fraction(1600, 9))
        self.assertEqual(parallel.power, Fraction(180))
        best, count = select_best_wiring(groups)
        self.assertEqual(best.peak.power, Fraction(180))
        self.assertEqual(best.wiring, (("A",), ("B",)))
        self.assertEqual(count, 2)

    def test_enumeration_size_and_nonempty_unique_strings(self):
        ids = [f"G{i}" for i in range(1, 10)]
        wirings = list(enumerate_wirings(ids))
        # S(9,1)+S(9,2)+S(9,3)=1+255+3025
        self.assertEqual(len(wirings), 3281)
        for wiring in wirings:
            flattened = [group_id for string in wiring for group_id in string]
            self.assertTrue(all(string for string in wiring))
            self.assertEqual(sorted(flattened), sorted(ids))

    def test_equal_power_prefers_one_string_and_lexicographic_order(self):
        groups = make_groups([
            ("B", "10", "10"),
            ("A", "10", "10"),
            ("C", "10", "10"),
        ])
        best, _ = select_best_wiring(groups)
        self.assertEqual(len(best.wiring), 1)
        self.assertEqual(best.wiring[0], ("A", "B", "C"))

    def test_canonical_wiring_sorts_within_and_between_strings(self):
        wiring = canonical_wiring([["D", "B"], ["A", "C"]])
        self.assertEqual(wiring, (("A", "C"), ("B", "D")))

    def test_example_baseline_is_improved_by_balanced_strings(self):
        values = [
            ("G1", "40", "10"),
            ("G2", "40", "8"),
            ("G3", "38", "10"),
            ("G4", "38", "8"),
        ]
        groups = make_groups(values)
        best, count = select_best_wiring(groups)
        self.assertEqual(count, 14)
        self.assertEqual(best.wiring, (("G1", "G3"), ("G2", "G4")))
        self.assertEqual(best.peak.power, Fraction(351))


if __name__ == "__main__":
    unittest.main()
