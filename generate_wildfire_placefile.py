#!/usr/bin/env python3
"""Multi-source active wildfire placefile for AguaceroWx.

Confirmed incidents: NIFC WFIGS current wildfire records.
Satellite heat detections: NASA FIRMS VIIRS (requires FIRMS_MAP_KEY secret)
and NOAA/GINA NGFS Alaska detections. Recent satellite detections are
explicitly labeled as satellite detections, not confirmed incident records.
"""

import csv
import io
import json
import os
import pathlib
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

OUT = pathlib.Path("active_wildfires.txt")
ICON_URL = "https://raw.githubusercontent.com/mookiemoo1103/wildfires/main/assets/fire_icon.png"
USER_AGENT = "AguaceroWx-MultiSource-Wildfire-Placefile/3.0"

WFIGS = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Incident_Locations_Current/FeatureServer/0/query"
NGFS = "https://ngfs-services.gina.alaska.edu/arcgis/rest/services/NGFS_Detections_EXPERIMENTAL_Polygons/FeatureServer/1/query"
FIRMS_API = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


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


def fetch_ngfs():
    # This public GINA/NOAA NGFS layer currently covers Alaska only.
    result = get_json(NGFS, {
        "where": "1=1",
        "outFields": "pixel_date_time_utc,known_incident_name,known_incident_type,confidence,frp,satellite,state,county,latitude,longitude",
        "returnGeometry": "true", "outSR": "4326", "f": "json",
        "resultRecordCount": 10000, "orderByFields": "pixel_date_time_utc DESC"
    })
    now = datetime.now(timezone.utc)
    items = []
    for f in result.get("features", []):
        a, g = f.get("attributes") or {}, f.get("geometry") or {}
        lat, lon = g.get("y", a.get("latitude")), g.get("x", a.get("longitude"))
        if lat is None or lon is None:
            continue
        stamp = a.get("pixel_date_time_utc") or ""
        try:
            dt = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = (now - dt.astimezone(timezone.utc)).total_seconds() / 60
            if age < -5 or age > 90:
                continue
        except (ValueError, TypeError):
            continue
        # Keep detections with nominal/high confidence only when field is present.
        conf = str(a.get("confidence") or "").lower()
        if conf and conf not in ("nominal", "high", "n", "h"):
            continue
        name = a.get("known_incident_name") or "Unmatched NGFS heat detection"
        items.append({
            "lat": float(lat), "lon": float(lon), "name": clean(name),
            "kind": "RECENT SATELLITE HEAT DETECTION - NOT INCIDENT VERIFIED",
            "started": dt.strftime("%Y-%m-%d %H:%M UTC"),
            "acres": "Not reported", "containment": "Not reported",
            "location": clean(", ".join(str(x) for x in (a.get("county"), a.get("state")) if x)),
            "source": "NOAA/GINA NGFS (Alaska layer)",
            "key": f"ngfs:{a.get('ogc_fid', '')}:{stamp}",
        })
    return items


def fetch_firms():
    key = os.environ.get("FIRMS_MAP_KEY", "").strip()
    if not key:
        print("FIRMS_MAP_KEY not set; skipping NASA FIRMS. Add it as a GitHub Actions secret.")
        return []
    # NASA's VIIRS 375m NRT feed; last 1 day requested, then strictly filtered
    # to detections no older than 90 minutes for a near-current view.
    url = f"{FIRMS_API}/{urllib.parse.quote(key)}/VIIRS_SNPP_NRT/-180,-90,180,90/1"
    try:
        rows = list(csv.DictReader(io.StringIO(get_text(url))))
    except Exception as exc:
        print(f"NASA FIRMS fetch failed: {exc}")
        return []
    now = datetime.now(timezone.utc)
    items = []
    for a in rows:
        try:
            dt = datetime.strptime(
                f"{a.get('acq_date')} {a.get('acq_time', '0000')}",
                "%Y-%m-%d %H%M"
            ).replace(tzinfo=timezone.utc)
            age = (now - dt).total_seconds() / 60
            lat, lon = float(a["latitude"]), float(a["longitude"])
            if age < -5 or age > 90:
                continue
            confidence = str(a.get("confidence", "")).lower()
            if confidence in ("low", "l"):
                continue
        except (ValueError, KeyError, TypeError):
            continue
        frp = a.get("frp") or "Not reported"
        items.append({
            "lat": lat, "lon": lon,
            "name": "NASA VIIRS active-fire detection",
            "kind": "RECENT SATELLITE HEAT DETECTION - NOT INCIDENT VERIFIED",
            "started": dt.strftime("%Y-%m-%d %H:%M UTC"),
            "acres": "Not reported", "containment": "Not reported",
            "location": clean(a.get("county") or a.get("state") or a.get("country")),
            "source": "NASA FIRMS VIIRS 375m",
            "key": f"firms:{a.get('latitude')}:{a.get('longitude')}:{a.get('acq_date')}:{a.get('acq_time')}",
            "frp": clean(frp),
        })
    return items


def near_existing(item, incidents, radius_km=8):
    # Equirectangular approximation is sufficient for duplicate matching.
    import math
    for x in incidents:
        dx = (item["lon"] - x["lon"]) * 111.32 * math.cos(math.radians(item["lat"]))
        dy = (item["lat"] - x["lat"]) * 111.32
        if math.hypot(dx, dy) <= radius_km:
            return True
    return False


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
    incidents = []
    for label, fn in (("NIFC", fetch_nifc), ("NGFS", fetch_ngfs), ("NASA FIRMS", fetch_firms)):
        try:
            got = fn()
            print(f"{label}: {len(got)} current records")
            if label == "NIFC":
                incidents.extend(got)
            else:
                # Avoid cluttering incident locations with duplicate satellite pixels.
                incidents.extend(x for x in got if not near_existing(x, incidents))
        except Exception as exc:
            print(f"{label} source unavailable: {exc}")

    lines = [
        "; Multi-source current wildfire and recent satellite detection placefile",
        "Title: Active Wildfires - Multi-Source",
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
        "; NIFC = active reported wildfire incidents.",
        "; Satellite detections are recent thermal anomalies, not confirmed fires.",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} with {len(incidents)} features.")


if __name__ == "__main__":
    main()
