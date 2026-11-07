#!/usr/bin/env python3
"""Generate a GRLevelX placefile of active NIFC wildfires and available perimeters."""

import json
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
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
ICON_URL = (
    "https://raw.githubusercontent.com/mookiemoo1103/wildfires/"
    "main/assets/fire_icon.png"
)
USER_AGENT = "AguaceroWx-Active-Wildfires/2.0"
LOCAL_TZ = ZoneInfo("America/Chicago")
LOOKBACK_DAYS = 30
# GRLevelX placefile polygon vertex alpha: 255 opaque, 0 transparent.
# Alpha 89 is approximately 65% transparent.
PERIMETER_RGBA = (255, 0, 0, 89)
PERIMETER_MAX_OFFSET_DEGREES = 0.0002


def arcgis_query(layer_url, where, out_fields, *, simplify=False):
    """Fetch all matching ArcGIS features, paging if the service requires it."""
    features = []
    offset = 0

    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultRecordCount": 2000,
            "resultOffset": offset,
        }
        if simplify:
            params["geometryPrecision"] = 5
            params["maxAllowableOffset"] = PERIMETER_MAX_OFFSET_DEGREES

        url = layer_url + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if payload.get("error"):
            raise RuntimeError(f"ArcGIS returned an error: {payload['error']}")
        if "features" not in payload:
            raise RuntimeError("ArcGIS response did not contain a features array.")

        page = payload["features"]
        features.extend(page)
        if not payload.get("exceededTransferLimit") or not page:
            break
        offset += len(page)

    return features


def fetch_incidents(cutoff_ms):
    """Fetch currently active wildfire incident points discovered in 30 days."""
    where = (
        "IncidentTypeCategory = 'WF' "
        f"AND FireDiscoveryDateTime >= {cutoff_ms} "
        "AND ContainmentDateTime IS NULL "
        "AND ControlDateTime IS NULL "
        "AND FireOutDateTime IS NULL "
        "AND (PercentContained IS NULL OR PercentContained < 100)"
    )
    fields = (
        "IncidentName,FireDiscoveryDateTime,IncidentSize,PercentContained,"
        "ContainmentDateTime,ControlDateTime,FireOutDateTime,IncidentTypeCategory"
    )
    return arcgis_query(INCIDENT_LAYER, where, fields)


def fetch_perimeters():
    """Fetch current NIFC perimeter polygons; match to active fires in main()."""
    # The current perimeter layer does not expose the visibility/status fields
    # used by older WFIGS products. Retrieve its current public features, then
    # retain only polygons whose incident names match the active 30-day point feed.
    return arcgis_query(PERIMETER_LAYER, "1=1", "*", simplify=True)


def started_date(value):
    if value in (None, ""):
        return "Not reported"
    try:
        dt = datetime.fromtimestamp(int(value) / 1000, timezone.utc)
        return dt.astimezone(LOCAL_TZ).strftime("%-m/%-d/%Y")
    except (TypeError, ValueError, OverflowError):
        return "Not reported"


def acreage(value):
    if value in (None, ""):
        return "Not reported"
    try:
        return f"{float(value):,.0f} Acres"
    except (TypeError, ValueError):
        return "Not reported"


def containment(value):
    if value in (None, ""):
        return "Not reported"
    try:
        return f"{float(value):g}% Contained"
    except (TypeError, ValueError):
        return "Not reported"


def clean(value):
    return (
        str(value or "")
        .replace('"', "'")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )


def add_perimeter(lines, feature):
    """Append a filled red RGBA polygon, preserving each exterior/interior ring."""
    attrs = feature.get("attributes") or {}
    geometry = feature.get("geometry") or {}
    rings = geometry.get("rings") or []
    if not rings:
        return False

    name = clean(attrs.get("poly_IncidentName")) or "Unnamed Wildfire"
    acres = acreage(attrs.get("poly_GISAcres"))
    pct = containment(attrs.get("attr_PercentContained"))
    tooltip = (
        f"Fire Name: {name}\\n"
        f"Perimeter Acreage: {acres}\\n"
        f"Containment: {pct}\\n"
        "Source: NIFC WFIGS current fire perimeters"
    )

    # A GRLevelX Polygon supports RGBA values on each vertex. Repeating the
    # first vertex closes each ring; separate rings preserve polygon holes.
    lines.append(f"; Perimeter: {name} | {tooltip.replace(chr(10), ' | ')}")
    lines.append("Polygon:")
    red, green, blue, alpha = PERIMETER_RGBA
    for ring in rings:
        if len(ring) < 3:
            continue
        points = list(ring)
        if points[0] != points[-1]:
            points.append(points[0])
        for point in points:
            if len(point) < 2:
                continue
            lon, lat = point[0], point[1]
            lines.append(
                f"{float(lat):.5f},{float(lon):.5f},"
                f"{red},{green},{blue},{alpha}"
            )
    lines.append("End:")
    return True


def main():
    cutoff_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).timestamp()
        * 1000
    )

    # Fetch both sources before writing anything. If either service fails, the
    # previously generated placefile remains intact.
    incidents = fetch_incidents(cutoff_ms)
    perimeters = fetch_perimeters()

    lines = [
        "; Active wildfires discovered within the last 30 days",
        "; Incident status excludes fires with containment, control, or out dates.",
        "; Perimeters are official NIFC WFIGS current perimeters when available.",
        "; Red perimeter fill is approximately 65% transparent.",
        "; Source: NIFC WFIGS Current Incident Locations and Current Perimeters",
        "Title: Active Wildfires - Last 30 Days (NIFC) with Perimeters",
        "RefreshSeconds: 300",
        'Font: 1, 12, 1, "Arial"',
        f'IconFile: 1, 128, 128, 64, 64, "{ICON_URL}"',
    ]

    active_names = {
        clean((feature.get("attributes") or {}).get("IncidentName")).casefold()
        for feature in incidents
        if clean((feature.get("attributes") or {}).get("IncidentName"))
    }

    perimeter_count = 0
    for feature in perimeters:
        perimeter_attrs = feature.get("attributes") or {}
        perimeter_name = clean(
            perimeter_attrs.get("poly_IncidentName")
            or perimeter_attrs.get("attr_IncidentName")
        ).casefold()
        if not perimeter_name or perimeter_name not in active_names:
            continue
        if add_perimeter(lines, feature):
            perimeter_count += 1

    icon_count = 0
    for feature in incidents:
        attrs = feature.get("attributes") or {}
        geom = feature.get("geometry") or {}
        lat, lon = geom.get("y"), geom.get("x")

        if attrs.get("IncidentTypeCategory") != "WF" or lat is None or lon is None:
            continue
        if any(attrs.get(field) for field in (
            "ContainmentDateTime", "ControlDateTime", "FireOutDateTime"
        )):
            continue
        pct = attrs.get("PercentContained")
        if pct is not None:
            try:
                if float(pct) >= 100:
                    continue
            except (TypeError, ValueError):
                continue

        fire_name = clean(attrs.get("IncidentName")) or "Unnamed Wildfire"
        tooltip = (
            f"Fire Name: {fire_name}\\n"
            f"Started: {started_date(attrs.get('FireDiscoveryDateTime'))}\\n"
            f"Current Reported Acreage: {acreage(attrs.get('IncidentSize'))}\\n"
            f"Containment: {containment(pct)}"
        )
        lines.append(
            f'Icon: {float(lat):.5f},{float(lon):.5f},0,1,1,"{tooltip}"'
        )
        icon_count += 1

    lines.append(
        f"; Active wildfire incidents plotted: {icon_count}; "
        f"available perimeters plotted: {perimeter_count}"
    )

    # A successful empty response is valid: writing it removes fires that have
    # aged out of the 30-day window. Source errors above still preserve old data.
    temp_output = OUTPUT.with_suffix(".txt.tmp")
    temp_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp_output.replace(OUTPUT)
    print(
        f"Generated {OUTPUT}: {icon_count} active wildfire points and "
        f"{perimeter_count} available perimeters."
    )


if __name__ == "__main__":
    main()
