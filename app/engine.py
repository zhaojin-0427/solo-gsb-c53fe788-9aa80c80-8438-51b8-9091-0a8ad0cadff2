"""Exact electrical model and exhaustive wiring search.

Inputs are two-decimal measurements, so they are converted to ``Fraction``.
All knee locations, quadratic extrema and ranking comparisons remain exact.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Group:
    id: str
    voc: Fraction
    isc: Fraction


@dataclass(frozen=True)
class Segment:
    """One linear current range: I = a*V + b, v0 <= V <= v1."""

    v0: Fraction
    v1: Fraction
    a: Fraction
    b: Fraction


@dataclass(frozen=True)
class Curve:
    segments: tuple[Segment, ...]
    voc: Fraction


@dataclass(frozen=True)
class Peak:
    voltage: Fraction
    current: Fraction
    power: Fraction


@dataclass(frozen=True)
class WiringResult:
    wiring: tuple[tuple[str, ...], ...]
    curve: Curve
    peak: Peak


def group_voltage(group: Group, current: Fraction) -> Fraction:
    return max(group.voc * (Fraction(1) - current / group.isc), Fraction(0))


def string_curve(groups: Sequence[Group]) -> Curve:
    """Return the ascending-voltage piecewise-linear V-I curve of one string."""

    if not groups:
        raise ValueError("A string must contain at least one group")

    max_current = max(group.isc for group in groups)
    thresholds = sorted({group.isc for group in groups}, reverse=True)

    def voltage_at(current: Fraction) -> Fraction:
        return sum((group_voltage(group, current) for group in groups), Fraction(0))

    segments: list[Segment] = []
    upper_voltage = Fraction(0)

    # Walk from I=Isc,max toward I=0. At a knee, every group with that Isc
    # changes from the clamped zero-voltage branch to its linear branch.
    for lower_current in thresholds[1:]:
        active = tuple(group for group in groups if group.isc > lower_current)
        resistance = sum((group.voc / group.isc for group in active), Fraction(0))
        a = -Fraction(1) / resistance
        b = sum((group.voc for group in active), Fraction(0)) / resistance
        lower_voltage = voltage_at(lower_current)
        segments.append(Segment(upper_voltage, lower_voltage, a, b))
        upper_voltage = lower_voltage

    active = tuple(g for g in groups if g.isc > 0)
    resistance = sum((group.voc / group.isc for group in active), Fraction(0))
    a = -Fraction(1) / resistance
    b = sum((group.voc for group in active), Fraction(0)) / resistance
    open_circuit_voltage = sum((group.voc for group in groups), Fraction(0))
    segments.append(Segment(upper_voltage, open_circuit_voltage, a, b))

    return Curve(tuple(segments), open_circuit_voltage)


def parallel_curve(string_curves: Sequence[Curve]) -> Curve:
    """Combine strings that share one terminal voltage.

    String currents are summed on each interval. At its own open-circuit knee
    a string contributes zero current and is omitted from the next interval.
    """

    if not string_curves:
        raise ValueError("A wiring must contain at least one string")

    breakpoints = {Fraction(0)}
    for curve in string_curves:
        for segment in curve.segments:
            breakpoints.update((segment.v0, segment.v1))
    breakpoints = sorted(breakpoints)
    segments: list[Segment] = []

    for x0, x1 in zip(breakpoints, breakpoints[1:]):
        active: list[Curve] = []
        for curve in string_curves:
            string_current = _string_current_at(curve, x0)
            # Include it when it still has a positive-current interval to the
            # right. Checking current at x0 also handles coincident knees.
            if curve.voc > x0 and string_current > 0:
                active.append(curve)

        a = sum((_right_segment_at(curve, x0).a for curve in active), Fraction(0))
        b = sum((_right_segment_at(curve, x0).b for curve in active), Fraction(0))
        segments.append(Segment(x0, x1, a, b))

    return Curve(tuple(segments), breakpoints[-1])


def _segment_at(curve: Curve, voltage: Fraction) -> Segment:
    for segment in curve.segments:
        if segment.v0 <= voltage <= segment.v1:
            return segment
    raise ValueError("Voltage is outside this curve")


def _right_segment_at(curve: Curve, voltage: Fraction) -> Segment:
    """Select the linear segment immediately to the right of a breakpoint."""

    for segment in curve.segments:
        if segment.v0 <= voltage < segment.v1:
            return segment
    raise ValueError("Voltage is outside this curve")


def _string_current_at(curve: Curve, voltage: Fraction) -> Fraction:
    if voltage < 0 or voltage > curve.voc:
        return Fraction(0)
    segment = _segment_at(curve, voltage)
    return max(segment.a * voltage + segment.b, Fraction(0))


def current_at(curve: Curve, voltage: Fraction) -> Fraction:
    # For a combined curve, summing string currents is only possible when its
    # constituents are known. Curve segments already contain summed linear
    # coefficients, and zeroing at the final endpoint protects the boundary.
    if voltage < 0 or voltage > curve.voc:
        return Fraction(0)
    segment = _segment_at(curve, voltage)
    return max(segment.a * voltage + segment.b, Fraction(0))


def power_at(curve: Curve, voltage: Fraction) -> Fraction:
    return voltage * current_at(curve, voltage)


def peak_power(curve: Curve) -> Peak:
    """Find breakpoints and quadratic interior extrema, then the global peak."""

    best_voltage = Fraction(0)
    best_power = Fraction(0)

    def consider(voltage: Fraction, power: Fraction) -> None:
        nonlocal best_voltage, best_power
        if power > best_power or (power == best_power and voltage < best_voltage):
            best_power = power
            best_voltage = voltage

    breakpoints = {Fraction(0), curve.voc}
    for segment in curve.segments:
        breakpoints.update((segment.v0, segment.v1))
        # P = a*V^2+b*V. Its stationary point is -b/(2a).
        if segment.a != 0:
            vertex = -segment.b / (2 * segment.a)
            if segment.v0 < vertex < segment.v1:
                consider(vertex, segment.a * vertex * vertex + segment.b * vertex)

    for breakpoint in breakpoints:
        consider(breakpoint, power_at(curve, breakpoint))

    return Peak(best_voltage, current_at(curve, best_voltage), best_power)


def canonical_wiring(
    assignment: Sequence[Sequence[str]],
) -> tuple[tuple[str, ...], ...]:
    strings = tuple(
        sorted(tuple(sorted(dict.fromkeys(groups))) for groups in assignment if groups)
    )
    return tuple(sorted(strings))


def enumerate_wirings(
    group_ids: Sequence[str], max_strings: int = 3
) -> Iterable[tuple[tuple[str, ...], ...]]:
    """Enumerate set partitions into one, two, or three non-empty strings."""

    ids = sorted(group_ids)
    results: set[tuple[tuple[str, ...], ...]] = set()
    labels = [0] * len(ids)

    def fill(position: int, used_blocks: int) -> None:
        if position == len(ids):
            wiring = [[] for _ in range(used_blocks)]
            for index, label in enumerate(labels):
                wiring[label].append(ids[index])
            results.add(canonical_wiring(wiring))
            return

        for label in range(min(used_blocks, max_strings)):
            labels[position] = label
            fill(position + 1, used_blocks)

        if used_blocks < max_strings:
            labels[position] = used_blocks
            fill(position + 1, used_blocks + 1)

    fill(1, 1)
    yield from sorted(results)


def analyze_wiring(
    groups: Sequence[Group], wiring: Sequence[Sequence[str]]
) -> WiringResult:
    by_id = {group.id: group for group in groups}
    canonical = canonical_wiring(wiring)
    curves = [string_curve([by_id[group_id] for group_id in string]) for string in canonical]
    combined = parallel_curve(curves)
    return WiringResult(canonical, combined, peak_power(combined))


def select_best_wiring(groups: Sequence[Group]) -> tuple[WiringResult, int]:
    by_id = {group.id: group for group in groups}
    string_cache: dict[tuple[str, ...], Curve] = {}

    def get_curve(group_ids: tuple[str, ...]) -> Curve:
        if group_ids not in string_cache:
            string_cache[group_ids] = string_curve([by_id[item] for item in group_ids])
        return string_cache[group_ids]

    best: WiringResult | None = None
    candidates = 0
    for wiring in enumerate_wirings(tuple(by_id), 3):
        candidates += 1
        combined = parallel_curve([get_curve(string) for string in wiring])
        result = WiringResult(wiring, combined, peak_power(combined))
        if best is None or _ranking_key(result) < _ranking_key(best):
            best = result

    assert best is not None
    return best, candidates


def _ranking_key(result: WiringResult):
    # Higher power first; fewer strings, lexicographic IDs, then lower voltage.
    return (
        -result.peak.power,
        len(result.wiring),
        result.wiring,
        result.peak.voltage,
    )
