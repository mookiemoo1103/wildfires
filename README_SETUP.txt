# Active Wildfires Placefile for AguaceroWx

## Files in this package
- `generate_wildfire_placefile.py` — fetches current NIFC wildfire incidents and optional perimeter outlines.
- `.github/workflows/update-wildfires.yml` — runs the generator every five minutes and supports manual runs.
- `assets/fire_icon.png` — your supplied transparent flame image.
- `active_wildfires.txt` — generated automatically by the workflow.

## Install into the separate `wildfires` repository
Upload/replace these files in the **root of mookiemoo1103/wildfires** while preserving folders:

1. `generate_wildfire_placefile.py` at the repository root.
2. `assets/fire_icon.png` inside the `assets` folder.
3. `.github/workflows/update-wildfires.yml` inside `.github/workflows`.
4. `README_SETUP.txt` at the root (optional documentation).

Do not upload the ZIP itself as the placefile. Extract it first and upload the files/folders.

## Run it
1. Open the repository's **Actions** tab.
2. Select **Update Active Wildfire Placefile**.
3. Click **Run workflow**.
4. Wait for a green checkmark. The workflow creates or updates `active_wildfires.txt`.

## AguaceroWx placefile URL
Add this exact URL as the placefile:

`https://raw.githubusercontent.com/mookiemoo1103/wildfires/main/active_wildfires.txt`

The flame icon is referenced from:

`https://raw.githubusercontent.com/mookiemoo1103/wildfires/main/assets/fire_icon.png`

## Coverage and refresh limitations
- This package uses the US National Interagency Fire Center (NIFC) WFIGS current incident feed. It is **United States coverage**, not complete North America coverage.
- GitHub Actions is scheduled every five minutes; GitHub may delay scheduled runs.
- AguaceroWx is instructed to refresh the text file every 10 seconds, but the source data and generated file only change when the workflow successfully runs.
- Perimeter outlines are optional. If the perimeter service fails, the script still generates incident markers.
- The generator excludes records marked contained, controlled, out, or 100% contained. Agency data can lag real-world conditions.
- Perimeter outlines are simplified for map performance and are approximate display geometry.
- Acres and containment are displayed when reported by the source.

## Data attribution
National Interagency Fire Center (NIFC), Wildland Fire Interagency Geospatial Services (WFIGS):
https://data-nifc.opendata.arcgis.com/
