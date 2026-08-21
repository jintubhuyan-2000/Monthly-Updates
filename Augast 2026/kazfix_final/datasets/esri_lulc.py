"""ESRI Global LULC 10m annual helpers."""
import ee
from config import ESRI_LULC

def collection(roi, start=None, end=None):
    col = ee.ImageCollection(ESRI_LULC).filterBounds(roi)
    if start is not None: col = col.filterDate(start,end)
    return col

def annual_label(year, roi):
    # ESRI Global LULC is a yearly product. Mosaic intersecting tiles.
    start, end = ee.Date.fromYMD(year,1,1), ee.Date.fromYMD(year+1,1,1)
    col = collection(roi,start,end)
    return col.select("b1").mosaic().rename("class").clip(roi.geometry()).set("year",year)

def available_years(roi, start_year=2017, end_year=None):
    end_year = end_year or __import__("datetime").date.today().year
    return list(range(start_year,end_year+1))
