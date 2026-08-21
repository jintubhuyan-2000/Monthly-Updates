"""NDVI anomaly analysis."""

import ee


def long_term_mean(ndvi_collection):
    return ndvi_collection.mean().rename("NDVI_mean")


def anomaly(image, baseline):
    return image.subtract(baseline).rename("NDVI_anomaly")


def collection_anomalies(ndvi_collection):
    baseline = long_term_mean(ndvi_collection)

    def make_anomaly(img):
        return anomaly(img, baseline).set(
            "system:time_start", img.get("system:time_start")
        ).set(
            "year", img.get("year")
        ).set(
            "month", img.get("month")
        )

    return ndvi_collection.map(make_anomaly)
