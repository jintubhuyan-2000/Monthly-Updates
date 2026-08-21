"""Endpoint and pixel-wise NDVI change detection."""
import ee

def image_difference(image_a, image_b, band="NDVI", roi=None):
    out = image_b.select(band).subtract(image_a.select(band)).rename(f"{band}_change")
    return out.clip(roi.geometry()) if roi is not None else out

def percent_change(image_a, image_b, band="NDVI", roi=None):
    a = image_a.select(band)
    b = image_b.select(band)
    out = b.subtract(a).divide(a.abs().max(1e-6)).multiply(100).rename(f"{band}_percent_change")
    return out.clip(roi.geometry()) if roi is not None else out

def endpoint_stats(image_a, image_b, roi, scale=250):
    combined = image_a.rename("start_ndvi").addBands(image_b.rename("end_ndvi"))
    return combined.reduceRegion(
        ee.Reducer.mean().combine(ee.Reducer.median(), "", True)
        .combine(ee.Reducer.minMax(), "", True)
        .combine(ee.Reducer.stdDev(), "", True),
        roi.geometry(), scale, maxPixels=1e13, bestEffort=True)

def transition_image(class_a, class_b):
    return class_a.multiply(100).add(class_b).rename("transition")

def transition_area(class_a, class_b, roi, classes, scale=10):
    transition = transition_image(class_a, class_b)
    area = ee.Image.pixelArea().divide(10000)
    feats = []
    for a in classes:
        for b in classes:
            result = area.updateMask(transition.eq(a*100+b)).reduceRegion(
                ee.Reducer.sum(), roi.geometry(), scale, maxPixels=1e13, bestEffort=True)
            feats.append(ee.Feature(None, {"from":a, "to":b, "area_ha":result.get("area")}))
    return ee.FeatureCollection(feats)
