"""Interactive geemap maps."""
import geemap.foliumap as geemap

NDVI_PALETTE = ["b2182b","ef8a62","fddbc7","ffffbf","a6d96a","66bd63","1a9850","006837"]
CHANGE_PALETTE = ["b2182b","ef8a62","fddbc7","f7f7f7","d9f0d3","7fbf7b","1b7837"]

def create_map(roi, center=(26.58,93.17), zoom=10):
    m=geemap.Map(center=center,zoom=zoom)
    m.addLayer(roi.style(color="FFFFFF",fillColor="00000000",width=2),{},"Kaziranga boundary")
    return m

def add_ndvi_layer(m,image,name="NDVI"):
    m.addLayer(image,{"min":0,"max":1,"palette":NDVI_PALETTE},name)

def add_change_layer(m,image,name="NDVI Change"):
    m.addLayer(image,{"min":-0.5,"max":0.5,"palette":CHANGE_PALETTE},name)

def add_lulc_layer(m,image,name,maximum=9,palette=None):
    palette=palette or ["419bdf","397d49","88b053","7a87c6","e49635","dfc35a","c4281b","a59b8f","b39fe1","ffffff"]
    m.addLayer(image,{"min":0 if maximum==8 else 1,"max":maximum,"palette":palette},name)
