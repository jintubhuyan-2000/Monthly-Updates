"""Landsat NDVI collections and monthly composites."""

import ee
from config import LANDSAT_5, LANDSAT_7, LANDSAT_8, LANDSAT_9


def _mask_landsat(img):
    qa = img.select("QA_PIXEL")
    mask = (
        qa.bitwiseAnd(1 << 1).eq(0)  # dilated cloud
        .And(qa.bitwiseAnd(1 << 2).eq(0))  # cirrus
        .And(qa.bitwiseAnd(1 << 3).eq(0))  # cloud
        .And(qa.bitwiseAnd(1 << 4).eq(0))  # cloud shadow
        .And(qa.bitwiseAnd(1 << 5).eq(0))  # snow
    )
    return img.updateMask(mask)


def _prep_landsat(img, sensor):
    img = _mask_landsat(img)
    if sensor in ("L5", "L7"):
        red, nir = "SR_B3", "SR_B4"
    else:
        red, nir = "SR_B4", "SR_B5"

    red_img = img.select(red).multiply(0.0000275).add(-0.2)
    nir_img = img.select(nir).multiply(0.0000275).add(-0.2)

    return (
        nir_img.subtract(red_img)
        .divide(nir_img.add(red_img))
        .rename("NDVI")
        .copyProperties(img, ["system:time_start"])
    )


def landsat_ndvi_collection(roi: ee.FeatureCollection, start, end):
    collections = [
        ee.ImageCollection(LANDSAT_5).filterBounds(roi).filterDate(start, end)
        .map(lambda x: _prep_landsat(x, "L5")),
        ee.ImageCollection(LANDSAT_7).filterBounds(roi).filterDate(start, end)
        .map(lambda x: _prep_landsat(x, "L7")),
        ee.ImageCollection(LANDSAT_8).filterBounds(roi).filterDate(start, end)
        .map(lambda x: _prep_landsat(x, "L8")),
        ee.ImageCollection(LANDSAT_9).filterBounds(roi).filterDate(start, end)
        .map(lambda x: _prep_landsat(x, "L9")),
    ]
    return collections[0].merge(collections[1]).merge(collections[2]).merge(collections[3])


def monthly_landsat_ndvi(year: int, month: int, roi: ee.FeatureCollection):
    start = ee.Date.fromYMD(year, month, 1)
    end = start.advance(1, "month")
    return (
        landsat_ndvi_collection(roi, start, end)
        .median()
        .clip(roi.geometry())
        .set({"year": year, "month": month, "system:time_start": start.millis()})
    )
