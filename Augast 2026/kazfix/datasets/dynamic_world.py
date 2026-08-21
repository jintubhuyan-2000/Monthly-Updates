"""Dynamic World annual/monthly land-cover helpers."""
import ee
from config import DYNAMIC_WORLD

PROB_BANDS = ["water","trees","grass","flooded_vegetation","crops",
              "shrub_and_scrub","built","bare","snow_and_ice"]

def collection(roi, start, end):
    return ee.ImageCollection(DYNAMIC_WORLD).filterBounds(roi).filterDate(start, end)

def _confident(img, confidence):
    probs = img.select(PROB_BANDS)
    return img.select("label").updateMask(probs.reduce(ee.Reducer.max()).gte(confidence))

def annual_label(year, roi, confidence=0.6):
    start, end = ee.Date.fromYMD(year,1,1), ee.Date.fromYMD(year+1,1,1)
    return collection(roi,start,end).map(lambda x:_confident(x,confidence)).mode().clip(roi.geometry()).set("year",year)

def monthly_label(year, month, roi, confidence=0.6):
    start = ee.Date.fromYMD(year,month,1)
    return collection(roi,start,start.advance(1,"month")).map(
        lambda x:_confident(x,confidence)).mode().clip(roi.geometry()).set(
            {"year":year,"month":month,"system:time_start":start.millis()})
