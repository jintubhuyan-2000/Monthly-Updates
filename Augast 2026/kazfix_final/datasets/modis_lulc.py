"""MODIS MCD12Q1 annual IGBP land cover."""
import ee
from config import MODIS_LULC

def annual_label(year, roi):
    start,end=ee.Date.fromYMD(year,1,1),ee.Date.fromYMD(year+1,1,1)
    return ee.ImageCollection(MODIS_LULC).filterBounds(roi).filterDate(start,end).first().select("LC_Type1").clip(roi.geometry()).set("year",year)
