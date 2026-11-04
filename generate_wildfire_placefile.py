#!/usr/bin/env python3
"""Build an AguaceroWx placefile of active US wildfires from NIFC WFIGS."""

import json
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

INCIDENT_LAYER = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Incident_Locations_Current/FeatureServer/0/query"
)
PERIMETER_LAYER = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query"
)
OUTPUT = pathlib.Path("active_wildfires.txt")
ASSET_URL = (
    "https://raw.githubusercontent.com/mookiemoo1103/wildfires/"
    "main/assets/fire_icon.png"
)
LOCAL_TZ = ZoneInfo("America/Chicago")
USER_AGENT = "AguaceroWx-Wildfire-Placefile/1.1"
MAX_PERIMETERS = 100
MAX_VERTICES_PER_RING = 100


def arcgis_query(url, params, timeout=60):
    request_url = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        request_url, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(payload["error"])
    return payload.get("features", [])


def format_date(value):
    if not value:
        return "Not reported"
    try:
        stamp = datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        return stamp.astimezone(LOCAL_TZ).strftime("%b %d, %Y")
    except (TypeError, ValueError, OverflowError):
        return "Not reported"


def format_acres(value):
    if value is None:
        return "Not reported"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "Not reported"


def active_incidents():
    # Only wildfire incidents; exclude closed records and fully contained fires.
    where = (
        "IncidentTypeCategory = 'WF' "
        "AND ContainmentDateTime IS NULL "
        "AND ControlDateTime IS NULL "
        "AND FireOutDateTime IS NULL "
        "AND (PercentContained IS NULL OR PercentContained < 100)"
    )
    fields = (
        "IncidentName,FireDiscoveryDateTime,IncidentSize,PercentContained,"
        "ContainmentDateTime,ControlDateTime,FireOutDateTime,"
        "IncidentTypeCategory,POOState,POOCounty"
    )
    features = arcgis_query(INCIDENT_LAYER, {
        "where": where,
        "outFields": fields,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": 2000,
    })
    fires = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        point = feature.get("geometry") or {}
        if point.get("x") is None or point.get("y") is None:
            continue
        if attrs.get("IncidentTypeCategory") != "WF":
            continue
        if any(attrs.get(k) for k in (
            "ContainmentDateTime", "ControlDateTime", "FireOutDateTime"
        )):
            continue
        contained = attrs.get("PercentContained")
        if contained is not None:
            try:
                if float(contained) >= 100:
                    continue
            except (TypeError, ValueError):
                pass
        county = attrs.get("POOCounty") or ""
        state = attrs.get("POOState") or ""
        location = ", ".join(x for x in (county, state) if x) or "United States"
        fires.append({
            "name": attrs.get("IncidentName") or "Unnamed Wildfire",
            "lat": float(point["y"]),
            "lon": float(point["x"]),
            "date": format_date(attrs.get("FireDiscoveryDateTime")),
            "acres": format_acres(attrs.get("IncidentSize")),
            "containment": (
                f"{float(contained):.1f}%" if contained is not None
                else "Not reported"
            ),
            "location": location,
        })
    return fires


def active_perimeters():
    """Best-effort optional perimeter layer; incidents still publish if it fails."""
    where = (
        "attr_ContainmentDateTime IS NULL "
        "AND attr_ControlDateTime IS NULL "
        "AND attr_FireOutDateTime IS NULL"
    )
    fields = (
        "poly_IncidentName,poly_GISAcres,attr_PercentContained,"
        "attr_ContainmentDateTime,attr_ControlDateTime,attr_FireOutDateTime"
    )
    try:
        return arcgis_query(PERIMETER_LAYER, {
            "where": where,
            "outFields": fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "geometryPrecision": "3",
            "f": "json",
            "resultRecordCount": MAX_PERIMETERS,
        }, timeout=45)[:MAX_PERIMETERS]
    except Exception as exc:
        print(f"Perimeter layer unavailable; continuing with fire points only: {exc}")
        return []


def main():
    fires = active_incidents()
    perimeters = active_perimeters()

    lines = [
        "; Active US wildfires - NIFC WFIGS",
        "; Agency-reported status; verify critical information with officials.",
        "Title: Active Wildfires - United States",
        "RefreshSeconds: 10",
        'Font: 1, 12, 1, "Arial"',
        f'IconFile: 1, 64, 64, 32, 32, "{ASSET_URL}"',
    ]

    # Draw a limited number of simplified perimeters behind incident markers.
    for feature in perimeters:
        geom = feature.get("geometry") or {}
        for ring in (geom.get("rings") or [])[:1]:
            if len(ring) < 4:
                continue
            stride = max(1, (len(ring) - 1) // MAX_VERTICES_PER_RING)
            points = ring[::stride]
            if points[-1] != ring[-1]:
                points.append(ring[-1])
            lines.append("Object: 0,0")
            lines.append("  Polygon: 255,90,0,2,255,90,0,25")
            for lon, lat in points:
                lines.append(f"    {float(lat):.4f},{float(lon):.4f}")
            lines.append("End:")

    for fire in fires:
        # Tooltip fields are kept concise for compatibility with placefile parsers.
        info = (
            f"{fire['name']} | {fire['location']} | "
            f"Started: {fire['date']} | Acres: {fire['acres']} | "
            f"Containment: {fire['containment']}"
        ).replace('"', "'")
        lines.extend([
            f"Object: {fire['lat']:.5f},{fire['lon']:.5f}",
            f'  Icon: 0,0,000,1,1,"{info}"',
            "End:",
        ])

    lines.extend([
        f"; Active wildfire incidents plotted: {len(fires)}",
        f"; Perimeter features plotted: {len(perimeters)}",
        "; Data: NIFC WFIGS. US coverage only.",
    ])
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}: {len(fires)} incidents, {len(perimeters)} perimeters")


if __name__ == "__main__":
    main()
