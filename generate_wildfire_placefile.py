#!/usr/bin/env python3
"""Generate a confirmed/reported active wildfire placefile from NIFC WFIGS."""

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
OUTPUT = pathlib.Path("active_wildfires.txt")
ICON_URL = (
    "https://raw.githubusercontent.com/mookiemoo1103/wildfires/"
    "main/assets/fire_icon.png"
)
USER_AGENT = "AguaceroWx-Confirmed-Wildfires/1.0"
LOCAL_TZ = ZoneInfo("America/Chicago")


def fetch_incidents():
    """Fetch current wildfire incident points; fail loudly on source errors."""
    params = {
        "where": (
            "IncidentTypeCategory = 'WF' "
            "AND ContainmentDateTime IS NULL "
            "AND ControlDateTime IS NULL "
            "AND FireOutDateTime IS NULL "
            "AND (PercentContained IS NULL OR PercentContained < 100)"
        ),
        "outFields": (
            "IncidentName,FireDiscoveryDateTime,IncidentSize,"
            "PercentContained,ContainmentDateTime,ControlDateTime,"
            "FireOutDateTime,IncidentTypeCategory"
        ),
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
        "resultRecordCount": 2000,
    }
    url = INCIDENT_LAYER + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if payload.get("error"):
        raise RuntimeError(f"NIFC WFIGS returned an error: {payload['error']}")
    if "features" not in payload:
        raise RuntimeError("NIFC WFIGS response did not contain incident features.")
    return payload["features"]


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
    return str(value or "").replace('"', "'").replace("\r", " ").replace("\n", " ").strip()


def main():
    features = fetch_incidents()
    icons = []

    for feature in features:
        attrs = feature.get("attributes") or {}
        geom = feature.get("geometry") or {}
        lat, lon = geom.get("y"), geom.get("x")

        # Keep only reported wildfire incidents with a usable point location.
        if attrs.get("IncidentTypeCategory") != "WF" or lat is None or lon is None:
            continue
        if any(attrs.get(field) for field in (
            "ContainmentDateTime", "ControlDateTime", "FireOutDateTime"
        )):
            continue
        pct = attrs.get("PercentContained")
        if pct is not None and float(pct) >= 100:
            continue

        fire_name = clean(attrs.get("IncidentName")) or "Unnamed Wildfire"
        tooltip = (
            f"Fire Name: {fire_name}\\n"
            f"Started: {started_date(attrs.get('FireDiscoveryDateTime'))}\\n"
            f"Current Reported Acreage: {acreage(attrs.get('IncidentSize'))}\\n"
            f"Containment: {containment(pct)}"
        )
        icons.append(
            f'Icon: {float(lat):.5f},{float(lon):.5f},0,1,1,"{tooltip}"'
        )

    # Do not replace a working placefile with an empty file if the feed unexpectedly
    # returns no records. A genuinely empty season can be reviewed manually.
    if not icons:
        raise RuntimeError(
            "NIFC returned no qualifying wildfire points; existing placefile was preserved."
        )

    lines = [
        "; Confirmed/reported active wildfire incidents from NIFC WFIGS only",
        "; Point icons only. No satellite detections and no fire perimeter polygons.",
        "; Source: NIFC WFIGS Current Incident Locations",
        "Title: Confirmed Active Wildfires - NIFC",
        "RefreshSeconds: 300",
        'Font: 1, 12, 1, "Arial"',
        f'IconFile: 1, 128, 128, 64, 64, "{ICON_URL}"',
        *icons,
        f"; Active reported wildfire incidents plotted: {len(icons)}",
    ]

    temp_output = OUTPUT.with_suffix(".txt.tmp")
    temp_output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp_output.replace(OUTPUT)
    print(f"Generated {OUTPUT}: {len(icons)} reported active wildfire points.")


if __name__ == "__main__":
    main()
