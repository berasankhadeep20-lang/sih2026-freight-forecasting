"""
Application-layer service implementing FR-3 (vessel type recommendation).

Deliberately rule-based, not ML — see architecture doc §2.3 for why.
No repository dependencies: it's a pure function over the vessel class
specs and ports handed to it, which makes it the simplest possible unit
test in the whole system (construct inputs, assert output, done).

`natural_vessel_class()` is exported separately from `recommend_vessel()`
because QueryOrchestrator needs it BEFORE port data is available — see
that module's docstring for why (short version: the forecast needs a
vessel class up front to know which rate series to use, and the cargo's
natural market segment is knowable from cargo volume alone, independent
of which ports are involved).
"""

from __future__ import annotations

from domain.models import NoVesselCapacityError, Port, VesselClassSpec, VesselRecommendation


def natural_vessel_class(
    cargo_volume_tonnes: int, vessel_classes: list[VesselClassSpec]
) -> VesselClassSpec:
    """
    The smallest vessel class whose capacity covers the cargo volume —
    i.e. the market segment this cargo naturally belongs to, independent
    of any port constraint. Used both as the first step of
    `recommend_vessel()` and, separately, by QueryOrchestrator to decide
    which vessel class's rates to forecast.
    """
    if not vessel_classes:
        raise ValueError("vessel_classes must not be empty")

    ascending = sorted(vessel_classes, key=lambda vc: vc.max_dwt)
    if cargo_volume_tonnes > ascending[-1].max_dwt:
        raise NoVesselCapacityError(
            f"Cargo volume {cargo_volume_tonnes}t exceeds the largest known vessel "
            f"class capacity ({ascending[-1].max_dwt}t). No standard vessel class can "
            f"carry this cargo in a single shipment."
        )
    return next(vc for vc in ascending if vc.max_dwt >= cargo_volume_tonnes)


def recommend_vessel(
    cargo_volume_tonnes: int,
    origin_port: Port,
    destination_port: Port,
    vessel_classes: list[VesselClassSpec],
) -> VesselRecommendation:
    """
    Algorithm (FR-3.1, FR-3.2, FR-3.3):
      1. Find the cargo's NATURAL class (see `natural_vessel_class`). We
         never recommend a larger class than this even if it would
         technically fit both ports: chartering a Capesize (~180,000t
         capacity) for a 70,000t parcel wastes capacity the charterer
         still pays for, so "can physically carry it" is not the same
         as "should be recommended."
      2. If the natural class fits both ports, recommend it.
      3. If not, step DOWN through progressively smaller classes (never
         up) until one fits both ports — this reflects the real
         operational fallback of using a smaller vessel when a port
         can't take the natural size, at the cost of needing extra
         voyages or partial loading elsewhere (out of scope to plan
         here, but the recommendation is flagged as constrained so a
         human knows to think about that).
      4. If cargo exceeds even the largest class's capacity, that's a
         hard error (FR-3.3's "no vessel class fits" case) — raised by
         `natural_vessel_class` and propagated here.
      5. If even the smallest class doesn't fit both ports, fall back to
         it anyway and name the binding constraint — the alternative
         (returning nothing) is less useful to a logistics manager.
    """
    ascending = sorted(vessel_classes, key=lambda vc: vc.max_dwt)
    natural = natural_vessel_class(cargo_volume_tonnes, vessel_classes)
    natural_index = ascending.index(natural)

    for i in range(natural_index, -1, -1):
        vc = ascending[i]
        origin_fits, origin_reason = _fits_port(vc, origin_port)
        dest_fits, dest_reason = _fits_port(vc, destination_port)
        if origin_fits and dest_fits:
            if i == natural_index:
                reason = (
                    f"{vc.vessel_class.value} is the class naturally sized for "
                    f"{cargo_volume_tonnes}t and fits within both {origin_port.name}'s "
                    f"and {destination_port.name}'s draft/LOA/beam limits."
                )
            else:
                _, blocking_reason = _fits_port(natural, origin_port)
                if blocking_reason is None:
                    _, blocking_reason = _fits_port(natural, destination_port)
                reason = (
                    f"The natural class for {cargo_volume_tonnes}t is "
                    f"{natural.vessel_class.value}, but {blocking_reason}. "
                    f"Stepped down to {vc.vessel_class.value}, which fits both ports."
                )
            return VesselRecommendation(
                vessel_class=vc.vessel_class,
                reason=reason,
                is_constrained=(i != natural_index),
            )

    # Not even the smallest class fits both ports — genuine infeasibility.
    smallest = ascending[0]
    _, origin_reason = _fits_port(smallest, origin_port)
    _, dest_reason = _fits_port(smallest, destination_port)
    binding = origin_reason or dest_reason or "unknown constraint"
    return VesselRecommendation(
        vessel_class=smallest.vessel_class,
        reason=(
            f"No standard vessel class fits both ports cleanly for this cargo volume, "
            f"not even the smallest class ({smallest.vessel_class.value}). Recommending "
            f"it as the closest alternative. Binding constraint: {binding}"
        ),
        is_constrained=True,
    )


def _fits_port(vc: VesselClassSpec, port: Port) -> tuple[bool, str | None]:
    """Returns (fits, reason_if_not) — the reason names the specific
    binding constraint so the caller never has to guess why."""
    if vc.typical_draft_m > port.max_draft_m:
        return False, (
            f"{vc.vessel_class.value} draft {vc.typical_draft_m}m exceeds "
            f"{port.name}'s max draft {port.max_draft_m}m"
        )
    if vc.typical_loa_m > port.max_loa_m:
        return False, (
            f"{vc.vessel_class.value} LOA {vc.typical_loa_m}m exceeds "
            f"{port.name}'s max LOA {port.max_loa_m}m"
        )
    if vc.typical_beam_m > port.max_beam_m:
        return False, (
            f"{vc.vessel_class.value} beam {vc.typical_beam_m}m exceeds "
            f"{port.name}'s max beam {port.max_beam_m}m"
        )
    return True, None
