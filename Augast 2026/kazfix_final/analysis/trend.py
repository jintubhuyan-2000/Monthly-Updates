"""Pixel trend helpers. Statistical Mann-Kendall/Sen calculations are done on ROI means in Python."""
import ee

def add_time_band(img):
    # fractional year makes the slope interpretable as NDVI change per year
    t = ee.Image.constant(ee.Date(img.get("system:time_start")).difference(
        ee.Date("2000-01-01"), "year")).rename("time").float()
    return t.addBands(img.select("NDVI").float())

def linear_ndvi_trend(ndvi_collection):
    return ndvi_collection.map(add_time_band).select(["time","NDVI"]).reduce(ee.Reducer.linearFit())

def trend_slope(ndvi_collection):
    return linear_ndvi_trend(ndvi_collection).select("scale")
