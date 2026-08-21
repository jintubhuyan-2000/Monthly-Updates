# Kaziranga Ecological Change Explorer — amended build

## What changed

- Overview defaults to **2006–2026** and reports:
  - Kaziranga Overview
  - Analysis start
  - Analysis end
  - complete monthly count
  - long-term mean NDVI
- Current incomplete month is excluded, so in August 2026 the 2006–2026 range contains **247 complete months**.
- NDVI uses **Landsat Collection 2 Level-2 Surface Reflectance (30 m)** instead of MODIS. NDVI Explorer can load **every available monthly Landsat NDVI map as an interactive layer** with a layer control.
- Change Detection:
  - start endpoint = January of the selected year
  - end endpoint = the final month in the selected date range
  - maps start NDVI, end NDVI, absolute difference and percentage change
  - reports endpoint means and change
- Trend analysis:
  - linear slope
  - R²
  - Mann–Kendall tau and p-value
  - Sen's slope
  - increasing/decreasing classification
- LULC:
  - Dynamic World by default
  - ESRI Global LULC by default
  - MODIS MCD12Q1 included as long-term LULC context
  - annual class-area tables
  - annual area charts
  - latest available annual LULC maps
  - CSV export
- Long Earth Engine operations use Streamlit status/progress indicators.

## Run

```bash
pip install -r requirements.txt

**Important Windows compatibility fix:** this build pins `geemap==0.36.6`. Newer geemap releases can raise `BoxKeyError: 'Box' object has no attribute 'xyz_to_folium'` when importing `geemap.foliumap` because of a basemap namespace collision. If you already installed a newer geemap, run:

```bash
python -m pip uninstall -y geemap
python -m pip install --force-reinstall geemap==0.36.6 python-box
```

Or double-click `INSTALL_WINDOWS.bat`.

earthengine authenticate
streamlit run app.py
```

The application uses:
`projects/webapp-385310/assets/Kaziranga`

## Notes

Earth Engine dataset availability is not identical across products. Dynamic World and ESRI have shorter histories than MODIS. ESRI/MODIS years with no intersecting image are skipped or reported rather than fabricated.

For a very large number of map layers, browser rendering can be heavy. The monthly-layer switch in the sidebar lets you turn the 247-layer view off while keeping the statistics and charts.


## Fixed ROI
All NDVI, change-detection, trend, Dynamic World, ESRI LULC, MODIS LULC, and related map/statistical outputs are constrained to the Earth Engine asset:
`projects/webapp-385310/assets/Kaziranga`

Raster outputs are explicitly clipped to the ROI before map display/statistical processing.
\n## Landsat NDVI\nThe NDVI workflow uses Landsat 5/7/8/9 Collection 2 Level-2 Surface Reflectance, harmonized to a common NDVI calculation and clipped to the fixed Kaziranga ROI. The default analysis scale is 30 m.\n\n## NDVI map colours\nNDVI is displayed with a low-to-high **red → yellow → green** palette, so healthier vegetation appears green. Change maps retain a diverging red/white/green palette so losses and gains are visually distinct.\n\n## Streamlit Plotly keys\nEvery Plotly chart has an explicit unique `key` to prevent `StreamlitDuplicateElementId` errors when the same chart function is rendered in multiple tabs.\n