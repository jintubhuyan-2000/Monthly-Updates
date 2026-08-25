"""Small GUI: KML/KMZ -> ESRI Shapefile."""

import os
import sys
import zipfile
import tempfile
import shutil
import importlib.util
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

missing = []
for module, package in [("geopandas", "geopandas"), ("shapely", "shapely")]:
    if importlib.util.find_spec(module) is None:
        missing.append(package)

if missing:
    print("Missing packages. Install with:")
    print("pip install geopandas pyogrio shapely fiona")
    sys.exit(1)

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection

WGS84 = "EPSG:4326"


def safe_filename(name):
    for c in '<>:"/\\|?*':
        name = name.replace(c, "_")
    return name.strip().strip(".") or "converted"


def extract_kmz(path):
    temp = tempfile.mkdtemp(prefix="kmz_to_shp_")
    try:
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(temp)
        kmls = []
        for root, _, files in os.walk(temp):
            for f in files:
                if f.lower().endswith(".kml"):
                    kmls.append(os.path.join(root, f))
        if not kmls:
            raise ValueError("No KML file was found inside the KMZ.")
        doc = [p for p in kmls if os.path.basename(p).lower() == "doc.kml"]
        return temp, (doc[0] if doc else kmls[0])
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def read_source(path):
    ext = os.path.splitext(path)[1].lower()
    temp = None
    kml = path

    if ext == ".kmz":
        temp, kml = extract_kmz(path)
    elif ext != ".kml":
        raise ValueError("Only .kml and .kmz files are supported.")

    try:
        try:
            import fiona
            fiona.drvsupport.supported_drivers["KML"] = "rw"
            fiona.drvsupport.supported_drivers["LIBKML"] = "rw"
        except Exception:
            pass

        try:
            gdf = gpd.read_file(kml, engine="pyogrio")
        except Exception:
            gdf = gpd.read_file(kml)

        if gdf.empty:
            raise ValueError("The KML/KMZ contains no readable features.")

        if gdf.crs is None:
            gdf = gdf.set_crs(WGS84)
        return gdf
    finally:
        if temp:
            shutil.rmtree(temp, ignore_errors=True)


def clean_columns(gdf):
    rename = {}
    used = set()
    for col in gdf.columns:
        if col == "geometry":
            continue
        name = "".join(c if c.isalnum() or c == "_" else "_" for c in str(col))
        name = (name or "FIELD")[:10]
        base = name
        n = 1
        while name.upper() in used:
            suffix = str(n)
            name = base[:10-len(suffix)] + suffix
            n += 1
        used.add(name.upper())
        rename[col] = name
    return gdf.rename(columns=rename)


def parts_of(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, GeometryCollection):
        result = []
        for g in geom.geoms:
            result.extend(parts_of(g))
        return result
    if isinstance(geom, (MultiPoint, MultiLineString, MultiPolygon)):
        result = []
        for g in geom.geoms:
            result.extend(parts_of(g))
        return result
    return [geom]


def split_geometry_types(gdf):
    rows = {"Point": [], "LineString": [], "Polygon": []}

    for _, row in gdf.iterrows():
        for geom in parts_of(row.geometry):
            r = row.copy()
            r.geometry = geom
            if isinstance(geom, Point):
                rows["Point"].append(r)
            elif isinstance(geom, LineString):
                rows["LineString"].append(r)
            elif isinstance(geom, Polygon):
                rows["Polygon"].append(r)

    result = {}
    for typ, values in rows.items():
        if values:
            result[typ] = gpd.GeoDataFrame(values, geometry="geometry",
                                           crs=gdf.crs or WGS84)
    return result


def convert(path, output):
    os.makedirs(output, exist_ok=True)
    base = safe_filename(os.path.splitext(os.path.basename(path))[0])
    groups = split_geometry_types(read_source(path))

    if not groups:
        raise ValueError("No Point, LineString, or Polygon geometry found.")

    generated = []
    multiple = len(groups) > 1

    for typ, gdf in groups.items():
        name = f"{base}_{typ}" if multiple else base
        shp = os.path.join(output, safe_filename(name) + ".shp")
        gdf = clean_columns(gdf)

        for col in gdf.columns:
            if col != "geometry" and pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)

        gdf.to_file(shp, driver="ESRI Shapefile", encoding="UTF-8",
                    engine="pyogrio")
        generated.append(shp)

    return generated


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KML / KMZ → Shapefile Converter")
        self.geometry("760x500")
        self.minsize(650, 450)

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready.")

        main = ttk.Frame(self, padding=20)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="KML / KMZ → Shapefile",
                  font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text="Convert KML or KMZ geographic data to ESRI Shapefile.",
                  font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 18))

        inf = ttk.LabelFrame(main, text="1. Input KML / KMZ", padding=12)
        inf.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(inf)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.input_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self.choose_input).pack(side="left", padx=(8, 0))

        outf = ttk.LabelFrame(main, text="2. Output Folder", padding=12)
        outf.pack(fill="x", pady=(0, 12))
        row = ttk.Frame(outf)
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.output_var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self.choose_output).pack(side="left", padx=(8, 0))

        info = ttk.LabelFrame(main, text="What this converter does", padding=12)
        info.pack(fill="both", expand=True, pady=(0, 12))
        ttk.Label(info, justify="left",
                  text=("• Supports .KML and .KMZ\n"
                        "• Supports Point, LineString and Polygon\n"
                        "• Mixed geometries are automatically split into separate shapefiles\n"
                        "• KML/KMZ is written as WGS 84 (EPSG:4326)\n"
                        "• Creates .shp, .shx, .dbf and .prj\n"
                        "• Preserves attributes where supported")).pack(anchor="nw")

        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 6))
        ttk.Label(main, textvariable=self.status_var).pack(anchor="w", pady=(0, 10))

        buttons = ttk.Frame(main)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left")
        ttk.Button(buttons, text="Convert to Shapefile",
                   command=self.run_convert).pack(side="right")

    def choose_input(self):
        path = filedialog.askopenfilename(
            title="Select KML/KMZ",
            filetypes=[("KML/KMZ", "*.kml *.kmz"),
                       ("KML", "*.kml"), ("KMZ", "*.kmz"),
                       ("All files", "*.*")]
        )
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                self.output_var.set(os.path.dirname(path))
            self.status_var.set("Selected: " + os.path.basename(path))

    def choose_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_var.set(folder)
            self.status_var.set("Output folder selected.")

    def run_convert(self):
        src = self.input_var.get().strip()
        out = self.output_var.get().strip()

        if not src or not os.path.isfile(src):
            messagebox.showwarning("Input Required", "Please select a valid KML/KMZ file.")
            return
        if os.path.splitext(src)[1].lower() not in (".kml", ".kmz"):
            messagebox.showwarning("Invalid File", "Please select a .kml or .kmz file.")
            return
        if not out:
            messagebox.showwarning("Output Required", "Please select an output folder.")
            return

        self.progress.start(10)
        self.status_var.set("Converting... Please wait.")
        self.update_idletasks()

        try:
            files = convert(src, out)
            self.progress.stop()
            self.status_var.set(f"Completed: {len(files)} shapefile(s).")
            names = "\n".join(os.path.basename(x) for x in files)
            messagebox.showinfo("Conversion Complete",
                                "Conversion completed successfully.\n\n"
                                f"Created:\n{names}\n\nOutput folder:\n{out}")
        except Exception as e:
            self.progress.stop()
            self.status_var.set("Conversion failed.")
            traceback.print_exc()
            messagebox.showerror(
                "Conversion Error",
                f"{type(e).__name__}: {e}\n\n"
                "If the error mentions KML/LIBKML/GDAL, reinstall the "
                "geospatial packages in a Conda environment."
            )

    def clear(self):
        self.input_var.set("")
        self.output_var.set("")
        self.status_var.set("Ready.")


if __name__ == "__main__":
    App().mainloop()