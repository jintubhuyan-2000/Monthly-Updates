"""Reusable Earth Engine statistics."""
import ee

def zonal_statistics(image, roi, scale=250):
    return image.reduceRegion(
        ee.Reducer.mean().combine(ee.Reducer.median(), "", True)
        .combine(ee.Reducer.minMax(), "", True)
        .combine(ee.Reducer.stdDev(), "", True),
        roi.geometry(), scale, maxPixels=1e13, bestEffort=True)

def class_area_hectares(label_image, roi, class_values, scale=10):
    area = ee.Image.pixelArea().divide(10000)
    features = []
    for value in class_values:
        result = area.updateMask(label_image.eq(value)).reduceRegion(
            ee.Reducer.sum(), roi.geometry(), scale, maxPixels=1e13, bestEffort=True)
        features.append(ee.Feature(None, {"class":value, "area_ha":result.get("area")}))
    return ee.FeatureCollection(features)

def class_area_from_histogram(label_image, roi, scale=10):
    area_img = ee.Image.pixelArea().divide(10000).addBands(label_image.rename("class"))
    return area_img.reduceRegion(
        ee.Reducer.sum().group(groupField=1, groupName="class"),
        roi.geometry(), scale, maxPixels=1e13, bestEffort=True).get("groups")
