#!/usr/bin/env python3
"""Generate an active-wildfire placefile from the official NIFC WFIGS feeds.

Coverage: United States. NIFC publishes current incident locations and
current fire perimeters. Source data is generally refreshed about every
five minutes; the client refresh interval cannot make the source fresher.
"""

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

OUTPUT = "active_wildfires.txt"
USER_AGENT = "AguaceroWx-Active-Wildfires/1.0"
ASSET_URL = (
    "https://raw.githubusercontent.com/mookiemoo1103/earthquake/"
    "main/assets/fire_icon.png"
)
LOCAL_TZ = ZoneInfo("America/Chicago")


def fetch_arcgis(url, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if "error" in payload:
        raise RuntimeError(f"ArcGIS service error: {payload['error']}")
    return payload.get("features", [])


def local_date(value):
    if not value:
        return "Not reported"
    try:
        dt = datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        return dt.astimezone(LOCAL_TZ).strftime("%b %d, %Y")
    except (TypeError, ValueError, OverflowError):
        return "Not reported"


def safe_number(value, decimals=0):
    if value is None:
        return "Not reported"
    try:
        number = float(value)
        if decimals == 0:
            return f"{number:,.0f}"
        return f"{number:,.{decimals}f}"
    except (TypeError, ValueError):
        return "Not reported"


def clean_tooltip(value):
    return str(value).replace('"', "'").replace("\r", " ").replace("\n", " ")


def active_incidents():
    # Wildfire category only; exclude prescribed fires and complexes.
    # Also exclude records declared contained, controlled, or out, and
    # records reporting 100% containment.
    where = (
        "IncidentTypeCategory = 'WF' "
        "AND (ContainmentDateTime IS NULL) "
        "AND (ControlDateTime IS NULL) "
        "AND (FireOutDateTime IS NULL) "
        "AND (PercentContained IS NULL OR PercentContained < 100)"
    )
    fields = (
        "IncidentName,FireDiscoveryDateTime,IncidentSize,"
        "PercentContained,ContainmentDateTime,ControlDateTime,"
        "FireOutDateTime,IncidentTypeCategory,POOState,POOCounty,"
        "IrwinID"
    )
    features = fetch_arcgis(INCIDENT_LAYER, {
        "where": where,
        "outFields": fields,
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": 2000,
    })

    results = []
    for feature in features:
        attrs = feature.get("attributes") or {}
        geom = feature.get("geometry") or {}
        x, y = geom.get("x"), geom.get("y")
        if x is None or y is None:
            continue

        # A final guard against non-wildfire or closed records.
        if attrs.get("IncidentTypeCategory") != "WF":
            continue
        if attrs.get("ContainmentDateTime") or attrs.get("ControlDateTime") or attrs.get("FireOutDateTime"):
            continue
        contained = attrs.get("PercentContained")
        if contained is not None and float(contained) >= 100:
            continue

        name = attrs.get("IncidentName") or "Unnamed Wildfire"
        county = attrs.get("POOCounty") or ""
        state = attrs.get("POOState") or ""
        location = ", ".join(part for part in (county, state) if part) or "United States"

        results.append({
            "name": name,
            "lat": float(y),
            "lon": float(x),
            "date": local_date(attrs.get("FireDiscoveryDateTime")),
            "acres": safe_number(attrs.get("IncidentSize")),
            "containment": (
                f"{safe_number(contained, 1)}%"
                if contained is not None else "Not reported"
            ),
            "location": location,
            "irwin": attrs.get("IrwinID"),
        })
    return results


def active_perimeters():
    # NIFC's current perimeter service includes the best available mapped
    # perimeter geometry. Exclude declared contained/controlled/out fires.
    where = (
        "(attr_ContainmentDateTime IS NULL) "
        "AND (attr_ControlDateTime IS NULL) "
        "AND (attr_FireOutDateTime IS NULL) "
        "AND (attr_IncidentTypeCategory = 'WF' OR attr_IncidentTypeCategory IS NULL)"
    )
    fields = (
        "poly_IncidentName,poly_GISAcres,attr_PercentContained,"
        "attr_FireDiscoveryDateTime,attr_ContainmentDateTime,"
        "attr_ControlDateTime,attr_FireOutDateTime,"
        "attr_IncidentTypeCategory,poly_IRWINID"
    )
    features = fetch_arcgis(PERIMETER_LAYER, {
        "where": where,
        "outFields": fields,
        "returnGeometry": "true",
        "outSR": "4326",
        "geometryPrecision": "4",
        "f": "json",
        "resultRecordCount": 1000,
    })
    return features


def main():
    incidents = active_incidents()
    perimeters = active_perimeters()

    lines = [
        "; ACTIVE WILDFIRES - NIFC / WFIGS",
        "; United States coverage. NIFC source data refreshes approximately every 5 minutes.",
        "Title: Active Wildfires - United States",
        "RefreshSeconds: 10",
        'Font: 1, 12, 1, "Arial"',
        f'IconFile: 1, 64, 64, 32, 32, "{ASSET_URL}"',
    ]

    # Draw current fire perimeters first so point icons remain visible above them.
    for feature in perimeters:
        attrs = feature.get("attributes") or {}
        geom = feature.get("geometry") or {}
        rings = geom.get("rings") or []
        if not rings:
            continue

        # Avoid enormous placefile objects: simplify by taking at most ~250
        # evenly spaced vertices per ring. The upstream perimeter remains
        # the authoritative geometry; this is a display approximation.
        for ring in rings:
            if len(ring) < 4:
                continue
            stride = max(1, len(ring) // 250)
            points = ring[::stride]
            if points[-1] != ring[-1]:
                points.append(ring[-1])
            if len(points) < 4:
                continue

            lines.append("Object: 0,0")
            lines.append("  Polygon: 255,90,0,2,255,90,0,35")
            for lon, lat in points:
                lines.append(f"    {float(lat):.4f},{float(lon):.4f}")
            lines.append("End:")

    # Plot active fire incident icons and click details.
    for fire in incidents:
        tooltip = clean_tooltip(
            f"Fire: {fire['name']}\\n"
            f"Started: {fire['date']}\\n"
            f"Acres burned: {fire['acres']}\\n"
            f"Containment: {fire['containment']}"
        )
        lines.extend([
            f"Object: {fire['lat']:.5f},{fire['lon']:.5f}",
            f'  Icon: 0,0,000,1,1,"{tooltip}"',
            "End:",
        ])

    lines.append(f"; Active wildfire incidents plotted: {len(incidents)}")
    lines.append(f"; Active perimeter features plotted: {len(perimeters)}")
    lines.append(
        "; Source: National Interagency Fire Center (NIFC) WFIGS. "
        "Incident reports can lag field conditions."
    )

    pathlib.Path(OUTPUT).write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
    print(
        f"Generated {OUTPUT}: {len(incidents)} active incidents, "
        f"{len(perimeters)} perimeter features."
    )


if __name__ == "__main__":
    main()
