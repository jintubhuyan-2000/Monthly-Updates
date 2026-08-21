"""LULC transition matrix utilities."""

import ee


def transition_matrix(class_a, class_b, roi, classes, scale=10):
    pixel_area = ee.Image.pixelArea().divide(10000)
    transition = class_a.multiply(100).add(class_b)

    features = []
    for from_class in classes:
        for to_class in classes:
            code = from_class * 100 + to_class
            area = pixel_area.updateMask(transition.eq(code)).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=roi.geometry(),
                scale=scale,
                maxPixels=1e13,
                bestEffort=True,
            )
            features.append(ee.Feature(None, {
                "from": from_class,
                "to": to_class,
                "area_ha": area.get("area")
            }))

    return ee.FeatureCollection(features)
