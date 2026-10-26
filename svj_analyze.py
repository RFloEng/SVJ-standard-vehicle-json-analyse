# Copyright 2026 RFloEng
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
svj_analyze — library-wide analysis for SVJ (Standard Vehicle JSON) files.

Pure stdlib (+ openpyxl for XLSX export). No svj-py dependency so it runs
anywhere. Feed it one or more inputs — each can be either:

    - a folder (scanned recursively, any depth), or
    - a .zip archive (scanned recursively, any depth, in-memory)

…and it produces:

    - index.json   : one row per vehicle, with the stats worth sorting on
    - tires.json   : unique tire footprints, with per-car attribution
    - tires.svj.json : tires-only SVJ document, every tire set de-duplicated
    - curves.json  : engine torque, damper bump/rebound, spring rates
    - library.xlsx : 3-sheet workbook (Vehicles / Tires / Curves index)

Usage:
    python svj_analyze.py <folder_or_zip> [<more> ...] [--out <out_dir>]
    python svj_analyze.py check <folder_or_zip> [<more> ...]
"""

from __future__ import annotations

__version__ = "0.3.0"

import argparse
import hashlib
import json
import math
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

# ------------------------------------------------------------------------ #
# Loading                                                                  #
# ------------------------------------------------------------------------ #


def find_svj_files(root: Path) -> list[Path]:
    """Every *.svj.json under root (recursive, any depth)."""
    return sorted(p for p in root.rglob("*.svj.json") if p.is_file())


def load_svj(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------------ #
# Input sources — folders OR zip archives, any depth                       #
# ------------------------------------------------------------------------ #

@dataclass
class SvjSource:
    """A parsed SVJ document plus a display name describing where it came from."""
    display_name: str   # e.g. "bmw_e30.svj.json" or "library.zip!/cars/bmw.svj.json"
    doc: dict


def iter_sources(input_path: Path) -> Iterable[SvjSource]:
    """Yield SvjSource records from a folder or a .zip archive.

    Folders are walked recursively (any depth). Zip archives are read in-memory
    and also walked recursively — nested subdirectories inside the archive are
    fine. Mixed-case `.ZIP` is accepted.
    """
    if input_path.is_dir():
        yield from _iter_folder(input_path)
    elif input_path.is_file() and input_path.suffix.lower() == ".zip":
        yield from _iter_zip(input_path)
    else:
        raise FileNotFoundError(
            f"{input_path}: not a folder or .zip archive"
        )


def _iter_folder(folder: Path) -> Iterable[SvjSource]:
    for p in find_svj_files(folder):
        try:
            yield SvjSource(display_name=p.name, doc=load_svj(p))
        except Exception as e:
            # Surface as an error record at the caller level
            yield SvjSource(display_name=p.name, doc={"__error__": str(e)})


def _iter_zip(zip_path: Path) -> Iterable[SvjSource]:
    """Read every *.svj.json inside a zip, recursively (any nested depth)."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name_lower = info.filename.lower()
            if not name_lower.endswith(".svj.json"):
                continue
            display = f"{zip_path.name}!/{info.filename}"
            try:
                with zf.open(info, "r") as f:
                    raw = f.read().decode("utf-8", errors="replace")
                doc = json.loads(raw)
                yield SvjSource(display_name=display, doc=doc)
            except Exception as e:
                yield SvjSource(display_name=display, doc={"__error__": str(e)})


# ------------------------------------------------------------------------ #
# Safe getters                                                             #
# ------------------------------------------------------------------------ #

def _dig(d: Any, *keys, default=None):
    cur = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _num(x) -> float | None:
    try:
        if x is None:
            return None
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------ #
# Per-car summarisation                                                    #
# ------------------------------------------------------------------------ #

CORNERS = ("FL", "FR", "RL", "RR")


def _corners(doc: dict) -> dict[str, dict]:
    """Per-corner blocks in the legacy ``suspension.<FL|FR|RL|RR>`` shape.

    SVJ <= 0.97 stores ``suspension.FL`` etc. directly; SVJ >= 0.100 moves the
    wheel/tire/brake data to the ``wheel_stations`` list and the springs and
    dampers to ``constraints`` entries whose id ends in ``_fl``/``_fr``/....
    Both layouts are normalised here so every reader sees one shape.
    """
    legacy = doc.get("suspension")
    if isinstance(legacy, dict) and any(c in legacy for c in CORNERS):
        return legacy
    stations = doc.get("wheel_stations")
    if not isinstance(stations, list):
        return {}
    cons: dict[tuple[str, str], dict] = {}
    for con in doc.get("constraints") or []:
        if not isinstance(con, dict) or con.get("type") not in ("spring", "damper"):
            continue
        cid = str(con.get("id", "")).lower()
        for c in CORNERS:
            if cid.endswith("_" + c.lower()):
                cons[(con["type"], c)] = con
    out: dict[str, dict] = {}
    for st in stations:
        if not isinstance(st, dict):
            continue
        c = st.get("id") or st.get("name")
        if c not in CORNERS:
            continue
        spring = cons.get(("spring", c)) or {}
        damper = cons.get(("damper", c)) or {}
        out[c] = {
            "topology": {"system_type": st.get("topology_hint")},
            "wheel": st.get("wheel") or {},
            "tire": st.get("tire") or {},
            "brake": st.get("brake") or {},
            "spring": {"type": spring.get("spring_type"), "rate": spring.get("rate")},
            "damper": {
                "type": damper.get("x_damper_type") or damper.get("damper_type"),
                "bump_curve": damper.get("bump_curve"),
                "rebound_curve": damper.get("rebound_curve"),
            },
            "_est": bool(st.get("_est") or damper.get("_est")),
        }
    return out


def _peak_of_curve(curve) -> tuple[float | None, float | None]:
    """Given [[x,y],...] return (x_at_peak_y, peak_y)."""
    if not isinstance(curve, list) or not curve:
        return (None, None)
    best = None
    for pt in curve:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        x, y = _num(pt[0]), _num(pt[1])
        if x is None or y is None:
            continue
        if best is None or y > best[1]:
            best = (x, y)
    if best is None:
        return (None, None)
    return best


def _power_curve_from_torque(torque_curve) -> list[list[float]]:
    """P[kW] = T[Nm] * rpm * 2pi / 60 / 1000."""
    out = []
    if not isinstance(torque_curve, list):
        return out
    for pt in torque_curve:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        rpm, t = _num(pt[0]), _num(pt[1])
        if rpm is None or t is None:
            continue
        out.append([rpm, t * rpm * 2 * math.pi / 60.0 / 1000.0])
    return out


def _interp_curve(pts: list, qx: float) -> float | None:
    """Linear interpolation of a sorted [[x, y], …] curve at query point qx."""
    if not isinstance(pts, list) or not pts:
        return None
    clean = [(x, y) for p in pts
             if isinstance(p, (list, tuple)) and len(p) >= 2
             for x, y in [(_num(p[0]), _num(p[1]))]
             if x is not None and y is not None]
    if not clean:
        return None
    clean.sort(key=lambda p: p[0])
    if qx <= clean[0][0]:
        return clean[0][1]
    if qx >= clean[-1][0]:
        return clean[-1][1]
    for i in range(1, len(clean)):
        if clean[i][0] >= qx:
            x0, y0 = clean[i - 1]
            x1, y1 = clean[i]
            t = (qx - x0) / (x1 - x0) if x1 != x0 else 0
            return y0 + t * (y1 - y0)
    return None


def _tire_key(wheel: dict, tires_sets: dict | None = None) -> tuple | None:
    """Identity of a tire footprint: (rim_diam_mm, rim_width_mm, loaded_r_mm).

    When *tires_sets* is supplied and the wheel carries a *set_ref*, values from
    ``tires.sets.<set_ref>`` take precedence over the wheel block.  This is needed
    for AC→SVJ files where ``wheel.rim_diameter`` is hardcoded to a placeholder
    (0.432 m) and the authoritative rim data lives in ``tires.sets``.
    """
    if not isinstance(wheel, dict):
        return None
    rd = _num(wheel.get("rim_diameter"))
    rw = _num(wheel.get("rim_width"))
    lr = _num(wheel.get("loaded_radius"))
    # Prefer tires.sets data when set_ref is available (AC→SVJ converter pattern)
    if tires_sets:
        sref = wheel.get("set_ref")
        if sref:
            ts = tires_sets.get(sref) or {}
            rim = ts.get("rim") or {}
            dims = ts.get("dimensions") or {}
            # rim.diameter is authoritative; wheel.rim_diameter may be a placeholder
            rd_ts = _num(rim.get("diameter"))
            if rd_ts is not None:
                rd = rd_ts
            # rim.width_nominal is available (approximated as section width in AC→SVJ)
            rw_ts = _num(rim.get("width_nominal"))
            if rw_ts is not None:
                rw = rw_ts
            # loaded_radius must be derived from overall_diameter (not stored directly)
            if lr is None:
                od = _num(dims.get("overall_diameter"))
                if od is not None:
                    lr = od / 2
    if rd is None and rw is None and lr is None:
        return None
    return (
        round(rd * 1000, 1) if rd is not None else None,
        round(rw * 1000, 1) if rw is not None else None,
        round(lr * 1000, 1) if lr is not None else None,
    )


def _tire_label(key: tuple) -> str:
    """Human label for a tire footprint."""
    rd_mm, rw_mm, lr_mm = key
    rim_in = rd_mm / 25.4 if rd_mm else None
    width_in = rw_mm / 25.4 if rw_mm else None
    parts = []
    if width_in is not None:
        parts.append(f"{width_in:.1f}J")
    if rim_in is not None:
        parts.append(f"x{rim_in:.0f}\"")
    base = "".join(parts) if parts else "unspecified"
    if lr_mm and rd_mm:
        sidewall = lr_mm - rd_mm / 2
        if sidewall > 0 and rw_mm:
            aspect = sidewall / rw_mm * 100
            base += f"  (~{aspect:.0f}% AR, R={lr_mm:.0f}mm)"
        elif sidewall > 0:
            base += f"  (R={lr_mm:.0f}mm)"
    return base


def summarize_vehicle(doc: dict, source: str) -> dict[str, Any]:
    meta = doc.get("_metadata", {}) or {}
    info = doc.get("vehicle_info", {}) or {}
    chassis = doc.get("chassis", {}) or {}
    steering = doc.get("steering", {}) or {}
    suspension = _corners(doc)
    powertrain = doc.get("powertrain", {}) or {}
    electric = doc.get("electric", {}) or {}
    tires_sets = (doc.get("tires") or {}).get("sets") or {}

    # Chassis basics
    mass = _num(chassis.get("mass_total"))
    wb = _num(chassis.get("wheelbase"))
    tf = _num(chassis.get("track_front"))
    tr = _num(chassis.get("track_rear"))
    cog = chassis.get("center_of_gravity")
    cog_x = _num(cog[0]) if isinstance(cog, list) and len(cog) > 0 else None
    cog_z = _num(cog[2]) if isinstance(cog, list) and len(cog) > 2 else None
    # Weight distribution (SVJ: X forward, origin at FL wheel center approx)
    # If CoG x and wheelbase are both defined, front fraction = 1 + cog_x/wb
    # since cog_x is negative (behind front axle) for typical cars.
    front_frac = None
    if cog_x is not None and wb and wb > 0:
        front_frac = max(0.0, min(1.0, 1.0 + cog_x / wb))

    # Powertrain
    engine = powertrain.get("engine") or {}
    torque_curve = engine.get("torque_curve")
    # Engine details
    engine_idle_rpm         = _num(engine.get("idle_rpm"))
    engine_max_rpm          = _num(engine.get("max_rpm"))
    engine_displacement_cc  = _num(engine.get("displacement"))
    engine_configuration    = engine.get("configuration")
    peak_rpm_t, peak_torque = _peak_of_curve(torque_curve)
    power_curve = _power_curve_from_torque(torque_curve)
    peak_rpm_p, peak_power_kw = _peak_of_curve(power_curve)
    gearbox = powertrain.get("gearbox") or {}
    diffs = powertrain.get("differentials") or []
    final_drive = None
    if diffs:
        final_drive = _num(diffs[0].get("final_drive"))

    # EV?
    motors = electric.get("motors") if isinstance(electric, dict) else None
    is_ev = bool(motors) or _dig(powertrain, "layout") in ("AWD-EV", "RWD-EV", "FWD-EV")
    battery_kwh = _num(_dig(electric, "battery", "capacity_kwh"))

    # Suspension / tires / brakes — walk all 4 corners
    corners_out: dict[str, Any] = {}
    tires: dict[str, Any] = {}
    for c in CORNERS:
        corner = suspension.get(c) or {}
        top = corner.get("topology") or {}
        wheel = corner.get("wheel") or {}
        spring = corner.get("spring") or {}
        damper = corner.get("damper") or {}
        brake = corner.get("brake") or {}
        disc = brake.get("disc") if isinstance(brake, dict) else {}
        key = _tire_key(wheel, tires_sets)
        tires[c] = {
            "key": list(key) if key else None,
            "label": _tire_label(key) if key else None,
            "rim_diameter_mm": (key[0] if key else None),
            "rim_width_mm": (key[1] if key else None),
            "loaded_radius_mm": (key[2] if key else None),
            "wheel_mass_kg": _num(wheel.get("mass")),
            "wheel_inertia_kgm2": _num(wheel.get("rotational_inertia")),
        }
        corners_out[c] = {
            "topology": top.get("system_type"),
            "spring_type": spring.get("type"),
            "spring_rate_Nm": _num(spring.get("rate")),
            "damper_type": damper.get("type"),
            "damper_bump_points": len(damper.get("bump_curve") or []),
            "damper_rebound_points": len(damper.get("rebound_curve") or []),
            "brake_disc_type": _dig(disc, "type") if isinstance(disc, dict) else None,
            "brake_disc_mm": (_num(_dig(disc, "outer_diameter")) or 0) * 1000 or None,
            "estimated": bool(corner.get("_est")),
        }

    # Topology summary
    top_f = corners_out["FL"]["topology"] or corners_out["FR"]["topology"]
    top_r = corners_out["RL"]["topology"] or corners_out["RR"]["topology"]

    # Spring F/R
    sp_f = _num(corners_out["FL"]["spring_rate_Nm"]) or _num(corners_out["FR"]["spring_rate_Nm"])
    sp_r = _num(corners_out["RL"]["spring_rate_Nm"]) or _num(corners_out["RR"]["spring_rate_Nm"])

    # Unique tire count per car
    unique_tires = set()
    for c in CORNERS:
        k = tires[c]["key"]
        if k:
            unique_tires.add(tuple(k))

    # Completeness / _est flags (rough)
    est_flags = 0
    for c in CORNERS:
        if corners_out[c]["estimated"]:
            est_flags += 1
    confidence = _dig(meta, "data_origin", "confidence")

    _COMP_KEYS = [
        "make", "model", "year", "drive_type",
        "mass_total_kg", "wheelbase_m", "track_front_m", "track_rear_m",
        "cog_height_m", "front_weight_fraction",
        "steering_type", "steering_ratio",
        "topology_front", "topology_rear",
        "spring_rate_front_Nm", "spring_rate_rear_Nm",
        "peak_torque_Nm", "peak_torque_rpm", "peak_power_kW", "peak_power_rpm",
        "engine_idle_rpm", "engine_max_rpm", "engine_displacement_cc", "engine_configuration",
        "gearbox_type", "final_drive", "data_confidence",
    ]
    result = {
        "source": source,
        "spec_version": meta.get("version"),
        "data_confidence": confidence,
        "make": info.get("make"),
        "model": info.get("model"),
        "year": info.get("year"),
        "variant": info.get("variant"),
        "drive_type": info.get("drive_type"),
        "is_ev": is_ev,
        "mass_total_kg": mass,
        "wheelbase_m": wb,
        "track_front_m": tf,
        "track_rear_m": tr,
        "cog_height_m": (-cog_z) if cog_z is not None else None,  # Z-down → positive height
        "front_weight_fraction": front_frac,
        "steering_type": steering.get("type") if isinstance(steering, dict) else None,
        "steering_ratio": (
            _num(steering.get("overall_ratio")) if isinstance(steering, dict) else None
        ),
        "topology_front": top_f,
        "topology_rear": top_r,
        "spring_rate_front_Nm": sp_f,
        "spring_rate_rear_Nm": sp_r,
        "peak_torque_Nm": peak_torque,
        "peak_torque_rpm": peak_rpm_t,
        "peak_power_kW": peak_power_kw,
        "peak_power_hp": (peak_power_kw * 1.341) if peak_power_kw else None,
        "peak_power_rpm": peak_rpm_p,
        "engine_idle_rpm":         engine_idle_rpm,
        "engine_max_rpm":          engine_max_rpm,
        "engine_displacement_cc":  engine_displacement_cc,
        "engine_configuration":    engine_configuration,
        "gearbox_type": gearbox.get("type"),
        "gear_count": len(gearbox.get("ratios") or []) if isinstance(gearbox, dict) else 0,
        "final_drive": final_drive,
        "battery_kwh": battery_kwh,
        "corners": corners_out,
        "tires_by_corner": tires,
        "unique_tires_on_car": len(unique_tires),
        "estimated_corners": est_flags,
        "power_to_weight_kW_per_tonne": (
            peak_power_kw / (mass / 1000.0) if (peak_power_kw and mass and mass > 0) else None
        ),
    }
    result["completeness_pct"] = round(
        sum(1 for k in _COMP_KEYS if result.get(k) is not None) / len(_COMP_KEYS) * 100, 1
    )
    return result


# ------------------------------------------------------------------------ #
# Library-wide aggregations                                                #
# ------------------------------------------------------------------------ #

def build_tire_catalogue(vehicles: list[dict]) -> list[dict]:
    """Unique tire keys with attribution."""
    bucket: dict[tuple, dict] = defaultdict(lambda: {
        "cars": [],
        "corners": defaultdict(int),
    })
    for v in vehicles:
        label = f"{v['make']} {v['model']} ({v['year']})"
        for c in CORNERS:
            t = v["tires_by_corner"][c]
            if not t["key"]:
                continue
            key = tuple(t["key"])
            b = bucket[key]
            b["corners"][c] += 1
            if label not in b["cars"]:
                b["cars"].append(label)

    out = []
    for key, b in bucket.items():
        rd_mm, rw_mm, lr_mm = key
        out.append({
            "key": list(key),
            "label": _tire_label(key),
            "rim_diameter_mm": rd_mm,
            "rim_diameter_in": round(rd_mm / 25.4, 1) if rd_mm else None,
            "rim_width_mm": rw_mm,
            "rim_width_in": round(rw_mm / 25.4, 2) if rw_mm else None,
            "loaded_radius_mm": lr_mm,
            "corner_counts": dict(b["corners"]),
            "car_count": len(b["cars"]),
            "cars": b["cars"],
        })
    out.sort(key=lambda x: (x["rim_diameter_mm"] or 0, x["rim_width_mm"] or 0))
    return out


def _set_fingerprint(tset: dict) -> str:
    """Content hash of a tire set, ignoring its free-text description."""
    body = {k: v for k, v in tset.items() if k != "description"}
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


class TireLibrary:
    """Accumulates every ``tires.sets.*`` entry of many SVJ docs into one
    de-duplicated, tires-only SVJ document.

    Two sets with identical content (description aside) collapse to one entry.
    A set that reuses a name but differs in content is kept under ``<name>__<hash6>``.
    The Race07 slip curves a set refers to (LatCurve/BrakingCurve/TractiveCurve)
    are copied into the set so each entry is self-contained.
    """

    def __init__(self) -> None:
        self._by_hash: dict[str, str] = {}      # content hash -> library key
        self._sets: dict[str, dict] = {}        # library key -> set
        self.total_seen = 0

    def add_doc(self, doc: dict, car_label: str, source: str) -> int:
        tires = doc.get("tires")
        if not isinstance(tires, dict):
            return 0
        sets = tires.get("sets")
        if not isinstance(sets, dict):
            return 0
        curves = tires.get("x_race07_slip_curves")
        added = 0
        for name, raw in sets.items():
            if not isinstance(raw, dict):
                continue
            self.total_seen += 1
            tset = dict(raw)
            x07 = tset.get("x_race07")
            if isinstance(curves, dict) and isinstance(x07, dict):
                used = {}
                for ref in ("LatCurve", "BrakingCurve", "TractiveCurve"):
                    cname = x07.get(ref)
                    if cname in curves:
                        used[cname] = curves[cname]
                if used:
                    tset["x_race07_slip_curves"] = used
            h = _set_fingerprint(tset)
            key = self._by_hash.get(h)
            if key is None:
                key = name if name not in self._sets else f"{name}__{h[:6]}"
                self._by_hash[h] = key
                tset["x_library"] = {"used_by": [], "source_names": [], "source_files": []}
                self._sets[key] = tset
                added += 1
            lib = self._sets[key]["x_library"]
            if car_label not in lib["used_by"]:
                lib["used_by"].append(car_label)
            if name not in lib["source_names"]:
                lib["source_names"].append(name)
            if source not in lib["source_files"]:
                lib["source_files"].append(source)
        return added

    def to_document(self, inputs: list[str], vehicle_count: int) -> dict:
        ordered = dict(sorted(self._sets.items()))
        return {
            "_metadata": {
                "specification": "SVJ",
                "version": "0.103",
                "description": "Tire library: every tires.sets entry from the scanned "
                               "SVJ files, de-duplicated. Tires only, no vehicle data.",
                "author": f"svj_analyze {__version__}",
                "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "x_library": {
                    "inputs": inputs,
                    "vehicles_scanned": vehicle_count,
                    "tire_sets_seen": self.total_seen,
                    "tire_sets_unique": len(ordered),
                },
            },
            "tires": {"sets": ordered},
        }


def extract_curves(doc: dict, car_id: str) -> list[dict]:
    """Return a list of curve records — easy to plot later."""
    out = []
    engine = _dig(doc, "powertrain", "engine") or {}
    tc = engine.get("torque_curve")
    if isinstance(tc, list) and tc:
        out.append({"car": car_id, "kind": "engine_torque", "corner": None,
                    "x_unit": "rpm", "y_unit": "Nm", "points": tc})
        # derived power
        pc = _power_curve_from_torque(tc)
        if pc:
            out.append({"car": car_id, "kind": "engine_power", "corner": None,
                        "x_unit": "rpm", "y_unit": "kW", "points": pc,
                        "derived": True})

    for c in CORNERS:
        corner = _corners(doc).get(c) or {}
        damper = corner.get("damper") or {}
        for k in ("bump_curve", "rebound_curve"):
            pts = damper.get(k)
            if isinstance(pts, list) and pts:
                out.append({"car": car_id, "kind": f"damper_{k[:-6]}", "corner": c,
                            "x_unit": "m/s", "y_unit": "N", "points": pts})
    return out


# ------------------------------------------------------------------------ #
# Handling Fingerprint — 8-axis normalised radar                           #
# ------------------------------------------------------------------------ #

def _fp_contact_patch(v: dict) -> float | None:
    """Average rim width (mm) across corners that have data."""
    ws = [w for c in CORNERS
          if (t := v.get("tires_by_corner", {}).get(c)) and t.get("rim_width_mm") is not None
          for w in [_num(t["rim_width_mm"])]
          if w is not None]
    return sum(ws) / len(ws) if ws else None


def _fp_damper_at_02(v: dict) -> float | None:
    """Average bump-damper force at 0.2 m/s across corners that have a curve."""
    vals = []
    for c in CORNERS:
        pts = (v.get("corners") or {}).get(c, {}).get("damper_bump")
        if pts:
            y = _interp_curve(pts, 0.2)
            if y is not None:
                vals.append(y)
    return sum(vals) / len(vals) if vals else None


# Each entry: (key, label, invert)
#   invert=True  → lower raw value maps to higher normalised score
#                  (outer rim of radar = "better" direction)
FP_DIM_DEFS: list[tuple[str, str, bool]] = [
    ("mass",        "Mass (light→)",       True),
    ("balance",     "F/R balance",         False),
    ("cog",         "CoG height (low→)",   True),
    ("contact",     "Contact patch",       False),
    ("spring_f",    "Spring F (N/m)",      False),
    ("spring_r",    "Spring R (N/m)",      False),
    ("damper",      "Damper @ 0.2 m/s",    False),
    ("torque",      "Torque @ 4000 rpm",   False),
    ("pw_ratio",    "Power/weight (kW/t)", False),
]


def _fp_raw(v: dict) -> dict[str, float | None]:
    """Extract the 9 raw fingerprint values from a summarised vehicle dict."""
    fwf = _num(v.get("front_weight_fraction"))
    return {
        "mass":     _num(v.get("mass_total_kg")),
        "balance":  (1.0 - 2.0 * abs(fwf - 0.5)) if fwf is not None else None,
        "cog":      _num(v.get("cog_height_m")),
        "contact":  _fp_contact_patch(v),
        "spring_f": _num(v.get("spring_rate_front_Nm")),
        "spring_r": _num(v.get("spring_rate_rear_Nm")),
        "damper":   _fp_damper_at_02(v),
        "torque":   _interp_curve(v.get("torque_curve") or [], 4000),
        "pw_ratio": _num(v.get("power_to_weight_kW_per_tonne")),
    }


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = p / 100.0 * (len(s) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] + frac * (s[hi] - s[lo])


def compute_fingerprint_norms(vehicles: list[dict]) -> dict[str, dict | None]:
    """Compute {p5, p95} for each fingerprint dimension across the library."""
    norms: dict[str, dict | None] = {}
    for key, _label, _inv in FP_DIM_DEFS:
        raws = [v for d in vehicles if (v := _fp_raw(d).get(key)) is not None]
        if not raws:
            norms[key] = None
            continue
        p5  = _percentile(raws, 5)
        p95 = _percentile(raws, 95)
        norms[key] = {"p5": p5, "p95": p95}
    return norms


def compute_fingerprint(v: dict, norms: dict) -> dict[str, float | None]:
    """Return a dict of 8 normalised [0, 1] scores for one vehicle.

    Values are clamped to [0, 1] and inverted where *invert* is True so that
    the outer edge of the radar chart always represents the "more extreme" or
    "more desirable" end of that dimension (per-axis intent is documented in
    FP_DIM_DEFS).  Returns None for a dimension if the raw value is missing
    or the library p5/p95 band collapses to a single value.
    """
    raw = _fp_raw(v)
    result: dict[str, float | None] = {}
    for key, _label, invert in FP_DIM_DEFS:
        x = raw.get(key)
        n = norms.get(key)
        if x is None or n is None or n["p5"] == n["p95"]:
            result[key] = None
            continue
        norm = (x - n["p5"]) / (n["p95"] - n["p5"])
        norm = max(0.0, min(1.0, norm))
        result[key] = round(1.0 - norm if invert else norm, 4)
    return result


# ------------------------------------------------------------------------ #
# Completeness heatmap — per-car × per-subtree fill rate                  #
# ------------------------------------------------------------------------ #

def _hm_fraction(vals: list) -> float:
    """Fraction of non-null/non-empty values in a list (0.0 – 1.0)."""
    if not vals:
        return 0.0
    present = sum(1 for x in vals
                  if x is not None and x != "" and x != "?")
    return present / len(vals)


def _hm_corner_frac(v: dict, field: str) -> float:
    """Fraction of corners that have a non-null value for *field*."""
    corners_data = v.get("corners") or {}
    return sum(1 for c in CORNERS
               if corners_data.get(c, {}).get(field) is not None) / 4


def _hm_has_list(v: dict, field: str) -> float:
    """Fraction of corners whose *field* is a non-empty list."""
    corners_data = v.get("corners") or {}
    return sum(1 for c in CORNERS
               if isinstance(corners_data.get(c, {}).get(field), list)
               and corners_data[c][field]) / 4


# Ordered list of (key, label, tooltip, scorer).
HEATMAP_GROUPS: list[tuple[str, str, str, any]] = [
    (
        "identity", "Identity",
        "make, model, year, drive type",
        lambda v: _hm_fraction(
            [v.get(k) for k in ["make", "model", "year", "drive_type"]]),
    ),
    (
        "chassis", "Chassis",
        "mass, wheelbase, track F/R, CoG height, front weight %",
        lambda v: _hm_fraction(
            [v.get(k) for k in [
                "mass_total_kg", "wheelbase_m", "track_front_m",
                "track_rear_m", "cog_height_m", "front_weight_fraction",
            ]]),
    ),
    (
        "engine", "Engine",
        "config, displacement, idle rpm, max rpm, peak torque, peak power",
        lambda v: _hm_fraction(
            [v.get(k) for k in [
                "engine_configuration", "engine_displacement_cc",
                "engine_idle_rpm", "engine_max_rpm",
                "peak_torque_Nm", "peak_power_kW",
            ]]),
    ),
    (
        "curves", "Curves",
        "torque curve present",
        lambda v: (
            1.0 if isinstance(v.get("torque_curve"), list) and v["torque_curve"]
            else 0.0
        ),
    ),
    (
        "suspension", "Suspension",
        "topology + spring rate, all 4 corners",
        lambda v: _hm_fraction(
            [v.get("corners", {}).get(c, {}).get(k)
             for c in CORNERS for k in ["topology", "spring_rate_Nm"]]),
    ),
    (
        "dampers", "Dampers",
        "bump-damper curve present, per corner",
        lambda v: _hm_has_list(v, "damper_bump"),
    ),
    (
        "tires", "Tires",
        "rim diameter present, per corner",
        lambda v: sum(
            1 for c in CORNERS
            if (v.get("tires_by_corner") or {}).get(c, {}).get("rim_diameter_mm")
            is not None
        ) / 4,
    ),
    (
        "drivetrain", "Drivetrain",
        "gearbox type, gear count, final drive",
        lambda v: _hm_fraction(
            [v.get(k) for k in ["gearbox_type", "gear_count", "final_drive"]]),
    ),
    (
        "brakes", "Brakes",
        "brake disc diameter, per corner",
        lambda v: _hm_corner_frac(v, "brake_disc_mm"),
    ),
]


def compute_completeness_heatmap(vehicles: list[dict]) -> list[dict]:
    """Return one record per vehicle with per-subtree completeness scores [0, 1].

    Each record also has an ``overall`` score (simple mean of all group scores)
    and ``car`` / ``source`` identifiers.
    """
    result = []
    for v in vehicles:
        row: dict[str, Any] = {
            "car":    f"{v['make']} {v['model']} ({v.get('year')})",
            "source": v["source"],
        }
        scores = []
        for key, _label, _tip, fn in HEATMAP_GROUPS:
            try:
                score = round(float(fn(v)), 4)
            except Exception:
                score = 0.0
            row[key] = score
            scores.append(score)
        row["overall"] = round(sum(scores) / len(scores), 4) if scores else 0.0
        result.append(row)
    return result


# ------------------------------------------------------------------------ #
# XLSX export                                                              #
# ------------------------------------------------------------------------ #

VEHICLE_COLUMNS = [
    ("source",             "File"),
    ("make",               "Make"),
    ("model",              "Model"),
    ("year",               "Year"),
    ("variant",            "Variant"),
    ("drive_type",         "Drive"),
    ("is_ev",              "EV"),
    ("mass_total_kg",      "Mass (kg)"),
    ("wheelbase_m",        "Wheelbase (m)"),
    ("track_front_m",      "Track F (m)"),
    ("track_rear_m",       "Track R (m)"),
    ("cog_height_m",       "CoG height (m)"),
    ("front_weight_fraction", "F weight %"),
    ("topology_front",     "Susp F"),
    ("topology_rear",      "Susp R"),
    ("spring_rate_front_Nm", "Spring F (N/m)"),
    ("spring_rate_rear_Nm",  "Spring R (N/m)"),
    ("steering_type",      "Steering"),
    ("steering_ratio",     "Steer ratio"),
    ("peak_torque_Nm",     "Peak T (Nm)"),
    ("peak_torque_rpm",    "Peak T rpm"),
    ("peak_power_kW",      "Peak P (kW)"),
    ("peak_power_hp",      "Peak P (hp)"),
    ("peak_power_rpm",     "Peak P rpm"),
    ("engine_configuration",    "Engine config"),
    ("engine_displacement_cc",  "Displ. (cc)"),
    ("engine_idle_rpm",         "Idle rpm"),
    ("engine_max_rpm",          "Max rpm"),
    ("power_to_weight_kW_per_tonne", "P/W (kW/t)"),
    ("gearbox_type",       "Gearbox"),
    ("gear_count",         "Gears"),
    ("final_drive",        "Final drive"),
    ("battery_kwh",        "Battery (kWh)"),
    ("unique_tires_on_car", "Unique tires"),
    ("estimated_corners",  "Est. corners"),
    ("data_confidence",    "Confidence"),
    ("spec_version",       "SVJ ver"),
    ("completeness_pct",   "Complete %"),
]


def export_xlsx(vehicles: list[dict], tires: list[dict],
                curves: list[dict], out_path: Path,
                fingerprints: list[dict] | None = None,
                heatmap: list[dict] | None = None) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = Workbook()
    bold = Font(bold=True, color="FFFFFF", name="Arial")
    header_fill = PatternFill("solid", start_color="1F3A68")
    thin = Side(border_style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    arial = Font(name="Arial")

    # --- Sheet 1: Vehicles -----------------------------------------------
    ws = wb.active
    ws.title = "Vehicles"
    for col_idx, (_, header) in enumerate(VEHICLE_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = bold
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    for r, v in enumerate(vehicles, start=2):
        for col_idx, (key, _) in enumerate(VEHICLE_COLUMNS, start=1):
            val = v.get(key)
            if isinstance(val, bool):
                val = "Yes" if val else "No"
            ws.cell(row=r, column=col_idx, value=val).font = arial
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col_idx, (_, header) in enumerate(VEHICLE_COLUMNS, start=1):
        letter = ws.cell(row=1, column=col_idx).column_letter
        ws.column_dimensions[letter].width = max(12, min(28, len(header) + 4))

    # --- Sheet 2: Tires --------------------------------------------------
    ws2 = wb.create_sheet("Tires")
    tire_cols = [
        ("label",            "Label"),
        ("rim_diameter_in",  "Rim Ø (in)"),
        ("rim_diameter_mm",  "Rim Ø (mm)"),
        ("rim_width_in",     "Rim W (in)"),
        ("rim_width_mm",     "Rim W (mm)"),
        ("loaded_radius_mm", "Loaded R (mm)"),
        ("car_count",        "# cars"),
        ("corner_counts",    "Corners"),
        ("cars",             "Used on"),
    ]
    for col_idx, (_, header) in enumerate(tire_cols, start=1):
        cell = ws2.cell(row=1, column=col_idx, value=header)
        cell.font = bold
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    for r, t in enumerate(tires, start=2):
        for col_idx, (key, _) in enumerate(tire_cols, start=1):
            val = t.get(key)
            if key == "corner_counts" and isinstance(val, dict):
                val = ", ".join(f"{k}×{v}" for k, v in val.items())
            elif key == "cars" and isinstance(val, list):
                val = " | ".join(val)
            ws2.cell(row=r, column=col_idx, value=val).font = arial
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = ws2.dimensions
    widths = [28, 11, 11, 11, 11, 14, 8, 18, 60]
    for i, w in enumerate(widths, start=1):
        ws2.column_dimensions[ws2.cell(row=1, column=i).column_letter].width = w

    # --- Sheet 3: Curves index ------------------------------------------
    ws3 = wb.create_sheet("Curves")
    curve_cols = [
        ("car", "Car"),
        ("kind", "Curve"),
        ("corner", "Corner"),
        ("x_unit", "X unit"),
        ("y_unit", "Y unit"),
        ("npoints", "# points"),
        ("x_min", "X min"),
        ("x_max", "X max"),
        ("y_min", "Y min"),
        ("y_max", "Y max"),
    ]
    for col_idx, (_, header) in enumerate(curve_cols, start=1):
        cell = ws3.cell(row=1, column=col_idx, value=header)
        cell.font = bold
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    for r, cu in enumerate(curves, start=2):
        pts = cu["points"]
        xs = [_num(p[0]) for p in pts if _num(p[0]) is not None]
        ys = [_num(p[1]) for p in pts if _num(p[1]) is not None]
        row = {
            "car": cu["car"], "kind": cu["kind"], "corner": cu.get("corner"),
            "x_unit": cu["x_unit"], "y_unit": cu["y_unit"],
            "npoints": len(pts),
            "x_min": min(xs) if xs else None, "x_max": max(xs) if xs else None,
            "y_min": min(ys) if ys else None, "y_max": max(ys) if ys else None,
        }
        for col_idx, (key, _) in enumerate(curve_cols, start=1):
            ws3.cell(row=r, column=col_idx, value=row[key]).font = arial
    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = ws3.dimensions
    for i in range(1, len(curve_cols) + 1):
        ws3.column_dimensions[ws3.cell(row=1, column=i).column_letter].width = 16

    # --- Sheet 4: Fingerprint (optional) -----------------------------------
    if fingerprints:  # noqa: E501 — kept separate to mirror browser naming
        ws4 = wb.create_sheet("Fingerprint")
        fp_cols = [("car", "Car"), ("source", "File")] + [
            (key, label) for key, label, _ in FP_DIM_DEFS
        ]
        for col_idx, (_, header) in enumerate(fp_cols, start=1):
            cell = ws4.cell(row=1, column=col_idx, value=header)
            cell.font = bold
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border
        for r, fp in enumerate(fingerprints, start=2):
            for col_idx, (key, _) in enumerate(fp_cols, start=1):
                val = fp.get(key)
                if isinstance(val, float):
                    val = round(val, 4)
                ws4.cell(row=r, column=col_idx, value=val).font = arial
        ws4.freeze_panes = "A2"
        ws4.auto_filter.ref = ws4.dimensions
        for i in range(1, len(fp_cols) + 1):
            w = 18 if i > 2 else (60 if i == 1 else 30)
            ws4.column_dimensions[ws4.cell(row=1, column=i).column_letter].width = w

    # --- Sheet 5: Heatmap (optional) ----------------------------------------
    if heatmap:
        # Build a colour-fill palette for 5 buckets: 0%, 25%, 50%, 75%, 100%
        from openpyxl.styles import PatternFill as _PF
        _fills = {
            "full":  _PF("solid", start_color="1E7E47"),   # dark green
            "high":  _PF("solid", start_color="92D050"),   # light green
            "mid":   _PF("solid", start_color="FFBF00"),   # amber
            "low":   _PF("solid", start_color="FF8C00"),   # orange
            "none":  _PF("solid", start_color="C00000"),   # red
        }

        def _score_fill(score: float | None):
            if score is None:
                return _fills["none"]
            if score >= 1.0:
                return _fills["full"]
            if score >= 0.75:
                return _fills["high"]
            if score >= 0.5:
                return _fills["mid"]
            if score >= 0.25:
                return _fills["low"]
            return _fills["none"]

        ws5 = wb.create_sheet("Heatmap")
        hm_cols = (
            [("car", "Car"), ("source", "File"), ("overall", "Overall")]
            + [(k, lbl) for k, lbl, _, _ in HEATMAP_GROUPS]
        )
        for col_idx, (_, header) in enumerate(hm_cols, start=1):
            cell = ws5.cell(row=1, column=col_idx, value=header)
            cell.font = bold
            cell.fill = header_fill
            cell.alignment = center
            cell.border = border
        for r, row in enumerate(heatmap, start=2):
            for col_idx, (key, _) in enumerate(hm_cols, start=1):
                val = row.get(key)
                c = ws5.cell(row=r, column=col_idx, value=val)
                c.font = arial
                if isinstance(val, float) and key not in ("car", "source"):
                    c.fill = _score_fill(val)
                    c.number_format = "0%"
        ws5.freeze_panes = "A2"
        ws5.auto_filter.ref = ws5.dimensions
        ws5.column_dimensions[ws5.cell(row=1, column=1).column_letter].width = 40
        ws5.column_dimensions[ws5.cell(row=1, column=2).column_letter].width = 40
        for i in range(3, len(hm_cols) + 1):
            ws5.column_dimensions[ws5.cell(row=1, column=i).column_letter].width = 14

    wb.save(out_path)


# ------------------------------------------------------------------------ #
# Structural validation (--validate)                                       #
# ------------------------------------------------------------------------ #

def validate_svj(doc: dict, source: str) -> list[dict]:
    """Basic structural validation of an SVJ document.

    Returns a list of issues, each a dict with keys:
        source, field, severity ("error"|"warning"), message
    """
    issues: list[dict] = []

    def _err(field: str, msg: str) -> None:
        issues.append({"source": source, "field": field,
                       "severity": "error", "message": msg})

    def _warn(field: str, msg: str) -> None:
        issues.append({"source": source, "field": field,
                       "severity": "warning", "message": msg})

    # _metadata.version
    if _dig(doc, "_metadata", "version") is None:
        _err("_metadata.version", "Missing required field")

    # vehicle_info.make / model / year
    info = doc.get("vehicle_info") or {}
    if not info.get("make"):
        _err("vehicle_info.make", "Missing or empty")
    if not info.get("model"):
        _err("vehicle_info.model", "Missing or empty")
    if not info.get("year"):
        _warn("vehicle_info.year", "Missing year")

    # chassis.mass_total
    chassis = doc.get("chassis") or {}
    mass = _num(chassis.get("mass_total"))
    if mass is None:
        _err("chassis.mass_total", "Missing or non-numeric")
    elif mass <= 0:
        _err("chassis.mass_total", f"Non-positive mass: {mass}")
    elif not (300 <= mass <= 50_000):
        _warn("chassis.mass_total",
              f"Suspicious mass {mass:.0f} kg (expected 300–50 000)")

    # chassis.wheelbase
    wb = _num(chassis.get("wheelbase"))
    if wb is None:
        _warn("chassis.wheelbase", "Missing wheelbase")
    elif wb <= 0:
        _err("chassis.wheelbase", f"Non-positive wheelbase: {wb}")

    # suspension: rim_diameter per corner
    sus = _corners(doc)
    for c in CORNERS:
        rd = _num(_dig(sus, c, "wheel", "rim_diameter"))
        if rd is None:
            _warn(f"wheel.{c}.rim_diameter",
                  "Missing wheel rim diameter")

    return issues


# ------------------------------------------------------------------------ #
# Physical sanity checks (check subcommand)                                #
# ------------------------------------------------------------------------ #

def sanity_check(doc: dict, source: str) -> list[dict]:
    """Physical sanity checks per vehicle.

    Returns a list of issues, each a dict with keys:
        source, check, severity ("error"|"warning"), message
    """
    issues: list[dict] = []

    def _add(check: str, sev: str, msg: str) -> None:
        issues.append({"source": source, "check": check,
                       "severity": sev, "message": msg})

    chassis    = doc.get("chassis", {}) or {}
    powertrain = doc.get("powertrain", {}) or {}
    suspension = _corners(doc)
    electric   = doc.get("electric", {}) or {}
    tires_sets = (doc.get("tires") or {}).get("sets") or {}

    wb    = _num(chassis.get("wheelbase"))
    cog   = chassis.get("center_of_gravity")
    cog_x = _num(cog[0]) if isinstance(cog, list) and len(cog) > 0 else None
    cog_z = _num(cog[2]) if isinstance(cog, list) and len(cog) > 2 else None

    # 1. CoG x inside [-wheelbase, 0]
    if cog_x is not None and wb is not None and wb > 0:
        if not (-wb <= cog_x <= 0):
            _add("cog_x_range", "error",
                 f"CoG x={cog_x:.3f}m not in [-{wb:.3f}, 0] (wheelbase)")
    elif cog_x is not None and wb is None:
        _add("cog_x_no_wb", "warning",
             "CoG x present but wheelbase missing — cannot check range")

    # 2. CoG height reasonable (0.15–1.80 m)
    if cog_z is not None:
        height = -cog_z
        if not (0.15 <= height <= 1.80):
            _add("cog_height", "warning",
                 f"CoG height {height:.3f}m outside typical [0.15, 1.80]m range")

    # 3. Rim Ø < 2 × loaded radius per corner
    #    Use tires.sets resolved values so AC→SVJ placeholder rim_diameter is handled.
    for c in CORNERS:
        corner = suspension.get(c) or {}
        wheel  = corner.get("wheel") or {}
        key = _tire_key(wheel, tires_sets)
        if key and key[0] is not None and key[2] is not None:
            rd_mm, _, lr_mm = key
            if rd_mm >= 2 * lr_mm:
                _add(f"tire_{c}_geometry", "error",
                     f"{c}: rim_diameter {rd_mm:.0f}mm >= 2×loaded_radius {lr_mm:.0f}mm")

    # 4. Damper curves must be strictly monotonically increasing in x
    for c in CORNERS:
        damper = _dig(suspension, c, "damper") or {}
        for curve_name in ("bump_curve", "rebound_curve"):
            pts = damper.get(curve_name)
            if not (isinstance(pts, list) and len(pts) >= 2):
                continue
            xs = [_num(p[0]) for p in pts
                  if isinstance(p, (list, tuple)) and len(p) >= 2
                  and _num(p[0]) is not None]
            for i in range(1, len(xs)):
                if xs[i] <= xs[i - 1]:
                    _add(f"damper_{c}_{curve_name}_monotonic", "warning",
                         f"{c} {curve_name}: x not strictly increasing at index {i} "
                         f"({xs[i]} <= {xs[i-1]})")
                    break

    # 5. Torque curve values must be non-negative
    tc = _dig(powertrain, "engine", "torque_curve")
    if isinstance(tc, list):
        for i, pt in enumerate(tc):
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                y = _num(pt[1])
                if y is not None and y < 0:
                    _add("torque_nonneg", "warning",
                         f"Torque curve has negative value {y:.1f} Nm at index {i}")
                    break

    # 6. Gear ratios must be strictly descending
    gbox   = powertrain.get("gearbox") or {}
    ratios = gbox.get("ratios") if isinstance(gbox, dict) else None
    if isinstance(ratios, list) and len(ratios) >= 2:
        nums = [_num(r) for r in ratios if _num(r) is not None]
        for i in range(1, len(nums)):
            if nums[i] >= nums[i - 1]:
                _add("gear_ratios_descending", "warning",
                     f"Gear ratios not strictly descending at gear {i+1}: "
                     f"{nums[i]:.4f} >= {nums[i-1]:.4f}")
                break

    # 7. Final drive > 1.0 for RWD / MR layouts
    layout = _dig(powertrain, "layout")
    diffs  = powertrain.get("differentials") or []
    fd     = _num(diffs[0].get("final_drive")) if diffs else None
    if layout in ("FR", "MR", "RR") and fd is not None and fd <= 1.0:
        _add("final_drive_ratio", "warning",
             f"Final drive {fd:.3f} ≤ 1.0 for {layout} layout")

    # 8. EV must have battery capacity
    motors = electric.get("motors") if isinstance(electric, dict) else None
    is_ev  = bool(motors) or (
        layout in ("AWD-EV", "RWD-EV", "FWD-EV") if layout else False
    )
    bat    = _num(_dig(electric, "battery", "capacity_kwh"))
    if is_ev and bat is None:
        _add("ev_battery", "error",
             "EV drivetrain detected but no battery.capacity_kwh defined")

    return issues


# ------------------------------------------------------------------------ #
# CLI                                                                      #
# ------------------------------------------------------------------------ #

def run(inputs: list[Path] | Path, out_dir: Path,
        validate: bool = False) -> dict[str, Any]:
    """Scan one or more inputs (folders and/or .zip archives) and write
    index.json, tires.json, curves.json, errors.json, library.xlsx to out_dir.
    """
    if isinstance(inputs, Path):
        inputs = [inputs]
    out_dir.mkdir(parents=True, exist_ok=True)

    vehicles: list[dict] = []
    all_curves: list[dict] = []
    errors: list[dict] = []
    val_issues: list[dict] = []
    sources_scanned: list[str] = []
    scanned_count = 0
    tire_lib = TireLibrary()

    for inp in inputs:
        try:
            src_label = f"{inp} ({'zip' if inp.is_file() else 'folder'})"
        except OSError:
            src_label = str(inp)
        sources_scanned.append(src_label)
        try:
            for src in iter_sources(inp):
                scanned_count += 1
                doc = src.doc
                if isinstance(doc, dict) and doc.get("__error__"):
                    errors.append({"file": src.display_name,
                                   "error": f"load: {doc['__error__']}"})
                    continue
                if validate:
                    val_issues.extend(validate_svj(doc, src.display_name))
                try:
                    v = summarize_vehicle(doc, source=src.display_name)
                    vehicles.append(v)
                    car_id = f"{v['make']} {v['model']} ({v['year']})"
                    all_curves.extend(extract_curves(doc, car_id))
                    tire_lib.add_doc(doc, car_id, src.display_name)
                except Exception as e:
                    errors.append({"file": src.display_name,
                                   "error": f"summarize: {e}"})
        except Exception as e:
            errors.append({"file": str(inp), "error": f"source: {e}"})

    tires = build_tire_catalogue(vehicles)

    # Fingerprint: normalise across the full library
    fp_norms = compute_fingerprint_norms(vehicles)
    fingerprints: list[dict] = []
    for v in vehicles:
        fp = compute_fingerprint(v, fp_norms)
        fingerprints.append({
            "car":    f"{v['make']} {v['model']} ({v['year']})",
            "source": v["source"],
            **fp,
        })

    # Completeness heatmap
    heatmap = compute_completeness_heatmap(vehicles)

    (out_dir / "index.json").write_text(
        json.dumps(vehicles, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "tires.json").write_text(
        json.dumps(tires, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "curves.json").write_text(
        json.dumps(all_curves, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "fingerprint.json").write_text(
        json.dumps(fingerprints, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "heatmap.json").write_text(
        json.dumps(heatmap, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "tires.svj.json").write_text(
        json.dumps(tire_lib.to_document(sources_scanned, len(vehicles)),
                   indent=1, ensure_ascii=False), encoding="utf-8")
    if errors:
        (out_dir / "errors.json").write_text(
            json.dumps(errors, indent=2), encoding="utf-8")
    if val_issues:
        (out_dir / "validation.json").write_text(
            json.dumps(val_issues, indent=2), encoding="utf-8")

    export_xlsx(vehicles, tires, all_curves, out_dir / "library.xlsx",
                fingerprints=fingerprints, heatmap=heatmap)

    result: dict[str, Any] = {
        "inputs": sources_scanned,
        "scanned_files": scanned_count,
        "vehicles": len(vehicles),
        "unique_tires": len(tires),
        "tire_sets_seen": tire_lib.total_seen,
        "tire_sets_unique": len(tire_lib._sets),
        "curves": len(all_curves),
        "errors": len(errors),
        "out_dir": str(out_dir),
    }
    if validate:
        result["validation_issues"] = len(val_issues)
    return result


def _main_run(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", type=Path, nargs="+",
                    help="One or more inputs. Each may be a folder (scanned "
                         "recursively at any depth) or a .zip archive.")
    ap.add_argument("--out", type=Path, default=Path("./svj_report"),
                    help="Output directory (default: ./svj_report)")
    ap.add_argument("--validate", action="store_true",
                    help="Run structural validation on each file; write "
                         "validation.json to the output directory.")
    args = ap.parse_args(argv)
    for p in args.inputs:
        if not p.exists():
            print(f"error: not found: {p}", file=sys.stderr)
            return 2
    report = run(args.inputs, args.out, validate=args.validate)
    print(json.dumps(report, indent=2))
    return 0


def _main_check(argv: list[str]) -> int:
    """CLI entry point for ``python svj_analyze.py check <inputs>``."""
    ap = argparse.ArgumentParser(
        prog="svj_analyze.py check",
        description="Run physical sanity checks on SVJ files.",
    )
    ap.add_argument("inputs", type=Path, nargs="+",
                    help="One or more folders or .zip archives to scan.")
    ap.add_argument("--json", action="store_true",
                    help="Output results as JSON instead of a human-readable table.")
    args = ap.parse_args(argv)
    for p in args.inputs:
        if not p.exists():
            print(f"error: not found: {p}", file=sys.stderr)
            return 2

    all_issues: list[dict] = []
    car_results: dict[str, list[dict]] = {}

    for inp in args.inputs:
        for src in iter_sources(inp):
            if isinstance(src.doc, dict) and src.doc.get("__error__"):
                print(f"  skip (load error): {src.display_name}", file=sys.stderr)
                continue
            issues = sanity_check(src.doc, src.display_name)
            car_results[src.display_name] = issues
            all_issues.extend(issues)

    if args.json:
        print(json.dumps(all_issues, indent=2))
        return 1 if any(i["severity"] == "error" for i in all_issues) else 0

    err_count  = sum(1 for i in all_issues if i["severity"] == "error")
    warn_count = sum(1 for i in all_issues if i["severity"] == "warning")
    print(f"\n{'='*80}")
    print(f"  svj_analyze check — {len(car_results)} car(s)  |  "
          f"{err_count} error(s)  {warn_count} warning(s)")
    print(f"{'='*80}")
    for src, issues in car_results.items():
        errs  = [i for i in issues if i["severity"] == "error"]
        warns = [i for i in issues if i["severity"] == "warning"]
        status = "FAIL" if errs else "PASS"
        print(f"\n  [{status}]  {src}")
        for i in errs:
            print(f"           ERROR  [{i['check']}]  {i['message']}")
        for i in warns:
            print(f"           WARN   [{i['check']}]  {i['message']}")
        if not issues:
            print("           (no issues found)")
    print(f"\n{'='*80}\n")
    return 1 if err_count else 0


def main(argv: list[str] | None = None) -> int:
    _argv: list[str] = sys.argv[1:] if argv is None else list(argv)
    for stream in (sys.stdout, sys.stderr):  # file names may be non-ASCII (Windows cp1252)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    if _argv and _argv[0] == "check":
        return _main_check(_argv[1:])
    return _main_run(_argv)


if __name__ == "__main__":
    raise SystemExit(main())
