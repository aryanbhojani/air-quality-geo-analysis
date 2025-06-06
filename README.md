# Air Quality Geospatial Analysis (USA 2024)

Python • GeoPandas • Folium • ArcGIS Online

Pipeline that blends **PM2.5**, **daily CO₂**, and **EPA TRI industrial‑facility
density** to map air‑quality hotspots across different U.S cities.

---

## Interactive map  
[View the interactive ArcGIS Map](https://ucsb.maps.arcgis.com/apps/mapviewer/index.html?webmap=f6ecfc63b55a437abc3a69f6389566ec)


---

## Quick‑start

```bash
# clone the repo
git clone https://github.com/aryanbhojani/air-quality-geo-analysis.git
cd air-quality-geo-analysis

# create the Conda env
conda env create -f environment.yml
conda activate airgeo

# drop required data files into ./data/  (see “Data sources” below)
python air_quality_geospatial_analysis.py
# → outputs/air_quality_map.html, metrics_by_city.csv, metrics_by_city.geojson
