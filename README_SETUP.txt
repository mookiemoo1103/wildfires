# Multi-source active wildfire placefile for AguaceroWx

## Sources and what is plotted

1. **NIFC WFIGS current incidents** — confirmed/reported wildfire incidents only (`IncidentTypeCategory = WF`), excluding records with containment, control, fire-out timestamps, or 100% containment.
2. **NASA FIRMS VIIRS 375 m** — optional near-real-time satellite thermal detections from the latest 90 minutes. These are marked as satellite detections, not verified incidents. NASA FIRMS requires a free MAP_KEY.
3. **NOAA/GINA NGFS** — optional public recent VIIRS detections from the available 12-hour layer, filtered to 90 minutes and nominal/high confidence. The specific public service currently queried is Alaska-only.

**Important:** A satellite heat detection is not proof of an active wildfire; it can include other heat sources, and clouds can hide fires. Satellite-only points are explicitly labeled as unverified heat detections. The script does not claim that these are confirmed fires.

FIRIS is not included as a live nationwide source because its aircraft-derived operational perimeter feeds are regional and do not provide a dependable public nationwide API endpoint for this workflow.

## Upload to your separate `mookiemoo1103/wildfires` repository

Extract this ZIP and upload/replace these paths at the repository root:

- `generate_wildfire_placefile.py`
- `.github/workflows/update-wildfires.yml`
- `assets/fire_icon.png`

The workflow generates `active_wildfires.txt` automatically.

## Enable NASA FIRMS

1. Create a free NASA FIRMS MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/area/
2. In GitHub, open `mookiemoo1103/wildfires` → Settings → Secrets and variables → Actions.
3. Click **New repository secret**.
4. Name: `FIRMS_MAP_KEY`
5. Value: paste your NASA FIRMS MAP_KEY.
6. Save.

Without this secret, NIFC and the public NGFS Alaska layer still run; NASA FIRMS is skipped.

## Run and load

1. Open Actions → **Update Multi-Source Active Wildfires** → Run workflow.
2. Wait for a green successful run.
3. Confirm `active_wildfires.txt` appears at repository root.
4. In AguaceroWx add this live placefile URL:

`https://raw.githubusercontent.com/mookiemoo1103/wildfires/main/active_wildfires.txt`

Suggested AguaceroWx refresh interval: 1 minute. The GitHub workflow runs every 5 minutes, and source updates can be slower.

## Stacked click/hover information

Each icon's hover text is authored with separate lines for:
- Fire Name
- Status (confirmed incident or satellite-only detection)
- Start/detection time
- Current reported acres
- Reported containment
- Location
- Source

For satellite detections, acreage and containment are shown as "Not reported" rather than invented.

## Limits

- NIFC WFIGS is United States incident coverage and updates on its own source schedule.
- NASA FIRMS is near-real-time satellite data; it is not a dispatch feed or a guarantee of current burning.
- The NGFS endpoint in this package is an Alaska-only public layer, not a nationwide feed.
- GitHub Actions may delay scheduled runs.
- This package intentionally starts with point markers only to keep AguaceroWx parsing lightweight.
