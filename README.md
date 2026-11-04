# Confirmed Active Wildfires — AguaceroWx Placefile

This repository generates a point-only placefile of **reported active wildfires** from the National Interagency Fire Center (NIFC) WFIGS Current Incident Locations feed.

## Placefile URL

`https://raw.githubusercontent.com/mookiemoo1103/wildfires/main/active_wildfires.txt`

Add that URL as a placefile in AguaceroWx.

## Display rules

- Reported wildfire incidents only (`IncidentTypeCategory = WF`).
- Excludes incidents marked contained, controlled, or out, and incidents reporting 100% containment.
- Uses incident location points only.
- Does **not** include satellite heat detections or fire perimeter polygons.
- Click information is limited to:
  1. Fire Name
  2. Started
  3. Current Reported Acreage
  4. Containment

## Refresh schedule

GitHub Actions runs the generator every 5 minutes. The generated placefile also specifies `RefreshSeconds: 300`. The client refresh interval does not make the upstream NIFC feed update faster.

## Required flame icon

The generator references this repository asset:

`assets/fire_icon.png`

Make sure the flame PNG is uploaded to that exact path in the `main` branch. If the asset is missing, the placefile data can still generate, but AguaceroWx cannot load the custom flame icon.

## Files

- `generate_wildfire_placefile.py` — fetches NIFC incidents and creates the placefile.
- `active_wildfires.txt` — generated placefile; updated by GitHub Actions.
- `.github/workflows/update-wildfires.yml` — scheduled automation.

## Manual run

From the repository root:

```bash
python3 generate_wildfire_placefile.py
```

The script preserves the existing placefile if the NIFC request fails or returns no qualifying incidents, rather than overwriting it with an empty output.
