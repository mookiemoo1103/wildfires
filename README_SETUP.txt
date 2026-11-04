# Confirmed/reported active wildfire placefile for AguaceroWx

## Data source

This package uses **NIFC WFIGS current wildfire incident locations only**.

- Includes records classified as wildfires (`IncidentTypeCategory = WF`).
- Excludes incidents with fire-out, containment, or control timestamps.
- Excludes incidents reported as 100% contained.
- Does **not** include NASA FIRMS, MODIS, VIIRS, NOAA/GINA NGFS, or any other satellite heat detections.

NIFC WFIGS contains officially reported/current incident records. It is the appropriate source here when you want reported wildfire incidents rather than unverified satellite hotspots. An incident can still be actively managed while partially contained; those records remain included unless NIFC reports it as completed/contained/controlled.

## Upload to your `mookiemoo1103/wildfires` repository

Extract this ZIP and upload/replace these paths at the repository root:

- `generate_wildfire_placefile.py`
- `.github/workflows/update-wildfires.yml`
- `assets/fire_icon.png`

The workflow generates `active_wildfires.txt` automatically. No NASA FIRMS key or other API secret is required.

## Run and load

1. Open Actions → **Update Confirmed Active Wildfires** → Run workflow.
2. Wait for a green successful run.
3. Confirm `active_wildfires.txt` appears at repository root.
4. In AguaceroWx add this placefile URL:

`https://raw.githubusercontent.com/mookiemoo1103/wildfires/main/active_wildfires.txt`

The GitHub workflow runs every 5 minutes. AguaceroWx's placefile refresh is set to 10 seconds, but the underlying data only changes when the workflow retrieves and publishes an update.

## Stacked click/hover information

Each fire icon displays exactly these four lines:

1. Fire Name
2. Start/Detection Date
3. Current Reported Acreage
4. Containment

No status, location, source, satellite confidence, or FRP fields are included.

## Important limitation

NIFC WFIGS is an official incident-location feed, not a live sensor confirming that flames are visible at every moment. This package uses its current active wildfire incident records and removes records marked completed, contained, controlled, or 100% contained. It intentionally does not plot satellite-only detections.
