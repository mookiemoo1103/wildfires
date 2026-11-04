# Active Wildfires Placefile (AguaceroWx)

## Files
- `generate_wildfire_placefile.py` — downloads active wildfire incident and perimeter data and builds the placefile.
- `.github/workflows/update-wildfires.yml` — runs every 5 minutes and can also be started manually.
- `assets/fire_icon.png` — transparent fire icon made from the supplied image.
- `active_wildfires.txt` — generated output; GitHub Actions updates this file.

## Setup
1. Add `generate_wildfire_placefile.py` to the root of your GitHub repository.
2. Add `active_wildfires.txt` to the root (it will be created automatically on the first successful run).
3. Add `assets/fire_icon.png` to an `assets` folder.
4. Add `.github/workflows/update-wildfires.yml` under the `.github/workflows` folder.
5. Commit all files to the `main` branch.
6. Open **Actions** → **Update Active Wildfire Placefile** → **Run workflow**.
7. Wait for a green checkmark.

## Placefile URL
After the first successful workflow run, use:

`https://raw.githubusercontent.com/mookiemoo1103/earthquake/main/active_wildfires.txt`

If you use a different repository name, replace `earthquake` in the URL and in `ASSET_URL` inside the Python script.

## Data coverage and update limits
- The incident and perimeter feeds are from the US National Interagency Fire Center (NIFC) WFIGS services. This first version is **United States coverage**, not a complete North America-wide incident feed.
- The official NIFC current perimeter data is refreshed about every 5 minutes; the script cannot make source data update faster than that.
- AguaceroWx requests the generated placefile every 10 seconds. GitHub Actions is scheduled every 5 minutes, subject to GitHub scheduling delays.
- Canadian fire reporting is fragmented across provincial/territorial agencies. A national Canadian perimeter estimate feed exists, but it does not provide the same named-incident, acres, and containment attributes, so it is not mixed into this incident layer.
- Fire status and containment are agency-reported and may lag actual conditions. The script excludes incidents with a containment, control, or out date, and incidents reporting 100% containment.
- Perimeter polygons are approximate display outlines from the current NIFC perimeter service; not every active incident has a mapped perimeter.

## Attribution
Data: National Interagency Fire Center (NIFC), Wildland Fire Interagency Geospatial Services (WFIGS).
https://data-nifc.opendata.arcgis.com/
