"""Sentinel-2 NDVI functions."""

import ee
from config import S2_SR


def mask_s2(img):
    scl = img.select("SCL")
    mask = (
        scl.neq(3)   # cloud shadow
        .And(scl.neq(8))   # cloud medium probability
        .And(scl.neq(9))   # cloud high probability
        .And(scl.neq(10))  # cirrus
        .And(scl.neq(11))  # snow/ice
    )
    return img.updateMask(mask)


def monthly_sentinel2_ndvi(year: int, month: int, roi: ee.FeatureCollection):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")

    collection = (
        ee.ImageCollection(S2_SR)
        .filterBounds(roi)
        .filterDate(start, end)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", 80))
        .map(mask_s2)
    )

    def add_ndvi(img):
        return (
            img.normalizedDifference(["B8", "B4"])
            .rename("NDVI")
            .copyProperties(img, ["system:time_start"])
        )

    return (
        collection.map(add_ndvi)
        .median()
        .clip(roi.geometry())
        .set({"year": year, "month": month, "system:time_start": start.millis()})
    )
