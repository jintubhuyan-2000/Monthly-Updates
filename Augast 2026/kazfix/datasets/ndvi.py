"""Monthly Landsat NDVI composites and ROI statistics."""
import datetime
import ee
from datasets.landsat import monthly_landsat_ndvi


def monthly_ndvi(year: int, month: int, roi):
    return monthly_landsat_ndvi(year, month, roi)


def monthly_landsat_collection(start_year, end_year, roi):
    today = datetime.date.today()
    last_complete = (today.year, today.month - 1)
    if today.month == 1:
        last_complete = (today.year - 1, 12)
    images = []
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            if (y, m) > last_complete:
                continue
            images.append(monthly_landsat_ndvi(y, m, roi))
    return ee.ImageCollection.fromImages(images)


def monthly_ndvi_feature_collection(collection, roi, scale=30):
    def to_feature(img):
        stats = img.reduceRegion(
            ee.Reducer.mean()
            .combine(ee.Reducer.median(), "", True)
            .combine(ee.Reducer.minMax(), "", True)
            .combine(ee.Reducer.stdDev(), "", True),
            geometry=roi.geometry(), scale=scale, maxPixels=1e13, bestEffort=True)
        return ee.Feature(None, {
            "date": ee.Date(img.get("system:time_start")).format("YYYY-MM"),
            "year": img.get("year"), "month": img.get("month"),
            "mean_ndvi": stats.get("NDVI_mean"),
            "median_ndvi": stats.get("NDVI_median"),
            "min_ndvi": stats.get("NDVI_min"),
            "max_ndvi": stats.get("NDVI_max"),
            "std_ndvi": stats.get("NDVI_stdDev"),
        })
    return ee.FeatureCollection(collection.map(to_feature))
