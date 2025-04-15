# -*- coding: utf-8 -*-
"""
Geospatial Analysis of Air Quality and Urban Factors — stable v1.0
=================================================================
Key fixes vs previous draft
---------------------------
* **Always** adds `tri_facilities` column (defaults to 0) so `fillna` call cannot
  raise `AttributeError`.
* Confirmed popup formatting uses pre‑formatted strings—no inline `if`.
* Keeps running even when OpenAQ returns 410; PM2.5 shown as "N/A".
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

import pandas as pd
import geopandas as gpd
import requests
import folium
from folium.plugins import HeatMap

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

YEARS = [2024]
RADIUS_KM = 25  # km

CITIES: List[tuple[str, float, float]] = [
    ("New York", 40.7128, -74.0060),
    ("Los Angeles", 34.0522, -118.2437),
    ("Chicago", 41.8781, -87.6298),
    ("Houston", 29.7604, -95.3698),
    ("Phoenix", 33.4484, -112.0740),
    ("Philadelphia", 39.9526, -75.1652),
    ("Tampa", 27.9506, -82.4572),
]

# ----------------------------- helper functions -----------------------------

def _standardise_carbon_monitor(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    emi_col = next((c for c in df.columns if c.lower().startswith("emission") or c.lower() in {"value", "co2"}), None)
    df = df.rename(columns={emi_col: "emissions"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date"], inplace=True)
    df["year"] = df["date"].dt.year
    return df[["city", "date", "emissions", "year"]]


def get_pm25_latest(lat: float, lon: float, api_key: str | None) -> float:
    params = {
        "coordinates": f"{lat},{lon}",
        "radius": RADIUS_KM * 1000,
        "parameter": "pm25",
        "limit": 100,
    }
    if api_key:
        params["api_key"] = api_key
    try:
        r = requests.get("https://api.openaq.org/v2/latest", params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        values = [m["value"] for loc in data.get("results", []) for m in loc.get("measurements", [])]
        return float("nan") if not values else sum(values) / len(values)
    except Exception:
        return float("nan")


def _read_tri(path: Path):
    try:
        df = pd.read_csv(path, low_memory=False)
        lat = next((c for c in df.columns if c.upper().startswith("LAT")), None)
        lon = next((c for c in df.columns if c.upper().startswith("LON")), None)
        if not lat or not lon:
            return None
        df = df.dropna(subset=[lat, lon])
        return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat], crs="EPSG:4326"))
    except Exception:
        return None

# ---------------------------------- main ------------------------------------

def main():
    api_key = os.getenv("OPENAQ_KEY")

    # Carbon Monitor
    cm_path = DATA_DIR / "carbon_monitor_cities.csv"
    cm_df = _standardise_carbon_monitor(cm_path) if cm_path.exists() else pd.DataFrame(columns=["city", "date", "emissions", "year"])

    # optional PM2.5 fallback
    fb_path = DATA_DIR / "pm25_fallback.csv"
    pm_fb = pd.read_csv(fb_path) if fb_path.exists() else None

    rows = []
    for city, lat, lon in CITIES:
        pm25 = get_pm25_latest(lat, lon, api_key)
        if pd.isna(pm25) and pm_fb is not None:
            row = pm_fb.loc[pm_fb.city == city]
            if not row.empty:
                pm25 = row.iloc[0].pm25
        co2_rows = cm_df[(cm_df.city == city) & (cm_df.year == YEARS[0])]
        co2 = co2_rows.emissions.mean() if not co2_rows.empty else float("nan")
        rows.append(dict(city=city, latitude=lat, longitude=lon, pm25=pm25, co2=co2))

    metrics = pd.DataFrame(rows)
    metrics["tri_facilities"] = 0  # ensure column exists

    # TRI facilities
    tri_path = DATA_DIR / "tri_2023_us.csv"
    place_zip = DATA_DIR / "tl_2024_us_place.zip"
    if tri_path.exists() and place_zip.exists():
        tri_gdf = _read_tri(tri_path)
        if tri_gdf is not None:
            place_gdf = gpd.read_file(f"zip://{place_zip}")
            subset = place_gdf[place_gdf.NAME.isin(metrics.city)]
            tri_in = gpd.sjoin(tri_gdf, subset[["NAME", "geometry"]], how="inner", predicate="within")
            counts = tri_in.groupby("NAME").size().rename("tri_facilities").reset_index()
            metrics = metrics.merge(counts, left_on="city", right_on="NAME", how="left").drop(columns="NAME")
            metrics["tri_facilities"].fillna(0, inplace=True)

    # save outputs
    OUTPUT_DIR.mkdir(exist_ok=True)
    metrics.to_csv(OUTPUT_DIR / "metrics_by_city.csv", index=False)
    gdf = gpd.GeoDataFrame(metrics, geometry=gpd.points_from_xy(metrics.longitude, metrics.latitude), crs="EPSG:4326")
    gdf.to_file(OUTPUT_DIR / "metrics_by_city.geojson", driver="GeoJSON")

    # map
    m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="CartoDB positron")
    HeatMap([[r.latitude, r.longitude, r.pm25] for r in gdf.itertuples() if not pd.isna(r.pm25)]).add_to(m)
    for r in gdf.itertuples():
        pm_disp = f"{r.pm25:.1f}" if not pd.isna(r.pm25) else "N/A"
        co2_disp = f"{r.co2:.1f}" if not pd.isna(r.co2) else "N/A"
        tri_disp = str(int(r.tri_facilities))
        folium.CircleMarker(
            [r.latitude, r.longitude], radius=5,
            popup=(f"<b>{r.city}</b><br>PM2.5: {pm_disp} µg/m³" \
                   f"<br>CO₂: {co2_disp} t/day" \
                   f"<br>TRI facilities: {tri_disp}"),
            color="black", fill=True, fill_opacity=0.7).add_to(m)
    m.save(OUTPUT_DIR / "air_quality_map.html")
    print("🎉 Completed — see outputs/ folder.")

if __name__ == "__main__":
    main()
