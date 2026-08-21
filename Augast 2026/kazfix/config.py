"""Configuration for the Kaziranga Ecological Change Explorer."""
from datetime import date

APP_TITLE = "Kaziranga 20-Year Ecological Change Explorer"
GEE_PROJECT = "webapp-385310"
# AUTHORITATIVE ROI — do not replace with a bounding box or user-drawn geometry.
KAZIRANGA_ASSET = "projects/webapp-385310/assets/Kaziranga"

CURRENT_YEAR = date.today().year
CURRENT_MONTH = date.today().month
DEFAULT_START_YEAR = 2006
DEFAULT_END_YEAR = CURRENT_YEAR

MODIS_NDVI = "MODIS/061/MOD13Q1"
DYNAMIC_WORLD = "GOOGLE/DYNAMICWORLD/V1"
MODIS_LULC = "MODIS/061/MCD12Q1"
ESRI_LULC = "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m"
LANDSAT_NDVI_SCALE = 30
LANDSAT_5 = "LANDSAT/LT05/C02/T1_L2"
LANDSAT_7 = "LANDSAT/LE07/C02/T1_L2"
LANDSAT_8 = "LANDSAT/LC08/C02/T1_L2"
LANDSAT_9 = "LANDSAT/LC09/C02/T1_L2"

DW_CLASSES = {
    0: "Water", 1: "Trees", 2: "Grass", 3: "Flooded vegetation",
    4: "Crops", 5: "Shrub & scrub", 6: "Built area",
    7: "Bare ground", 8: "Snow & ice",
}
ESRI_CLASSES = {
    1: "Water", 2: "Trees", 3: "Grass", 4: "Flooded vegetation",
    5: "Crops", 6: "Scrub", 7: "Built area", 8: "Bare ground",
    9: "Snow & ice", 10: "Clouds",
}
MODIS_IGBP_CLASSES = {
    1:"Evergreen needleleaf forest",2:"Evergreen broadleaf forest",
    3:"Deciduous needleleaf forest",4:"Deciduous broadleaf forest",
    5:"Mixed forest",6:"Closed shrublands",7:"Open shrublands",
    8:"Woody savannas",9:"Savannas",10:"Grasslands",11:"Permanent wetlands",
    12:"Croplands",13:"Urban and built-up",
    14:"Cropland/natural vegetation mosaic",15:"Permanent snow and ice",
    16:"Barren or sparsely vegetated",17:"Water bodies",
}
SEASONS = {
    "Winter":[12,1,2], "Pre-monsoon":[3,4,5],
    "Monsoon":[6,7,8,9], "Post-monsoon":[10,11],
}
