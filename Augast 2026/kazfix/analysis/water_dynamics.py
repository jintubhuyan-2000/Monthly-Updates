"""Water and flooded-vegetation dynamics using Dynamic World."""

import ee


def water_frequency(start, end, roi, threshold=0.5):
    col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate(start, end)
    )

    def water_probability(img):
        return img.select("water").gte(threshold).rename("water")

    return col.map(water_probability).mean().rename("water_frequency")


def flooded_vegetation_frequency(start, end, roi, threshold=0.5):
    col = (
        ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
        .filterBounds(roi)
        .filterDate(start, end)
    )

    def fv(img):
        return img.select("flooded_vegetation").gte(threshold).rename(
            "flooded_vegetation"
        )

    return col.map(fv).mean().rename("flooded_vegetation_frequency")
