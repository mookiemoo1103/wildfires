#!/usr/bin/env python3
"""Confirmed/reported active wildfire incident placefile for AguaceroWx.

Uses only current NIFC WFIGS wildfire incident records. Satellite detections
are intentionally excluded because they are not confirmed incidents.
"""

import json
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timezone

OUT = pathlib.Path("active_wildfires.txt")
ICON_URL = "https://raw.githubusercontent.com/mookiemoo1103/wildfires/main/assets/fire_icon.png"
USER_AGENT = "AguaceroWx-Confirmed-Wildfire-Placefile/4.0"

WFIGS = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Incident_Locations_Current/FeatureServer/0/query"


def get_json(url, params, timeout=60):
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    return data


def get_text(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def utc_ms_to_text(value):
    if not value:
        return "Not reported"
    try:
        dt = datetime.fromtimestamp(float(value) / 1000, timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OverflowError):
        return "Not reported"


def clean(value):
    return str(value if value not in (None, "") else "Not reported").replace('"', "'").replace("\r", " ").replace("\n", " ")


def fetch_nifc():
    # Explicitly exclude prescribed burns and incident complexes.
    where = (
        "IncidentTypeCategory = 'WF' "
        "AND FireOutDateTime IS NULL "
        "AND ContainmentDateTime IS NULL "
        "AND ControlDateTime IS NULL "
        "AND (PercentContained IS NULL OR PercentContained < 100)"
    )
    fields = (
        "IncidentName,FireDiscoveryDateTime,IncidentSize,PercentContained,"
        "FireOutDateTime,ContainmentDateTime,ControlDateTime,"
        "IncidentTypeCategory,POOCity,POOCounty,POOState,IrwinID"
    )
    result = get_json(WFIGS, {
        "where": where, "outFields": fields, "returnGeometry": "true",
        "outSR": "4326", "f": "json", "resultRecordCount": 2000
    })
    items = []
    for f in result.get("features", []):
        a, g = f.get("attributes") or {}, f.get("geometry") or {}
        if g.get("x") is None or g.get("y") is None:
            continue
        if a.get("IncidentTypeCategory") != "WF":
            continue
        if any(a.get(k) for k in ("FireOutDateTime", "ContainmentDateTime", "ControlDateTime")):
            continue
        try:
            pct = float(a["PercentContained"]) if a.get("PercentContained") is not None else None
            if pct is not None and pct >= 100:
                continue
        except (ValueError, TypeError):
            pct = None
        acres = a.get("IncidentSize")
        try:
            acres = f"{float(acres):,.0f}" if acres is not None else "Not reported"
        except (ValueError, TypeError):
            acres = "Not reported"
        place = ", ".join(str(x) for x in (a.get("POOCity"), a.get("POOCounty"), a.get("POOState")) if x)
        items.append({
            "lat": float(g["y"]), "lon": float(g["x"]),
            "name": clean(a.get("IncidentName") or "Unnamed Wildfire"),
            "kind": "CONFIRMED ACTIVE INCIDENT",
            "started": utc_ms_to_text(a.get("FireDiscoveryDateTime")),
            "acres": acres,
            "containment": f"{pct:g}%" if pct is not None else "Not reported",
            "location": clean(place),
            "source": "NIFC WFIGS",
            "key": str(a.get("IrwinID") or a.get("IncidentName") or "").lower(),
        })
    return items


def hover(f):
    # Literal escaped newlines keep each attribute on its own line in placefile hover.
    parts = [
        f"Fire Name: {f['name']}",
        f"Start/Detection Date: {f['started']}",
        f"Current Reported Acreage: {f['acres']}",
        f"Containment: {f['containment']}",
    ]
    return r"\n".join(clean(x) for x in parts)


def main():
    try:
        incidents = fetch_nifc()
        print(f"NIFC WFIGS: {len(incidents)} current wildfire incidents")
    except Exception as exc:
        print(f"NIFC WFIGS source unavailable: {exc}")
        incidents = []

    lines = [
        "; Confirmed/reported active wildfire incidents from NIFC WFIGS only",
        "Title: Confirmed Active Wildfires - NIFC",
        "RefreshSeconds: 10",
        'Font: 1, 12, 1, "Arial"',
        f'IconFile: 1, 128, 128, 64, 64, "{ICON_URL}"',
    ]
    for fire in incidents:
        lines.append(
            f'Icon: {fire["lat"]:.5f},{fire["lon"]:.5f},0,1,1,"{hover(fire)}"'
        )
    lines += [
        f"; Plotted features: {len(incidents)}",
        "; Source: NIFC WFIGS current incident locations.",
        "; Satellite heat detections are not included.",
    ]
    OUT.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(incidents)} features.")


if __name__ == "__main__":
    main()
