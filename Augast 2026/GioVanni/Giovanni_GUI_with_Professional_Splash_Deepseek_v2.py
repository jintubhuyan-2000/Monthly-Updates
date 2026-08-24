# =============================================================================
# NASA GIOVANNI AREA-AVERAGED TIME SERIES GUI WITH OSM MAP INTEGRATION
# =============================================================================
#
# WORKING SOLUTION:
# - Map opens in browser (reliable)
# - Auto-detects rectangle drawing
# - Auto-updates coordinates in main window
# - Seamless user experience
#
# =============================================================================

import os
import re
import math
import zipfile
import threading
import traceback
import warnings
import sys
import time
import json
import webbrowser
import tempfile
import subprocess
import socket
import http.server
import socketserver
import threading
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter.font import Font

import numpy as np
import pandas as pd
import requests
import earthaccess

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection
import matplotlib.colors as colors

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union
from shapely.geometry import shape

import xml.etree.ElementTree as ET

# For OSM map integration
import folium
from folium import plugins

warnings.filterwarnings('ignore')

# =============================================================================
# SPLASH SCREEN CLASS
# =============================================================================

class SplashScreen:
    """Professional splash screen with loading progress"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.configure(bg='#0a1628')
        
        window_width = 600
        window_height = 400
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.attributes('-topmost', True)
        
        main_frame = tk.Frame(self.root, bg='#0a1628')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        nasa_frame = tk.Frame(main_frame, bg='#0a1628')
        nasa_frame.pack(pady=(30, 10))
        
        nasa_label = tk.Label(
            nasa_frame,
            text="NASA",
            font=("Arial", 40, "bold"),
            fg='#fc3d21',
            bg='#0a1628'
        )
        nasa_label.pack(side=tk.LEFT)
        
        nasa_sub = tk.Label(
            nasa_frame,
            text="GIOVANNI",
            font=("Arial", 36, "bold"),
            fg='#ffffff',
            bg='#0a1628'
        )
        nasa_sub.pack(side=tk.LEFT, padx=(10, 0))
        
        earth_frame = tk.Frame(main_frame, bg='#0a1628')
        earth_frame.pack(pady=5)
        
        earth_label = tk.Label(
            earth_frame,
            text="🌍",
            font=("Arial", 48),
            bg='#0a1628'
        )
        earth_label.pack()
        
        subtitle = tk.Label(
            main_frame,
            text="Area-Averaged Time Series Analysis",
            font=("Arial", 16),
            fg='#87CEEB',
            bg='#0a1628'
        )
        subtitle.pack(pady=(10, 20))
        
        self.status_var = tk.StringVar(value="Initializing application...")
        status_label = tk.Label(
            main_frame,
            textvariable=self.status_var,
            font=("Arial", 11),
            fg='#cccccc',
            bg='#0a1628'
        )
        status_label.pack(pady=(10, 10))
        
        self.progress = ttk.Progressbar(
            main_frame,
            length=400,
            mode='determinate',
            maximum=100
        )
        self.progress.pack(pady=10)
        
        self.percent_var = tk.StringVar(value="0%")
        percent_label = tk.Label(
            main_frame,
            textvariable=self.percent_var,
            font=("Arial", 10),
            fg='#aaaaaa',
            bg='#0a1628'
        )
        percent_label.pack()
        
        version_frame = tk.Frame(main_frame, bg='#0a1628')
        version_frame.pack(side=tk.BOTTOM, pady=(20, 0))
        
        version_label = tk.Label(
            version_frame,
            text="Version 2.0 | Developed by Jintu Moni Bhuyan",
            font=("Arial", 9),
            fg='#666666',
            bg='#0a1628'
        )
        version_label.pack()
        
        copyright_label = tk.Label(
            version_frame,
            text="© 2026 NASA Giovanni Data Analysis Tool",
            font=("Arial", 8),
            fg='#555555',
            bg='#0a1628'
        )
        copyright_label.pack()
        
        self.anim_label = tk.Label(
            main_frame,
            text="Loading.",
            font=("Arial", 12),
            fg='#87CEEB',
            bg='#0a1628'
        )
        self.anim_label.pack(pady=(5, 0))
        self.anim_count = 0
        self.anim_running = True
        self.animate_loading()
        
        self.root.update()
        
    def animate_loading(self):
        if not self.anim_running:
            return
        dots = "." * (self.anim_count % 4)
        self.anim_label.config(text=f"Loading{dots}")
        self.anim_count += 1
        self.root.after(500, self.animate_loading)
    
    def update_progress(self, value, status=None):
        if status:
            self.status_var.set(status)
        self.progress['value'] = value
        self.percent_var.set(f"{int(value)}%")
        self.root.update()
        
    def close(self):
        self.anim_running = False
        self.root.destroy()
        
    def run(self):
        self.root.mainloop()

# =============================================================================
# LOADING TASKS WITH PROGRESS
# =============================================================================

def load_with_splash():
    """Load the application with splash screen progress"""
    
    splash = SplashScreen()
    
    tasks = [
        (5, "Loading NumPy...", lambda: np.__version__),
        (10, "Loading Pandas...", lambda: pd.__version__),
        (15, "Loading Matplotlib...", lambda: plt.__version__),
        (20, "Loading Shapely...", lambda: None),
        (25, "Loading Earthaccess...", lambda: earthaccess.__version__),
        (30, "Loading Folium for OSM...", lambda: folium.__version__),
        (40, "Initializing geospatial components...", lambda: None),
        (50, "Loading XML processing...", lambda: None),
        (60, "Loading product catalogue...", lambda: None),
        (70, "Initializing Tkinter components...", lambda: None),
        (80, "Building main interface...", lambda: None),
        (90, "Finalizing configuration...", lambda: None),
        (100, "Application ready! Starting...", lambda: None),
    ]
    
    for progress, status, task in tasks:
        splash.update_progress(progress, status)
        time.sleep(0.3)
        
    splash.close()
    
    root = tk.Tk()
    app = GiovanniGUI(root)
    root.mainloop()

# =============================================================================
# GIOVANNI API
# =============================================================================

GIOVANNI_API = "https://api.giovanni.earthdata.nasa.gov/timeseries"

# =============================================================================
# PRODUCT CATALOGUE
# =============================================================================

PRODUCTS = {
    "GPM IMERG V07 - Final Run": {
        "variables": {
            "Precipitation": "GPM_3IMERGHH_07_precipitation",
            "Random Error": "GPM_3IMERGHH_07_randomError",
            "Probability of Liquid Phase": "GPM_3IMERGHH_07_probLiquidPrecipitation"
        },
        "native_minutes": 30,
        "precipitation": True,
        "data_type": "half_hourly"
    },
    "GPM IMERG V07 - Late Run": {
        "variables": {
            "Precipitation": "GPM_3IMERGHHL_07_precipitation",
        },
        "native_minutes": 30,
        "precipitation": True,
        "data_type": "half_hourly"
    },
    "GPM IMERG V07 - Early Run": {
        "variables": {
            "Precipitation": "GPM_3IMERGHHE_07_precipitation",
        },
        "native_minutes": 30,
        "precipitation": True,
        "data_type": "half_hourly"
    },
    "GLDAS Noah 0.25° V2.1": {
        "variables": {
            "Near Surface Air Temperature": "GLDAS_NOAH025_3H_2_1_Tair_f_inst",
            "Total Precipitation": "GLDAS_NOAH025_3H_2_1_Precip_tavg",
            "Root Zone Soil Moisture": "GLDAS_NOAH025_3H_2_1_SoilMoiRootZone_inst",
            "Surface Soil Moisture": "GLDAS_NOAH025_3H_2_1_SoilMoi0_10cm_inst",
            "Wind Speed": "GLDAS_NOAH025_3H_2_1_Wind_f_inst"
        },
        "native_minutes": 180,
        "precipitation": False,
        "data_type": "half_hourly"
    },
    "MERRA-2": {
        "variables": {
            "2 m Air Temperature": "M2T1NXSLV_T2M",
            "Total Precipitation": "M2T1NXFLX_PRECTOT",
            "Surface Wind Speed": "M2T1NXFLX_WIND10M",
            "Specific Humidity": "M2T1NXSLV_QV2M"
        },
        "native_minutes": 60,
        "precipitation": False,
        "data_type": "hourly"
    }
}

# =============================================================================
# OSM MAP CLASS - WORKING BROWSER-BASED SOLUTION
# =============================================================================

class OSMMapSelector:
    """Interactive OSM map - opens in browser with auto-detection"""
    
    def __init__(self, parent, callback):
        self.parent = parent
        self.callback = callback
        self.bounding_box = None
        self.map_file = None
        self.coords_file = None
        self.monitor_running = False
        self.monitor_thread = None
        
    def open_map(self, initial_bounds=None):
        """Open interactive OSM map in browser with auto-detection"""
        
        # Create the map HTML
        self.map_file = self.create_map_html(initial_bounds)
        
        # Create a coords file for communication
        self.coords_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.coords_file.close()
        
        # Initialize coords file
        with open(self.coords_file.name, 'w') as f:
            json.dump({"coords": None}, f)
        
        # Open in browser
        webbrowser.open('file://' + self.map_file)
        
        # Start monitoring for coordinates
        self.start_monitoring()
        
        return self.map_file
        
    def create_map_html(self, initial_bounds=None):
        """Create the HTML file with the interactive map"""
        
        center_lat = 20
        center_lon = 0
        zoom = 2
        
        if initial_bounds:
            minx, miny, maxx, maxy = initial_bounds
            center_lat = (miny + maxy) / 2
            center_lon = (minx + maxx) / 2
            zoom = 5
        
        # Create map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom,
            tiles='OpenStreetMap',
            control_scale=True
        )
        
        # Add draw plugin
        draw = plugins.Draw(
            export=False,
            position='topleft',
            draw_options={
                'polygon': False,
                'polyline': False,
                'rectangle': True,
                'circle': False,
                'marker': True,
                'circlemarker': False,
                'rectangle_options': {
                    'color': '#ff0000',
                    'weight': 3,
                    'fill': True,
                    'fillColor': '#ff0000',
                    'fillOpacity': 0.2
                }
            }
        )
        draw.add_to(m)
        
        # Create HTML with auto-save functionality
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Select AOI - NASA Giovanni</title>
            <style>
                body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
                #map {{ width: 100%; height: 100vh; }}
                #info {{
                    position: fixed;
                    bottom: 30px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: rgba(0,0,0,0.85);
                    color: white;
                    padding: 12px 24px;
                    border-radius: 10px;
                    font-size: 14px;
                    z-index: 9999;
                    text-align: center;
                    max-width: 80%;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                }}
                #coords {{
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: rgba(0,0,0,0.8);
                    color: #00ff88;
                    padding: 12px 18px;
                    border-radius: 8px;
                    font-family: 'Courier New', monospace;
                    font-size: 13px;
                    z-index: 9999;
                    display: none;
                    max-width: 300px;
                    line-height: 1.8;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                    border: 1px solid #00ff88;
                }}
                .success {{ background: rgba(0,128,0,0.9) !important; }}
                .coords-display {{
                    position: fixed;
                    top: 20px;
                    left: 20px;
                    background: rgba(0,0,0,0.7);
                    color: #ffcc00;
                    padding: 8px 15px;
                    border-radius: 5px;
                    font-family: Arial, sans-serif;
                    font-size: 12px;
                    z-index: 9999;
                    border: 1px solid #ffcc00;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div id="info">✏️ Draw a rectangle on the map to select your Area of Interest</div>
            <div id="coords">Coordinates will appear here</div>
            <div class="coords-display" id="status">🔄 Ready to draw</div>
            
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>
            <link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css" />
            
            <script>
                var map = L.map('map').setView([{center_lat}, {center_lon}], {zoom});
                
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '© OpenStreetMap contributors'
                }}).addTo(map);
                
                var drawnItems = new L.FeatureGroup();
                map.addLayer(drawnItems);
                
                var drawControl = new L.Control.Draw({{
                    draw: {{
                        polygon: false,
                        polyline: false,
                        rectangle: true,
                        circle: false,
                        marker: true,
                        circlemarker: false
                    }},
                    edit: {{
                        featureGroup: drawnItems
                    }}
                }});
                map.addControl(drawControl);
                
                var selectedCoords = null;
                var infoDiv = document.getElementById('info');
                var coordsDiv = document.getElementById('coords');
                var statusDiv = document.getElementById('status');
                
                // Function to save coordinates to file
                function saveCoordinates(coords) {{
                    var xhr = new XMLHttpRequest();
                    xhr.open('POST', 'http://localhost:8765/save', true);
                    xhr.setRequestHeader('Content-Type', 'application/json');
                    xhr.send(JSON.stringify({{coords: coords}}));
                }}
                
                map.on('draw:created', function(e) {{
                    var layer = e.layer;
                    drawnItems.clearLayers();
                    drawnItems.addLayer(layer);
                    
                    var coords;
                    if (e.layerType === 'rectangle') {{
                        var bounds = layer.getBounds();
                        coords = {{
                            west: bounds.getWest(),
                            south: bounds.getSouth(),
                            east: bounds.getEast(),
                            north: bounds.getNorth()
                        }};
                        infoDiv.innerHTML = '✅ Rectangle selected! Coordinates saved.';
                        infoDiv.className = 'success';
                        statusDiv.innerHTML = '✅ Selected: ' + bounds.getWest().toFixed(2) + '° to ' + bounds.getEast().toFixed(2) + '°';
                    }} else if (e.layerType === 'marker') {{
                        var latlng = layer.getLatLng();
                        coords = {{
                            west: latlng.lng - 0.5,
                            south: latlng.lat - 0.5,
                            east: latlng.lng + 0.5,
                            north: latlng.lat + 0.5
                        }};
                        infoDiv.innerHTML = '✅ Marker placed with 0.5° buffer! Coordinates saved.';
                        infoDiv.className = 'success';
                        statusDiv.innerHTML = '✅ Marker at: ' + latlng.lat.toFixed(2) + '°, ' + latlng.lng.toFixed(2) + '°';
                    }}
                    
                    selectedCoords = coords;
                    coordsDiv.style.display = 'block';
                    coordsDiv.innerHTML = 
                        '🟥 West: ' + coords.west.toFixed(6) + '°<br>' +
                        '🟩 South: ' + coords.south.toFixed(6) + '°<br>' +
                        '🟥 East: ' + coords.east.toFixed(6) + '°<br>' +
                        '🟩 North: ' + coords.north.toFixed(6) + '°';
                    
                    // Save to file
                    saveCoordinates(coords);
                    
                    // Also save to localStorage
                    localStorage.setItem('bbox_coords', JSON.stringify(coords));
                }});
                
                map.on('draw:deleted', function(e) {{
                    selectedCoords = null;
                    coordsDiv.style.display = 'none';
                    infoDiv.innerHTML = '✏️ Draw a rectangle on the map to select your AOI';
                    infoDiv.className = '';
                    statusDiv.innerHTML = '🔄 Selection cleared';
                    localStorage.removeItem('bbox_coords');
                }});
                
                // Function to get coordinates
                window.getCoordinates = function() {{
                    return selectedCoords || JSON.parse(localStorage.getItem('bbox_coords'));
                }};
                
                console.log('Map loaded. Draw a rectangle to select your AOI.');
                console.log('Coordinates will be auto-saved when you draw.');
            </script>
        </body>
        </html>
        """
        
        temp_file = tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8')
        temp_file.write(html_content)
        temp_file.close()
        
        return temp_file.name
        
    def start_monitoring(self):
        """Start monitoring for coordinate changes"""
        if self.monitor_running:
            return
            
        self.monitor_running = True
        
        # Start a simple HTTP server to receive coordinates
        self.start_http_server()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_coords, daemon=True)
        self.monitor_thread.start()
        
    def start_http_server(self):
        """Start a simple HTTP server to receive coordinates"""
        try:
            # Try to start server on port 8765
            handler = self.create_handler()
            self.http_server = socketserver.TCPServer(('localhost', 8765), handler)
            server_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            server_thread.start()
        except Exception as e:
            print(f"Could not start HTTP server: {e}")
            
    def create_handler(self):
        """Create a custom HTTP request handler"""
        
        class CoordHandler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.parent = kwargs.pop('parent', None)
                super().__init__(*args, **kwargs)
                
            def do_POST(self):
                if self.path == '/save':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    try:
                        data = json.loads(post_data.decode('utf-8'))
                        coords = data.get('coords')
                        if coords:
                            # Save to file
                            with open(self.parent.coords_file.name, 'w') as f:
                                json.dump({"coords": coords}, f)
                            self.parent.bounding_box = (
                                coords['west'],
                                coords['south'],
                                coords['east'],
                                coords['north']
                            )
                            # Update UI
                            self.parent.parent.after(0, self.parent.update_ui)
                    except Exception as e:
                        print(f"Error processing coordinates: {e}")
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
                    
            def log_message(self, format, *args):
                pass  # Suppress logging
                
        # Create a handler with parent reference
        class Handler(CoordHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, parent=self.parent, **kwargs)
                
        return Handler
        
    def monitor_coords(self):
        """Monitor the coordinates file for changes"""
        last_modified = 0
        
        while self.monitor_running:
            try:
                if os.path.exists(self.coords_file.name):
                    stat = os.stat(self.coords_file.name)
                    if stat.st_mtime > last_modified:
                        last_modified = stat.st_mtime
                        with open(self.coords_file.name, 'r') as f:
                            data = json.load(f)
                            coords = data.get('coords')
                            if coords:
                                self.bounding_box = (
                                    coords['west'],
                                    coords['south'],
                                    coords['east'],
                                    coords['north']
                                )
                                self.parent.after(0, self.update_ui)
            except Exception as e:
                pass
            time.sleep(0.5)
            
    def update_ui(self):
        """Update the UI with new coordinates"""
        if self.bounding_box:
            self.callback(self.bounding_box)
            
    def get_coordinates(self):
        """Get the current coordinates"""
        return self.bounding_box
        
    def close(self):
        """Close the map and stop monitoring"""
        self.monitor_running = False
        if hasattr(self, 'http_server'):
            self.http_server.shutdown()
        if self.map_file and os.path.exists(self.map_file):
            try:
                os.unlink(self.map_file)
            except:
                pass

# =============================================================================
# MAIN APPLICATION CLASS
# =============================================================================

class GiovanniGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("NASA Giovanni Area-Averaged Time Series (with OSM Map Integration)")
        self.root.geometry("1400x950")
        self.root.minsize(1200, 850)
        
        try:
            self.root.iconbitmap(default='nasa_icon.ico')
        except:
            pass

        # Variables
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.product = tk.StringVar()
        self.variable = tk.StringVar()
        self.start_date = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
        self.start_time = tk.StringVar(value="00:00")
        self.end_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.end_time = tk.StringVar(value="23:59")
        self.roi_file = tk.StringVar()
        self.grid_resolution = tk.StringVar(value="0.1")
        self.cosine_weight = tk.BooleanVar(value=True)
        self.coverage_weight = tk.BooleanVar(value=True)
        self.output_folder = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready")
        self.progress_value = tk.DoubleVar(value=0)
        
        self.roi_source = tk.StringVar(value="file")
        self.analysis_mode = tk.StringVar(value="area_average")
        self.single_point_lat = tk.StringVar(value="")
        self.single_point_lon = tk.StringVar(value="")
        self.create_spatial_maps = tk.BooleanVar(value=True)

        self.roi_geometry = None
        self.grid_points = []
        self.grid_weights = None
        self.processing = False
        self.osm_selector = None

        self.create_widgets()
        self.update_variables()

    # =========================================================================
    # GUI CREATION
    # =========================================================================

    def create_widgets(self):
        main = ttk.Frame(self.root, padding="5")
        main.pack(fill="both", expand=True)

        # Title
        title_frame = tk.Frame(main, bg='#0a1628')
        title_frame.pack(fill='x', pady=(0, 5))
        
        title_label = tk.Label(
            title_frame,
            text="NASA GIOVANNI AREA-AVERAGED TIME SERIES",
            font=("Arial", 14, "bold"),
            fg='#fc3d21',
            bg='#0a1628'
        )
        title_label.pack(side=tk.LEFT)
        
        subtitle_label = tk.Label(
            title_frame,
            text="🌍 with OSM Map Integration",
            font=("Arial", 11),
            fg='#87CEEB',
            bg='#0a1628'
        )
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0))

        # Main content - split into left and right panels
        content_frame = ttk.Frame(main)
        content_frame.pack(fill="both", expand=True)

        # Left panel - Input & Configuration
        left_panel = ttk.Frame(content_frame, width=450)
        left_panel.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 5))
        
        # Right panel - Map and Log
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.RIGHT, fill="both", expand=True, padx=(5, 0))

        # ============================================================
        # LEFT PANEL: INPUT & CONFIGURATION
        # ============================================================
        
        # Create a canvas with scrollbar for left panel
        left_canvas = tk.Canvas(left_panel, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_panel, orient="vertical", command=left_canvas.yview)
        left_scrollable = ttk.Frame(left_canvas)
        
        left_scrollable.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )
        
        left_canvas.create_window((0, 0), window=left_scrollable, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="right", fill="y")

        # ---- EARTHDATA LOGIN ----
        login_frame = ttk.LabelFrame(left_scrollable, text="Earthdata Login", padding="8")
        login_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(login_frame, textvariable=self.username, width=25).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(login_frame, textvariable=self.password, show="*", width=25).grid(row=1, column=1, padx=5, pady=2)

        ttk.Button(login_frame, text="Test Login", command=self.test_login).grid(row=0, column=2, rowspan=2, padx=10)

        # ---- PRODUCT SELECTION ----
        product_frame = ttk.LabelFrame(left_scrollable, text="Dataset / Product", padding="8")
        product_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(product_frame, text="Product:").grid(row=0, column=0, sticky="w", padx=5)
        self.product_combo = ttk.Combobox(
            product_frame,
            textvariable=self.product,
            values=list(PRODUCTS.keys()),
            state="readonly",
            width=35
        )
        self.product_combo.grid(row=0, column=1, padx=5, pady=2)
        self.product_combo.bind("<<ComboboxSelected>>", lambda e: self.update_variables())

        ttk.Label(product_frame, text="Variable:").grid(row=1, column=0, sticky="w", padx=5)
        self.variable_combo = ttk.Combobox(
            product_frame,
            textvariable=self.variable,
            state="readonly",
            width=35
        )
        self.variable_combo.grid(row=1, column=1, padx=5, pady=2)

        # ---- DATE RANGE ----
        date_frame = ttk.LabelFrame(left_scrollable, text="Date Range (UTC)", padding="8")
        date_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(date_frame, text="Start Date:").grid(row=0, column=0, padx=2)
        ttk.Entry(date_frame, textvariable=self.start_date, width=12).grid(row=0, column=1)
        ttk.Label(date_frame, text="Time:").grid(row=0, column=2)
        ttk.Entry(date_frame, textvariable=self.start_time, width=8).grid(row=0, column=3)

        ttk.Label(date_frame, text="End Date:").grid(row=0, column=4, padx=2)
        ttk.Entry(date_frame, textvariable=self.end_date, width=12).grid(row=0, column=5)
        ttk.Label(date_frame, text="Time:").grid(row=0, column=6)
        ttk.Entry(date_frame, textvariable=self.end_time, width=8).grid(row=0, column=7)

        # ---- ANALYSIS MODE ----
        mode_frame = ttk.LabelFrame(left_scrollable, text="Analysis Mode", padding="8")
        mode_frame.pack(fill="x", pady=(0, 5))

        ttk.Radiobutton(
            mode_frame,
            text="Area Average (Grid-based)",
            variable=self.analysis_mode,
            value="area_average",
            command=self.toggle_mode
        ).grid(row=0, column=0, padx=5, sticky="w")

        ttk.Radiobutton(
            mode_frame,
            text="Single Point",
            variable=self.analysis_mode,
            value="single_point",
            command=self.toggle_mode
        ).grid(row=0, column=1, padx=5, sticky="w")

        self.point_frame = ttk.Frame(mode_frame)
        self.point_frame.grid(row=1, column=0, columnspan=2, pady=2)

        ttk.Label(self.point_frame, text="Latitude:").pack(side=tk.LEFT, padx=2)
        ttk.Entry(self.point_frame, textvariable=self.single_point_lat, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Label(self.point_frame, text="Longitude:").pack(side=tk.LEFT, padx=2)
        ttk.Entry(self.point_frame, textvariable=self.single_point_lon, width=10).pack(side=tk.LEFT, padx=2)

        self.point_frame.pack_forget()

        # ---- ROI SELECTION ----
        roi_frame = ttk.LabelFrame(left_scrollable, text="Region of Interest", padding="8")
        roi_frame.pack(fill="x", pady=(0, 5))

        source_frame = ttk.Frame(roi_frame)
        source_frame.pack(fill="x", pady=2)

        ttk.Radiobutton(
            source_frame,
            text="📁 Upload KML/KMZ",
            variable=self.roi_source,
            value="file",
            command=self.toggle_roi_source
        ).pack(side=tk.LEFT, padx=5)

        ttk.Radiobutton(
            source_frame,
            text="🗺️ Select from OpenStreetMap",
            variable=self.roi_source,
            value="osm",
            command=self.toggle_roi_source
        ).pack(side=tk.LEFT, padx=5)

        self.file_frame = ttk.Frame(roi_frame)
        self.file_frame.pack(fill="x", pady=2)

        ttk.Button(self.file_frame, text="Upload KML/KMZ", command=self.select_roi).pack(side=tk.LEFT, padx=2)
        ttk.Entry(self.file_frame, textvariable=self.roi_file, width=35, state="readonly").pack(side=tk.LEFT, padx=2, fill="x", expand=True)
        ttk.Button(self.file_frame, text="Read ROI", command=self.read_roi).pack(side=tk.LEFT, padx=2)

        self.osm_frame = ttk.Frame(roi_frame)
        self.osm_frame.pack(fill="x", pady=2)
        
        ttk.Button(
            self.osm_frame,
            text="🗺️ Open OSM Map",
            command=self.open_osm_map
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(self.osm_frame, text="Status:").pack(side=tk.LEFT, padx=(10, 5))
        
        self.osm_status_label = tk.Label(
            self.osm_frame,
            text="Not selected",
            font=("Arial", 9),
            fg='#888888'
        )
        self.osm_status_label.pack(side=tk.LEFT)

        self.osm_frame.pack_forget()

        # ROI info
        self.roi_info = scrolledtext.ScrolledText(roi_frame, height=4, width=50, font=("Courier", 9))
        self.roi_info.pack(fill="x", pady=5)

        # ---- PROCESSING OPTIONS ----
        option_frame = ttk.LabelFrame(left_scrollable, text="Processing Options", padding="8")
        option_frame.pack(fill="x", pady=(0, 5))

        ttk.Label(option_frame, text="Grid Resolution:").grid(row=0, column=0, padx=2)
        ttk.Entry(option_frame, textvariable=self.grid_resolution, width=8).grid(row=0, column=1)

        ttk.Checkbutton(
            option_frame,
            text="Cosine Weighting",
            variable=self.cosine_weight
        ).grid(row=0, column=2, padx=5)

        ttk.Checkbutton(
            option_frame,
            text="Coverage Weighting",
            variable=self.coverage_weight
        ).grid(row=0, column=3, padx=5)

        ttk.Checkbutton(
            option_frame,
            text="Daily Spatial Maps",
            variable=self.create_spatial_maps
        ).grid(row=1, column=0, columnspan=4, padx=5)

        # ---- OUTPUT FOLDER ----
        output_frame = ttk.LabelFrame(left_scrollable, text="Output Folder", padding="8")
        output_frame.pack(fill="x", pady=(0, 5))

        ttk.Button(output_frame, text="Select Folder", command=self.select_output).pack(side=tk.LEFT, padx=2)
        ttk.Entry(output_frame, textvariable=self.output_folder, width=40, state="readonly").pack(side=tk.LEFT, padx=2, fill="x", expand=True)

        # ---- RUN BUTTON ----
        run_frame = ttk.Frame(left_scrollable)
        run_frame.pack(fill="x", pady=5)

        self.run_button = ttk.Button(run_frame, text="🚀 SUBMIT / RUN ANALYSIS", command=self.start_processing)
        self.run_button.pack(fill="x", pady=2, ipady=5)

        self.progress_bar = ttk.Progressbar(run_frame, variable=self.progress_value, maximum=100)
        self.progress_bar.pack(fill="x", pady=2)

        ttk.Label(run_frame, textvariable=self.status_text).pack(pady=2)

        # ============================================================
        # RIGHT PANEL: RESULTS & LOG
        # ============================================================
        
        # Results summary
        results_frame = ttk.LabelFrame(right_panel, text="📊 Results Summary", padding="5")
        results_frame.pack(fill="x", pady=(0, 5))
        
        self.summary_text = scrolledtext.ScrolledText(results_frame, height=4, font=("Courier", 9))
        self.summary_text.pack(fill="x")
        self.summary_text.config(state=tk.DISABLED)
        
        files_frame = ttk.Frame(results_frame)
        files_frame.pack(fill="x", pady=2)
        
        self.files_listbox = tk.Listbox(files_frame, height=3)
        self.files_listbox.pack(side=tk.LEFT, fill="both", expand=True)
        
        btn_frame2 = ttk.Frame(files_frame)
        btn_frame2.pack(side=tk.RIGHT, padx=2)
        
        ttk.Button(btn_frame2, text="📂 Open", command=self.open_output_folder, width=6).pack(pady=1)
        ttk.Button(btn_frame2, text="🗑️ Clear", command=self.clear_results, width=6).pack(pady=1)

        # Log frame
        log_frame = ttk.LabelFrame(right_panel, text="📋 Processing Log", padding="5")
        log_frame.pack(fill="both", expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, font=("Courier", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state=tk.DISABLED)

    # =========================================================================
    # OSM MAP FUNCTIONS
    # =========================================================================
    
    def toggle_roi_source(self):
        """Toggle between file upload and OSM selection"""
        if self.roi_source.get() == "file":
            self.file_frame.pack(fill="x", pady=2)
            self.osm_frame.pack_forget()
        else:
            self.file_frame.pack_forget()
            self.osm_frame.pack(fill="x", pady=2)
            self.roi_file.set("")
            
    def open_osm_map(self):
        """Open the OSM map in browser"""
        if self.osm_selector is None:
            self.osm_selector = OSMMapSelector(self.root, self.osm_selection_callback)
        
        # Get current bounds if we have them
        initial_bounds = None
        if self.roi_geometry:
            initial_bounds = self.roi_geometry.bounds
        
        # Open the map
        self.osm_selector.open_map(initial_bounds)
        self.osm_status_label.config(text="Map opened in browser - draw rectangle", fg='#0066cc')
        self.log_message("🗺️ OSM map opened in browser. Draw a rectangle to select your AOI.")
        
        messagebox.showinfo(
            "OSM Map",
            "🌍 The map has opened in your web browser.\n\n"
            "1. Use the rectangle tool (🟦) to draw your AOI\n"
            "2. Coordinates will be auto-detected\n"
            "3. Return to this window when done"
        )
        
    def osm_selection_callback(self, bounds):
        """Callback when OSM selection is made"""
        minx, miny, maxx, maxy = bounds
        
        self.osm_status_label.config(
            text=f"✓ Selected: {minx:.2f}° to {maxx:.2f}°, {miny:.2f}° to {maxy:.2f}°",
            fg='#006600'
        )
        
        self.roi_geometry = box(minx, miny, maxx, maxy)
        
        centroid = self.roi_geometry.centroid
        area = self.roi_geometry.area
        
        self.roi_info.delete("1.0", "end")
        self.roi_info.insert("end",
            f"West  : {minx:.6f}\n"
            f"South : {miny:.6f}\n"
            f"East  : {maxx:.6f}\n"
            f"North : {maxy:.6f}\n\n"
            f"Centroid: ({centroid.x:.4f}, {centroid.y:.4f})\n"
            f"Area: {area:.4f} deg²\n"
            f"Source: OpenStreetMap\n"
        )
        
        self.log_message(f"✅ ROI selected from OSM: {minx:.4f}, {miny:.4f}, {maxx:.4f}, {maxy:.4f}")
        self.update_status(f"✅ ROI selected from OSM: {minx:.2f}°E to {maxx:.2f}°E", 0)

    # =========================================================================
    # MODE TOGGLE
    # =========================================================================

    def toggle_mode(self):
        if self.analysis_mode.get() == "single_point":
            self.point_frame.pack(side=tk.LEFT, padx=10)
            self.roi_file.set("")
            self.roi_info.delete("1.0", "end")
            self.roi_geometry = None
        else:
            self.point_frame.pack_forget()

    # =========================================================================
    # LOGGING METHODS
    # =========================================================================

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def update_status(self, message, progress=None):
        self.status_text.set(message)
        if progress is not None:
            self.progress_value.set(progress)
        self.root.update_idletasks()

    def update_summary(self, text):
        self.summary_text.config(state=tk.NORMAL)
        self.summary_text.delete(1.0, tk.END)
        self.summary_text.insert(tk.END, text)
        self.summary_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def add_file_to_list(self, file_path):
        self.files_listbox.insert(tk.END, os.path.basename(file_path))

    def clear_results(self):
        self.files_listbox.delete(0, tk.END)
        self.update_summary("")
        self.log_message("Results cleared")

    def open_output_folder(self):
        output_dir = self.output_folder.get()
        if output_dir and os.path.exists(output_dir):
            if os.name == 'nt':
                os.startfile(output_dir)
            elif os.name == 'posix':
                os.system(f'open "{output_dir}"' if sys.platform == 'darwin' else f'xdg-open "{output_dir}"')
        else:
            messagebox.showwarning("Warning", "Output directory not found or not set")

    # =========================================================================
    # PRODUCT VARIABLES
    # =========================================================================

    def update_variables(self):
        product = self.product.get()
        if product not in PRODUCTS:
            return
        variables = list(PRODUCTS[product]["variables"].keys())
        self.variable_combo["values"] = variables
        if variables:
            self.variable.set(variables[0])

    # =========================================================================
    # EARTHDATA LOGIN
    # =========================================================================

    def test_login(self):
        username = self.username.get().strip()
        password = self.password.get()

        if not username or not password:
            messagebox.showerror("Login Error", "Enter Earthdata username and password.")
            return

        try:
            os.environ["EARTHDATA_USERNAME"] = username
            os.environ["EARTHDATA_PASSWORD"] = password

            auth = earthaccess.login(strategy="environment", persist=False)
            session = auth.get_session()
            response = session.get("https://api.giovanni.earthdata.nasa.gov", timeout=30)

            self.log_message("✅ Earthdata authentication successful.")
            messagebox.showinfo("Success", "NASA Earthdata authentication successful.")

        except Exception as e:
            self.log_message(f"❌ Earthdata login failed: {str(e)}")
            messagebox.showerror("Earthdata Login Failed", str(e))

        finally:
            os.environ.pop("EARTHDATA_USERNAME", None)
            os.environ.pop("EARTHDATA_PASSWORD", None)

    # =========================================================================
    # ROI SELECTION & EXTRACTION
    # =========================================================================

    def select_roi(self):
        filename = filedialog.askopenfilename(
            title="Select KML or KMZ",
            filetypes=[("KML/KMZ", "*.kml *.kmz"), ("KML", "*.kml"), ("KMZ", "*.kmz")]
        )
        if filename:
            self.roi_file.set(filename)
            self.roi_source.set("file")
            self.toggle_roi_source()

    def extract_kmz(self, filename):
        extract_folder = Path(filename).with_suffix("")
        extract_folder = Path(str(extract_folder) + "_extracted")
        extract_folder.mkdir(exist_ok=True)

        with zipfile.ZipFile(filename, "r") as kmz:
            kmz.extractall(extract_folder)

        for root, dirs, files in os.walk(extract_folder):
            for file in files:
                if file.lower().endswith(".kml"):
                    return os.path.join(root, file)

        raise FileNotFoundError("No KML file found inside KMZ.")

    def read_kml(self, filename):
        tree = ET.parse(filename)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        geometries = []

        for coordinates in root.findall(".//kml:coordinates", ns):
            if coordinates.text is None:
                continue

            points = []
            for coord in coordinates.text.strip().split():
                parts = coord.split(",")
                if len(parts) < 2:
                    continue
                lon = float(parts[0])
                lat = float(parts[1])
                points.append((lon, lat))

            if len(points) >= 3:
                if points[0] != points[-1]:
                    points.append(points[0])
                polygon = Polygon(points)
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)
                if not polygon.is_empty:
                    geometries.append(polygon)

        if not geometries:
            raise ValueError("No polygon geometry found.")

        return unary_union(geometries)

    def read_roi(self):
        filename = self.roi_file.get()
        if not filename:
            messagebox.showerror("ROI Error", "Select a KML or KMZ file.")
            return

        try:
            if filename.lower().endswith(".kmz"):
                filename = self.extract_kmz(filename)

            self.roi_geometry = self.read_kml(filename)

            minx, miny, maxx, maxy = self.roi_geometry.bounds
            centroid = self.roi_geometry.centroid
            area = self.roi_geometry.area

            self.roi_info.delete("1.0", "end")
            self.roi_info.insert("end",
                f"West  : {minx:.6f}\n"
                f"South : {miny:.6f}\n"
                f"East  : {maxx:.6f}\n"
                f"North : {maxy:.6f}\n\n"
                f"Centroid: ({centroid.x:.4f}, {centroid.y:.4f})\n"
                f"Area: {area:.4f} deg²\n"
                f"Source: KML/KMZ File\n"
            )

            self.log_message("✅ ROI successfully extracted from KML/KMZ.")
            
            if self.roi_source.get() == "osm":
                self.roi_source.set("file")
                self.toggle_roi_source()

        except Exception as e:
            messagebox.showerror("ROI Error", str(e))

    # =========================================================================
    # GRID GENERATION
    # =========================================================================

    def generate_grid(self):
        resolution = float(self.grid_resolution.get())
        minx, miny, maxx, maxy = self.roi_geometry.bounds

        points = []
        x = math.floor(minx / resolution) * resolution + resolution / 2

        while x <= maxx:
            y = math.floor(miny / resolution) * resolution + resolution / 2
            while y <= maxy:
                point = Point(x, y)
                cell = box(x - resolution/2, y - resolution/2, x + resolution/2, y + resolution/2)

                if self.roi_geometry.intersects(cell):
                    points.append({
                        "latitude": y,
                        "longitude": x,
                        "cell": cell
                    })
                y += resolution
            x += resolution

        return points

    def calculate_weights(self, points):
        weights = []

        for p in points:
            cell = p["cell"]
            intersection = cell.intersection(self.roi_geometry).area

            if self.coverage_weight.get():
                coverage = intersection / cell.area
            else:
                coverage = 1.0

            if self.cosine_weight.get():
                lat_weight = math.cos(math.radians(p["latitude"]))
            else:
                lat_weight = 1.0

            weights.append(coverage * lat_weight)

        weights = np.array(weights)
        if weights.sum() == 0:
            raise ValueError("No valid spatial weights.")

        return weights / weights.sum()

    # =========================================================================
    # GIOVANNI QUERY
    # =========================================================================

    def query_point(self, session, latitude, longitude, variable_id, start, end):
        params = {
            "data": variable_id,
            "location": f"[{latitude:.4f},{longitude:.4f}]",
            "time": f"{start}/{end}"
        }

        response = session.get(GIOVANNI_API, params=params, timeout=120)
        response.raise_for_status()
        return response.text

    def parse_response(self, text):
        lines = text.splitlines()

        data_start = None
        for i, line in enumerate(lines):
            if "timestamp" in line.lower() and "data" in line.lower():
                data_start = i
                break

        if data_start is None:
            raise ValueError("Giovanni data table not found.")

        records = []
        for line in lines[data_start + 1:]:
            line = line.strip()
            if not line:
                continue

            parts = re.split(r",|\t", line)
            if len(parts) < 2:
                continue

            timestamp = parts[0].strip()
            value = parts[1].strip()

            try:
                value = float(value)
            except:
                continue

            if value <= -9990:
                continue

            records.append((timestamp, value))

        if not records:
            raise ValueError("No valid observations returned.")

        df = pd.DataFrame(records, columns=["Datetime", "Value"])
        df["Datetime"] = pd.to_datetime(df["Datetime"], errors="coerce")
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
        df = df.dropna()

        return df

    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================

    def start_processing(self):
        if self.processing:
            return

        if not self.username.get() or not self.password.get():
            messagebox.showerror("Error", "Earthdata username and password required.")
            return

        mode = self.analysis_mode.get()
        
        if mode == "area_average":
            if self.roi_source.get() == "file":
                if not self.roi_file.get():
                    messagebox.showerror("Error", "KML/KMZ file required for area average mode.")
                    return
                if self.roi_geometry is None:
                    self.read_roi()
                    if self.roi_geometry is None:
                        return
            else:
                if self.roi_geometry is None:
                    messagebox.showerror("Error", "Please select an area using the OpenStreetMap selector.")
                    return
        else:
            try:
                lat = float(self.single_point_lat.get())
                lon = float(self.single_point_lon.get())
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    raise ValueError("Invalid coordinates")
            except:
                messagebox.showerror("Error", "Enter valid latitude (-90 to 90) and longitude (-180 to 180).")
                return

        if not self.output_folder.get():
            folder = filedialog.askdirectory(title="Select output folder")
            if folder:
                self.output_folder.set(folder)
            else:
                return

        self.processing = True
        self.run_button.config(state=tk.DISABLED)
        self.progress_value.set(0)
        self.clear_results()

        thread = threading.Thread(target=self.process, daemon=True)
        thread.start()

    def process(self):
        try:
            self.log_message("=" * 70)
            self.log_message("🚀 STARTING PROCESSING")
            self.log_message("=" * 70)

            start = f"{self.start_date.get()}T{self.start_time.get()}:00"
            end = f"{self.end_date.get()}T{self.end_time.get()}:00"

            product = self.product.get()
            variable_name = self.variable.get()
            variable_id = PRODUCTS[product]["variables"][variable_name]

            output = self.output_folder.get()
            os.makedirs(output, exist_ok=True)

            mode = self.analysis_mode.get()

            self.update_status("🔐 Authenticating with Earthdata...", 5)
            self.log_message("🔐 Authenticating with Earthdata...")

            os.environ["EARTHDATA_USERNAME"] = self.username.get()
            os.environ["EARTHDATA_PASSWORD"] = self.password.get()

            auth = earthaccess.login(strategy="environment", persist=False)
            session = auth.get_session()

            os.environ.pop("EARTHDATA_USERNAME", None)
            os.environ.pop("EARTHDATA_PASSWORD", None)

            is_precip = PRODUCTS[product].get("precipitation", False)

            if mode == "single_point":
                self.log_message("📍 Processing single point...")
                lat = float(self.single_point_lat.get())
                lon = float(self.single_point_lon.get())
                
                self.update_status(f"📍 Querying point ({lat:.4f}, {lon:.4f})...", 20)
                self.log_message(f"📍 Querying point: Lat={lat:.4f}, Lon={lon:.4f}")
                
                data = self.query_point(session, lat, lon, variable_id, start, end)
                df = self.parse_response(data)
                
                self.roi_geometry = Point(lon, lat)
                
                halfhourly = df.set_index("Datetime").resample("30min").mean().reset_index()
                halfhourly.columns = ["Datetime", "Area_Average"]
                
                if is_precip:
                    hourly = df.set_index("Datetime").resample("1h").sum().reset_index()
                    daily = df.set_index("Datetime").resample("1D").sum().reset_index()
                else:
                    hourly = df.set_index("Datetime").resample("1h").mean().reset_index()
                    daily = df.set_index("Datetime").resample("1D").mean().reset_index()
                
                hourly.columns = ["Datetime", "Area_Average"]
                daily.columns = ["Datetime", "Area_Average"]
                
                df.to_csv(os.path.join(output, "Single_Point_Data.csv"), index=False)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Single_Point_Data.csv")))
                
            else:
                self.update_status("🗺️ Generating spatial grid...", 10)
                self.log_message("🗺️ Generating spatial grid...")

                points = self.generate_grid()
                weights = self.calculate_weights(points)
                self.grid_points = points
                self.grid_weights = weights

                self.log_message(f"📊 Grid cells: {len(points)}")

                self.update_status("📡 Querying Giovanni API...", 15)
                self.log_message("📡 Starting Giovanni queries...")

                all_data = []
                total = len(points)
                completed = 0

                def worker(index, p):
                    df = self.query_point(
                        session,
                        p["latitude"],
                        p["longitude"],
                        variable_id,
                        start,
                        end
                    )
                    df = self.parse_response(df)
                    df["Grid_ID"] = index
                    df["Latitude"] = p["latitude"]
                    df["Longitude"] = p["longitude"]
                    df["Weight"] = weights[index - 1]
                    return df

                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {
                        executor.submit(worker, i, p): i
                        for i, p in enumerate(points, start=1)
                    }

                    for future in as_completed(futures):
                        grid_id = futures[future]
                        try:
                            df = future.result()
                            all_data.append(df)
                            self.log_message(f"✅ Grid {grid_id}/{total} completed.")
                        except Exception as e:
                            self.log_message(f"❌ Grid {grid_id} failed: {e}")

                        completed += 1
                        percent = 15 + (completed / total) * 75
                        self.update_status(f"📊 Processed {completed}/{total} grid cells", percent)

                if not all_data:
                    raise RuntimeError("No Giovanni data returned.")

                raw = pd.concat(all_data, ignore_index=True)

                self.update_status("📊 Calculating area average...", 90)
                self.log_message("📊 Calculating area average...")

                def average_group(group):
                    values = group["Value"].values
                    w = group["Weight"].values
                    valid = np.isfinite(values)
                    values = values[valid]
                    w = w[valid]
                    if len(values) == 0:
                        return np.nan
                    return np.average(values, weights=w)

                area = (
                    raw
                    .groupby("Datetime")
                    .apply(average_group, include_groups=False)
                    .reset_index(name="Area_Average")
                )

                halfhourly = (
                    area
                    .set_index("Datetime")
                    .resample("30min")
                    .mean()
                    .reset_index()
                )

                if is_precip:
                    hourly = (
                        area
                        .set_index("Datetime")
                        .resample("1h")
                        .sum()
                        .reset_index()
                    )
                    daily = (
                        area
                        .set_index("Datetime")
                        .resample("1D")
                        .sum()
                        .reset_index()
                    )
                else:
                    hourly = (
                        area
                        .set_index("Datetime")
                        .resample("1h")
                        .mean()
                        .reset_index()
                    )
                    daily = (
                        area
                        .set_index("Datetime")
                        .resample("1D")
                        .mean()
                        .reset_index()
                    )

                self.update_status("💾 Saving output files...", 92)
                self.log_message("💾 Saving output files...")

                halfhourly.to_csv(os.path.join(output, "HalfHourly_Area_Average.csv"), index=False)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "HalfHourly_Area_Average.csv")))

                hourly.to_csv(os.path.join(output, "Hourly_Area_Average.csv"), index=False)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Hourly_Area_Average.csv")))

                daily.to_csv(os.path.join(output, "Daily_Area_Average.csv"), index=False)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Daily_Area_Average.csv")))

                raw.to_csv(os.path.join(output, "Raw_Grid_TimeSeries.csv"), index=False)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Raw_Grid_TimeSeries.csv")))

                grid_df = pd.DataFrame({
                    "Grid_ID": range(1, len(points) + 1),
                    "Latitude": [p["latitude"] for p in points],
                    "Longitude": [p["longitude"] for p in points],
                    "Weight": weights
                })
                grid_df.to_csv(os.path.join(output, "Grid_Points_Weights.csv"), index=False)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Grid_Points_Weights.csv")))

            # ---- CREATE PLOTS ----
            self.update_status("📈 Creating plots...", 94)
            self.log_message("📈 Creating plots...")

            plt.rcParams["font.family"] = "Times New Roman"
            
            date_range_str = f"{halfhourly['Datetime'].min().strftime('%d %B %Y')} to {halfhourly['Datetime'].max().strftime('%d %B %Y')}"

            self.create_plot(
                halfhourly, 
                f"{'Single Point' if mode == 'single_point' else 'Area-Averaged'} Half-hourly Time Series",
                os.path.join(output, "HalfHourly_Area_Average.png"),
                date_range_str,
                mode
            )
            self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "HalfHourly_Area_Average.png")))

            self.create_plot(
                hourly, 
                f"{'Single Point' if mode == 'single_point' else 'Area-Averaged'} Hourly Time Series",
                os.path.join(output, "Hourly_Area_Average.png"),
                date_range_str,
                mode
            )
            self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Hourly_Area_Average.png")))

            self.create_plot(
                daily, 
                f"{'Single Point' if mode == 'single_point' else 'Area-Averaged'} Daily Time Series",
                os.path.join(output, "Daily_Area_Average.png"),
                date_range_str,
                mode
            )
            self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Daily_Area_Average.png")))

            if mode == "area_average":
                self.create_roi_plot(points, output)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "ROI_and_Grid.png")))
            else:
                self.create_point_plot(output)
                self.root.after(0, lambda: self.add_file_to_list(os.path.join(output, "Point_Location.png")))

            if mode == "area_average" and self.create_spatial_maps.get():
                self.update_status("🗺️ Creating daily spatial maps...", 96)
                self.log_message("🗺️ Creating daily spatial maps...")
                
                spatial_dir = os.path.join(output, "Daily_Spatial_Maps")
                os.makedirs(spatial_dir, exist_ok=True)
                
                self.create_daily_spatial_maps(raw, points, spatial_dir)
                self.log_message(f"✅ Daily spatial maps saved to: {spatial_dir}")
                self.root.after(0, lambda: self.add_file_to_list(spatial_dir))

            # ---- EXCEL OUTPUT ----
            self.update_status("📊 Creating Excel output...", 97)
            self.log_message("📊 Creating Excel output...")

            excel_file = os.path.join(output, "Giovanni_Area_TimeSeries.xlsx")
            with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
                halfhourly.to_excel(writer, sheet_name="HalfHourly", index=False)
                hourly.to_excel(writer, sheet_name="Hourly", index=False)
                daily.to_excel(writer, sheet_name="Daily", index=False)
                
                if mode == "area_average":
                    grid_df.to_excel(writer, sheet_name="Grid_Weights", index=False)
                    raw.to_excel(writer, sheet_name="Raw_Grid_Data", index=False)

            self.root.after(0, lambda: self.add_file_to_list(excel_file))

            # ---- STATISTICS ----
            self.update_status("📊 Generating statistics...", 98)
            self.log_message("📊 Generating statistics...")

            stats_file = os.path.join(output, "Statistics.txt")
            values = daily["Area_Average"].dropna()

            roi_source = "KML/KMZ File" if self.roi_source.get() == "file" else "OpenStreetMap Selection"

            with open(stats_file, "w", encoding="utf-8") as f:
                f.write("NASA GIOVANNI AREA-AVERAGED TIME SERIES\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"Mode: {'Single Point' if mode == 'single_point' else 'Area Average'}\n")
                if mode == "single_point":
                    f.write(f"Latitude: {self.single_point_lat.get()}\n")
                    f.write(f"Longitude: {self.single_point_lon.get()}\n")
                else:
                    f.write(f"ROI Source: {roi_source}\n")
                    if self.roi_source.get() == "file":
                        f.write(f"KML/KMZ File: {self.roi_file.get()}\n")
                f.write(f"Product: {product}\n")
                f.write(f"Variable: {variable_name}\n")
                f.write(f"Date Range: {date_range_str}\n\n")
                f.write(f"Number of observations: {len(values)}\n")
                f.write(f"Minimum: {values.min():.4f}\n")
                f.write(f"Maximum: {values.max():.4f}\n")
                f.write(f"Mean: {values.mean():.4f}\n")
                f.write(f"Median: {values.median():.4f}\n")
                f.write(f"Standard deviation: {values.std():.4f}\n")
                f.write(f"Total: {values.sum():.4f}\n")

            self.root.after(0, lambda: self.add_file_to_list(stats_file))

            self.update_status("✅ PROCESS COMPLETED", 100)

            summary_parts = []
            summary_parts.append("=" * 70)
            summary_parts.append("✅ PROCESSING COMPLETED SUCCESSFULLY")
            summary_parts.append("=" * 70)
            summary_parts.append("")
            summary_parts.append(f"Mode: {'Single Point' if mode == 'single_point' else 'Area Average'}")
            if mode == "single_point":
                summary_parts.append(f"Location: ({self.single_point_lat.get()}, {self.single_point_lon.get()})")
            else:
                summary_parts.append(f"ROI Source: {roi_source}")
            summary_parts.append(f"Product: {product}")
            summary_parts.append(f"Variable: {variable_name}")
            summary_parts.append(f"Date Range: {date_range_str}")
            summary_parts.append("")
            summary_parts.append(f"Half-hour records: {len(halfhourly)}")
            summary_parts.append(f"Hourly records: {len(hourly)}")
            summary_parts.append(f"Daily records: {len(daily)}")
            summary_parts.append("")
            summary_parts.append(f"Output folder: {output}")
            summary_parts.append("=" * 70)
            
            summary = "\n".join(summary_parts)

            self.root.after(0, lambda: self.update_summary(summary))

            self.log_message("=" * 70)
            self.log_message("✅ PROCESS COMPLETED SUCCESSFULLY")
            self.log_message(f"📁 Output folder: {output}")
            self.log_message("=" * 70)

            self.root.after(0, lambda: messagebox.showinfo(
                "Completed",
                "✅ Processing completed successfully!\n\n"
                f"📁 Output folder:\n{output}"
            ))

        except Exception as e:
            traceback_text = traceback.format_exc()
            self.log_message(f"❌ ERROR: {str(e)}")
            self.log_message(traceback_text)

            self.root.after(0, lambda: messagebox.showerror("Processing Error", str(e)))

        finally:
            os.environ.pop("EARTHDATA_USERNAME", None)
            os.environ.pop("EARTHDATA_PASSWORD", None)

            self.processing = False
            self.root.after(0, lambda: self.run_button.config(state=tk.NORMAL))
            if not self.processing:
                self.root.after(0, lambda: self.update_status("✅ Ready"))

    # =========================================================================
    # PLOTTING METHODS
    # =========================================================================

    def create_plot(self, df, title, filename, date_range_str, mode="area_average"):
        try:
            fig, ax = plt.subplots(figsize=(14, 6))

            ax.plot(
                df["Datetime"],
                df["Area_Average"],
                color="red",
                linewidth=2.5,
                marker="o",
                markersize=6
            )

            ax.fill_between(
                df["Datetime"],
                df["Area_Average"],
                color="red",
                alpha=0.1
            )

            ax.set_xlabel("Date", fontsize=14, fontweight="bold")
            ylabel = "Area-Averaged Value" if mode == "area_average" else "Point Value"
            ax.set_ylabel(ylabel, fontsize=14, fontweight="bold")
            ax.set_title(f"{title}\n({date_range_str})", fontsize=16, fontweight="bold")

            ax.grid(True, linestyle="--", alpha=0.5)

            for spine in ax.spines.values():
                spine.set_linewidth(1.5)

            locator = mdates.AutoDateLocator()
            formatter = mdates.DateFormatter("%d-%b\n%H:%M")
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(formatter)

            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            plt.tight_layout()

            plt.savefig(filename, dpi=600, bbox_inches="tight")
            plt.close()

            self.log_message(f"✅ Plot saved: {os.path.basename(filename)}")

        except Exception as e:
            self.log_message(f"❌ Error creating plot {os.path.basename(filename)}: {str(e)}")

    def create_roi_plot(self, points, output):
        try:
            fig, ax = plt.subplots(figsize=(9, 8))

            geom = self.roi_geometry

            if geom.geom_type == "Polygon":
                x, y = geom.exterior.xy
                ax.plot(x, y, linewidth=2, color="blue")
                ax.fill(x, y, alpha=0.2, color="blue")

            elif geom.geom_type == "MultiPolygon":
                for polygon in geom.geoms:
                    x, y = polygon.exterior.xy
                    ax.plot(x, y, linewidth=2, color="blue")
                    ax.fill(x, y, alpha=0.2, color="blue")

            ax.scatter(
                [p["longitude"] for p in points],
                [p["latitude"] for p in points],
                s=15, color="red", alpha=0.7
            )

            centroid = geom.centroid
            ax.scatter(centroid.x, centroid.y, marker="x", s=100, color="black", linewidths=2)

            source = "OSM Selection" if self.roi_source.get() == "osm" else "KML/KMZ"
            ax.set_xlabel("Longitude", fontsize=13, fontweight="bold")
            ax.set_ylabel("Latitude", fontsize=13, fontweight="bold")
            ax.set_title(f"Giovanni ROI and Grid (Source: {source})", fontsize=16, fontweight="bold")
            ax.grid(True, linestyle="--", alpha=0.5)

            plt.tight_layout()
            plt.savefig(os.path.join(output, "ROI_and_Grid.png"), dpi=600, bbox_inches="tight")
            plt.close()

            self.log_message("✅ ROI map saved.")

        except Exception as e:
            self.log_message(f"❌ Error creating ROI plot: {str(e)}")

    def create_point_plot(self, output):
        try:
            fig, ax = plt.subplots(figsize=(8, 8))
            
            lat = float(self.single_point_lat.get())
            lon = float(self.single_point_lon.get())
            
            ax.scatter(lon, lat, s=200, color="red", marker="x", linewidths=3)
            
            circle = plt.Circle((lon, lat), 0.5, fill=False, color="blue", linewidth=2)
            ax.add_patch(circle)
            
            ax.set_xlabel("Longitude", fontsize=13, fontweight="bold")
            ax.set_ylabel("Latitude", fontsize=13, fontweight="bold")
            ax.set_title(f"Single Point Location\n({lat:.4f}, {lon:.4f})", fontsize=16, fontweight="bold")
            ax.grid(True, linestyle="--", alpha=0.5)
            
            ax.set_xlim(lon - 1, lon + 1)
            ax.set_ylim(lat - 1, lat + 1)
            
            plt.tight_layout()
            plt.savefig(os.path.join(output, "Point_Location.png"), dpi=600, bbox_inches="tight")
            plt.close()
            
            self.log_message("✅ Point location plot saved.")

        except Exception as e:
            self.log_message(f"❌ Error creating point plot: {str(e)}")

    # =========================================================================
    # DAILY SPATIAL MAPS
    # =========================================================================

    def create_daily_spatial_maps(self, raw_data, points, output_dir):
        try:
            raw_data['Date'] = raw_data['Datetime'].dt.date
            unique_dates = sorted(raw_data['Date'].unique())
            
            self.log_message(f"🗺️ Creating {len(unique_dates)} daily spatial maps...")
            
            lats = sorted(set([p["latitude"] for p in points]))
            lons = sorted(set([p["longitude"] for p in points]))
            
            lon_grid, lat_grid = np.meshgrid(lons, lats)
            
            is_precip = PRODUCTS[self.product.get()].get("precipitation", False)
            
            for i, date in enumerate(unique_dates):
                day_data = raw_data[raw_data['Date'] == date]
                
                if len(day_data) == 0:
                    continue
                
                grid_values = np.zeros((len(lats), len(lons)))
                grid_values.fill(np.nan)
                
                for idx, p in enumerate(points):
                    point_data = day_data[day_data['Grid_ID'] == idx + 1]
                    if len(point_data) > 0:
                        lat_idx = lats.index(p["latitude"])
                        lon_idx = lons.index(p["longitude"])
                        if is_precip:
                            grid_values[lat_idx, lon_idx] = point_data['Value'].sum()
                        else:
                            grid_values[lat_idx, lon_idx] = point_data['Value'].mean()
                
                fig, ax = plt.subplots(figsize=(10, 8))
                
                im = ax.pcolormesh(lon_grid, lat_grid, grid_values, 
                                   cmap='viridis', 
                                   shading='auto',
                                   alpha=0.8)
                
                cbar = plt.colorbar(im, ax=ax)
                if is_precip:
                    cbar.set_label('Accumulated Precipitation (mm)', fontsize=12)
                else:
                    cbar.set_label('Mean Value', fontsize=12)
                
                geom = self.roi_geometry
                if geom.geom_type == "Polygon":
                    x, y = geom.exterior.xy
                    ax.plot(x, y, linewidth=2, color='black', linestyle='--')
                elif geom.geom_type == "MultiPolygon":
                    for polygon in geom.geoms:
                        x, y = polygon.exterior.xy
                        ax.plot(x, y, linewidth=2, color='black', linestyle='--')
                
                ax.scatter(
                    [p["longitude"] for p in points],
                    [p["latitude"] for p in points],
                    s=5, color='black', alpha=0.3
                )
                
                ax.set_xlabel("Longitude", fontsize=13, fontweight="bold")
                ax.set_ylabel("Latitude", fontsize=13, fontweight="bold")
                
                date_str = date.strftime("%d %B %Y")
                if is_precip:
                    title = f"Daily Accumulated Precipitation - {date_str}"
                else:
                    title = f"Daily Mean Value - {date_str}"
                ax.set_title(title, fontsize=16, fontweight="bold")
                
                ax.grid(True, linestyle="--", alpha=0.3)
                
                plt.tight_layout()
                
                filename = f"Daily_Map_{date.strftime('%Y%m%d')}.png"
                plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches="tight")
                plt.close()
                
                progress = 96 + ((i + 1) / len(unique_dates)) * 3
                self.update_status(f"🗺️ Creating spatial maps: {i+1}/{len(unique_dates)}", progress)
                
                self.log_message(f"✅ Created map for {date.strftime('%Y-%m-%d')}")
            
            self.log_message(f"✅ All {len(unique_dates)} daily spatial maps created.")

        except Exception as e:
            self.log_message(f"❌ Error creating daily spatial maps: {str(e)}")

    # =========================================================================
    # OUTPUT FOLDER
    # =========================================================================

    def select_output(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_folder.set(folder)

# =============================================================================
# MAIN APPLICATION
# =============================================================================

if __name__ == "__main__":
    load_with_splash()