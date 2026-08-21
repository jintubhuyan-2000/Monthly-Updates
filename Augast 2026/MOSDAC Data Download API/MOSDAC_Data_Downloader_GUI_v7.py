"""
MOSDAC Data Downloader GUI with Data Visualization
A comprehensive GUI for downloading, processing, and visualizing satellite data from MOSDAC
"""

import sys
import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import requests
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import Normalize
import pandas as pd
from scipy import stats
import re

# Try importing rasterio for GeoTIFF support
try:
    import rasterio
    from rasterio.plot import show
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    print("Rasterio not installed. GeoTIFF support limited. Install with: pip install rasterio")

# Try importing xarray for NetCDF support
try:
    import xarray as xr
    HAS_XARRAY = True
except ImportError:
    HAS_XARRAY = False
    print("xarray not installed. NetCDF support limited. Install with: pip install xarray netCDF4")

# Try importing netCDF4
try:
    import netCDF4
    HAS_NETCDF4 = True
except ImportError:
    HAS_NETCDF4 = False

# GUI imports
try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    HAS_PYQT = True
except ImportError:
    print("PyQt5 is not installed. Please install it using: pip install PyQt5")
    HAS_PYQT = False
    sys.exit(1)

try:
    from tqdm.auto import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class MOSDACDownloader:
    """Core downloader class for MOSDAC data"""
    
    def __init__(self):
        self.token_url = "https://mosdac.gov.in/download_api/gettoken"
        self.search_url = "https://mosdac.gov.in/apios/datasets.json"
        self.check_internet_url = "https://mosdac.gov.in/download_api/check-internet"
        self.download_url = "https://mosdac.gov.in/download_api/download"
        self.refresh_url = "https://mosdac.gov.in/download_api/refresh-token"
        self.logout_url = "https://mosdac.gov.in/download_api/logout"
        self.datasets_url = "https://mosdac.gov.in/apios/datasets.json"
        
        self.access_token = None
        self.refresh_token = None
        self.username = None
        self.is_authenticated = False
        
        # Download settings
        self.download_path = ""
        self.use_date_structure = False
        self.generate_logs = False
        self.error_logs_dir = ""
        self.logger = None
        self.downloaded_files = []  # Store downloaded file paths for processing
        self.prefer_geotiff = True  # Prefer GeoTIFF downloads
        
    def authenticate(self, username: str, password: str) -> Tuple[bool, str]:
        """Authenticate with MOSDAC and get tokens"""
        try:
            data = {"username": username, "password": password}
            response = requests.post(self.token_url, json=data, timeout=10)
            
            if response.status_code == 503:
                return False, "Service Unavailable: Server is under maintenance"
                
            if response.status_code == 400:
                try:
                    resp = response.json()
                    return False, f"Validation Error: {resp.get('error', 'Invalid credentials')}"
                except:
                    return False, "Invalid credentials provided"
                    
            if response.status_code == 401:
                try:
                    resp = response.json()
                    return False, f"Authentication Error: {resp.get('error', 'Invalid username/password')}"
                except:
                    return False, "Invalid username or password"
                    
            response.raise_for_status()
            token_response = response.json()
            
            self.access_token = token_response.get("access_token")
            self.refresh_token = token_response.get("refresh_token")
            self.username = username
            self.is_authenticated = True
            
            return True, "Authentication successful"
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if '503' in error_msg or 'Service Unavailable' in error_msg:
                return False, "Server Unavailable: Please try again later"
            elif 'ConnectionError' in error_msg:
                return False, "Network Error: Please check your internet connection"
            else:
                return False, f"Authentication failed: {error_msg}"
    
    def get_datasets(self) -> List[Dict[str, Any]]:
        """Fetch available datasets from MOSDAC with detailed product info"""
        try:
            # First try to get from API
            response = requests.get(self.datasets_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                datasets = []
                
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            dataset_id = item.get('id') or item.get('datasetId')
                            if dataset_id:
                                datasets.append({
                                    "id": dataset_id,
                                    "title": item.get('title') or item.get('name') or dataset_id,
                                    "description": item.get('description', '')
                                })
                elif isinstance(data, dict) and 'entries' in data:
                    for entry in data['entries']:
                        if isinstance(entry, dict):
                            dataset_id = entry.get('id') or entry.get('datasetId')
                            if dataset_id:
                                datasets.append({
                                    "id": dataset_id,
                                    "title": entry.get('title') or entry.get('name') or dataset_id,
                                    "description": entry.get('description', '')
                                })
                
                if not datasets:
                    datasets = self.get_complete_datasets()
                    
                return datasets
            else:
                return self.get_complete_datasets()
                
        except Exception as e:
            print(f"Error fetching datasets: {e}")
            return self.get_complete_datasets()
    
    def get_complete_datasets(self) -> List[Dict[str, Any]]:
        """Return complete list of MOSDAC datasets from the product list"""
        return [
            {"id": "3RIMG_L2B_CTP", "title": "Cloud Top Properties", "description": "Cloud top properties derived using INSAT3R IMAGER"},
            {"id": "3RIMG_L3G_GPI_DLY", "title": "Daily GPI", "description": "Daily GPI from INSAT-3DR"},
            {"id": "3RIMG_L3B_HEM_DLY", "title": "Daily HEM", "description": "Daily HEM from INSAT-3DR"},
            {"id": "3RIMG_L3G_IMR_DLY", "title": "Daily IMR Rain", "description": "Daily IMR Rain from INSAT-3DR"},
            {"id": "3RIMG_L3B_OLR_DLY", "title": "Daily OLR", "description": "Daily OLR from INSAT-3DR"},
            {"id": "3RIMG_L3B_SST_DLY", "title": "Daily SST", "description": "Daily SST from INSAT-3DR"},
            {"id": "3RIMG_L3B_UTH_DLY", "title": "Daily UTH", "description": "Daily UTH from INSAT-3DR"},
            {"id": "3RIMG_L2C_CMP", "title": "Cloud Microphysics", "description": "Day-time cloud microphysical parameters"},
            {"id": "3RIMG_L3C_PET_DLY", "title": "Evapotranspiration", "description": "Evapotranspiration (ET) product"},
            {"id": "3RIMG_L1C_ASIA_MER", "title": "Imager L1C Asia", "description": "IMAGER Level1 data in Mercator projection for Asian Sector"},
            {"id": "3RIMG_L2B_IMC", "title": "IMSRA Rainfall", "description": "INSAT multispectral Rainfall Algorithm Technique"},
            {"id": "3RIMG_L2P_IRW", "title": "IR Wind", "description": "INSAT-3DR Infrared channel derived Wind"},
            {"id": "3RIMG_L2B_CMK", "title": "Cloud Mask", "description": "INSAT cloud mask algorithm"},
            {"id": "3RIMG_L2C_INS", "title": "Insolation", "description": "INSAT-3DR derived INSOLATION"},
            {"id": "3RIMG_L3C_INS_DLY", "title": "Daily Insolation", "description": "INSAT-3DR derived INSOLATION Daily"},
            {"id": "3RIMG_L2G_IMR", "title": "IMR Rain", "description": "Indian Multi Spectral rainfall from IMAGER"},
            {"id": "3RIMG_L2B_LST", "title": "Land Surface Temperature", "description": "Land surface temperature (LST)"},
            {"id": "3RIMG_L1C_SGP", "title": "L1C SGP", "description": "Level1 IMAGER 6 channel data in Mercator projection"},
            {"id": "3RIMG_L1B_STD", "title": "L1B Standard", "description": "Level1 data for Imager 6 channels"},
            {"id": "3RIMG_L2C_FOG", "title": "FOG", "description": "Night time FOG detection"},
            {"id": "3RIMG_L2G_GPI", "title": "GPI Rainfall", "description": "Rainfall from INSAT-3DR Imager using GOES Precipitation Index"},
            {"id": "3RIMG_L2B_SST", "title": "SST", "description": "Sea surface temperature from split thermal window channels"},
            {"id": "3RIMG_L2C_SNW", "title": "Snow Cover", "description": "Snow cover derived from IMAGER"},
            {"id": "3RIMG_L2G_AOD", "title": "Aerosol Optical Depth", "description": "Aerosol optical thickness at 650 nm"},
            {"id": "3RIMG_L2P_FIR", "title": "Active Fire", "description": "Active FIRE product"},
            {"id": "3RIMG_L2P_SMK", "title": "Active Smoke", "description": "Active Smoke product"},
            {"id": "3RIMG_L2P_WV_MERGED", "title": "Merged WV Wind", "description": "Merged wind product using Atmospheric Motion Vectors"},
            {"id": "3RIMG_L2B_HEM", "title": "HEM", "description": "Hydro-Estimator precipitation product"},
            {"id": "3RIMG_L2B_OLR", "title": "OLR", "description": "Outgoing Longwave Radiation"},
            {"id": "3RIMG_L2B_UTH", "title": "UTH", "description": "Upper Tropospheric Humidity"},
            {"id": "3RIMG_L2P_WVW", "title": "WV Wind", "description": "Water vapour derived wind vectors"},
            {"id": "3RIMG_L3G_GPI_WKL", "title": "Weekly GPI", "description": "Weekly GPI from INSAT-3DR"},
            {"id": "3RIMG_L3B_HEM_WKL", "title": "Weekly HEM", "description": "Weekly HEM from INSAT-3DR"},
            {"id": "3RIMG_L3G_IMR_WKL", "title": "Weekly IMR", "description": "Weekly IMR from INSAT-3DR"},
            {"id": "3RIMG_L3B_OLR_WKL", "title": "Weekly OLR", "description": "Weekly OLR from INSAT-3DR"},
            {"id": "3RIMG_L3B_SST_WKL", "title": "Weekly SST", "description": "Weekly SST from INSAT-3DR"},
            {"id": "3RIMG_L3B_UTH_WKL", "title": "Weekly UTH", "description": "Weekly UTH from INSAT-3DR"},
            {"id": "3RIMG_L2G_WDP", "title": "Wind Derived Product", "description": "Wind Derived Product using INSAT-3DR AMVs"},
            {"id": "3RIMG_L2P_MRW", "title": "MIR Wind", "description": "Winds derived using MIR band data"},
            {"id": "3RIMG_L2P_VSW", "title": "Visible Wind", "description": "Winds derived using Visible band data"},
        ]
    
    def search_files(self, dataset_id: str, start_time: str = "", end_time: str = "", 
                    bounding_box: str = "", gid: str = "", count: int = 0) -> Tuple[int, float, List[Dict]]:
        """Search for files matching the criteria"""
        try:
            data = {"datasetId": dataset_id}
            
            if start_time:
                data["startTime"] = start_time
            if end_time:
                data["endTime"] = end_time
            if bounding_box:
                data["boundingBox"] = bounding_box
            if gid:
                data["gId"] = gid
            if count > 0:
                data["count"] = count
                
            response = requests.get(self.search_url, params=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                total_results = result.get("totalResults", 0)
                total_size_mb = result.get("totalSizeMB", 0)
                entries = result.get("entries", [])
                
                # Sort entries to prioritize GeoTIFF files
                if self.prefer_geotiff:
                    entries = self.prioritize_geotiff(entries)
                
                return total_results, total_size_mb, entries
            else:
                return 0, 0, []
                
        except Exception as e:
            print(f"Error searching files: {e}")
            return 0, 0, []
    
    def prioritize_geotiff(self, entries):
        """Sort entries to prioritize GeoTIFF files"""
        geotiff_entries = []
        other_entries = []
        
        for entry in entries:
            identifier = entry.get('identifier', '').lower()
            # Check if it's a GeoTIFF
            if identifier.endswith('.tif') or identifier.endswith('.tiff') or 'geotiff' in identifier:
                geotiff_entries.append(entry)
            else:
                other_entries.append(entry)
        
        # Return GeoTIFF first, then others
        return geotiff_entries + other_entries
    
    def download_file(self, record_id: str, identifier: str, prod_date: str, 
                     file_num: int, total_files: int, progress_callback=None) -> Tuple[bool, str]:
        """Download a single file"""
        if not self.access_token:
            return False, "No access token available"
        
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"id": record_id}
        
        # Create download path
        if self.download_path:
            download_dir = self.download_path
        else:
            download_dir = os.getcwd()
            
        if self.use_date_structure and prod_date:
            try:
                date_obj = datetime.strptime(prod_date, "%Y-%m-%dT%H:%M:%SZ")
                year = date_obj.strftime("%Y")
                day = date_obj.strftime("%d")
                month_abbr = date_obj.strftime("%b").upper()
                day_month = f"{day}{month_abbr}"
                
                dataset_dir = os.path.join(download_dir, record_id.split('-')[0] if '-' in record_id else 'MOSDAC')
                download_dir = os.path.join(dataset_dir, year, day_month)
            except:
                pass
                
        os.makedirs(download_dir, exist_ok=True)
        file_path = os.path.join(download_dir, identifier)
        tmp_file_path = file_path + ".part"
        
        # Check if file already exists
        if os.path.exists(file_path):
            self.downloaded_files.append(file_path)
            return True, "File already exists"
            
        # Check for incomplete download
        if os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except:
                pass
        
        RETRY_DELAYS = [10, 20, 30, 60, 90, 120]
        
        for attempt, delay in enumerate(RETRY_DELAYS + [None]):
            try:
                response = requests.get(self.download_url, headers=headers, 
                                       params=params, stream=True, timeout=30)
                
                if response.status_code == 401:
                    return False, "Token expired"
                    
                if response.status_code == 404:
                    try:
                        error_data = response.json() if response.text else {}
                        if error_data.get("code") == "NOT_RELEASED":
                            return False, "Product not released on Internet"
                    except:
                        pass
                    return False, "File not found"
                    
                if response.status_code == 429:
                    try:
                        resp = response.json() if response.text else {}
                        err_type = resp.get('type', '')
                        if err_type == 'minute_limit':
                            time.sleep(20)
                            continue
                        elif err_type == 'daily_limit':
                            return False, "Daily download limit reached"
                    except:
                        time.sleep(20)
                        continue
                        
                response.raise_for_status()
                
                total_size = int(response.headers.get('Content-Length', 0))
                content_disposition = response.headers.get('Content-Disposition')
                
                if not content_disposition or 'filename=' not in content_disposition:
                    return False, "File not available on server"
                
                # Download file with progress
                with open(tmp_file_path, "wb") as file:
                    downloaded = 0
                    
                    if HAS_TQDM:
                        with tqdm(desc=f"[{file_num}/{total_files}]", total=total_size, 
                                 unit='B', unit_scale=True) as bar:
                            for chunk in response.iter_content(chunk_size=1048576):
                                if chunk:
                                    file.write(chunk)
                                    downloaded += len(chunk)
                                    bar.update(len(chunk))
                                    if progress_callback:
                                        progress_callback(file_num, total_files, downloaded, total_size)
                    else:
                        chunk_size = 1048576
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if chunk:
                                file.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback:
                                    progress_callback(file_num, total_files, downloaded, total_size)
                        
                os.rename(tmp_file_path, file_path)
                self.downloaded_files.append(file_path)
                return True, "Download successful"
                
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if delay is None:
                    return False, f"Network error after multiple retries: {str(e)}"
                if os.path.exists(tmp_file_path):
                    try:
                        os.remove(tmp_file_path)
                    except:
                        pass
                time.sleep(delay)
                
            except Exception as e:
                return False, f"Download error: {str(e)}"
        
        return False, "Download failed"
    
    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            return False
            
        try:
            data = {"refresh_token": self.refresh_token}
            response = requests.post(self.refresh_url, json=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                return True
            return False
            
        except Exception:
            return False
    
    def logout(self) -> bool:
        """Logout from MOSDAC"""
        if not self.username:
            return True
            
        try:
            data = {"username": self.username}
            response = requests.post(self.logout_url, json=data, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def setup_logging(self, log_dir: str):
        """Setup error logging"""
        if not log_dir:
            log_dir = os.path.join(os.getcwd(), "error_logs")
            
        try:
            os.makedirs(log_dir, exist_ok=True)
            self.error_logs_dir = log_dir
            
            date_str = datetime.now().strftime("%d-%m-%Y")
            log_file_path = os.path.join(log_dir, f"{date_str}_error.log")
            
            logger = logging.getLogger("mosdac_client")
            logger.handlers.clear()
            
            file_handler = logging.FileHandler(log_file_path)
            formatter = logging.Formatter(
                fmt="%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%d-%m-%Y %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            logger.setLevel(logging.ERROR)
            self.logger = logger
            self.generate_logs = True
            
        except Exception as e:
            print(f"Error setting up logging: {e}")


class DataProcessor:
    """Class for processing and visualizing downloaded data"""
    
    def __init__(self):
        self.data = None
        self.lat = None
        self.lon = None
        self.time = None
        self.variable_name = None
        self.log_callback = None
        self.is_geotiff = False
        
    def set_log_callback(self, callback):
        """Set callback for logging messages"""
        self.log_callback = callback
        
    def add_log(self, message):
        """Add log message"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[Processor] {message}")
    
    def load_geotiff(self, file_path):
        """Load GeoTIFF file using rasterio"""
        try:
            if not HAS_RASTERIO:
                self.add_log("Rasterio not installed. Cannot load GeoTIFF.")
                self.add_log("Install with: pip install rasterio")
                return None
                
            src = rasterio.open(file_path)
            data = src.read(1)  # Read first band
            
            # Get transform
            transform = src.transform
            width = src.width
            height = src.height
            
            # Create lat/lon arrays
            lon = np.arange(width) * transform.a + transform.c
            lat = np.arange(height) * transform.e + transform.f
            
            # Handle missing values
            if src.nodata is not None:
                data = np.ma.masked_where(data == src.nodata, data)
            else:
                data = np.ma.masked_invalid(data)
            
            self.is_geotiff = True
            self.data = data[np.newaxis, :, :]  # Add time dimension
            self.lat = lat
            self.lon = lon
            self.variable_name = os.path.basename(file_path)
            
            self.add_log(f"Loaded GeoTIFF: {os.path.basename(file_path)}")
            self.add_log(f"  Shape: {data.shape}")
            self.add_log(f"  Bounds: lon {lon.min():.2f} to {lon.max():.2f}, lat {lat.min():.2f} to {lat.max():.2f}")
            self.add_log(f"  CRS: {src.crs}")
            
            src.close()
            return self.data
            
        except Exception as e:
            self.add_log(f"Error loading GeoTIFF: {str(e)}")
            return None
    
    def load_netcdf(self, file_path):
        """Load NetCDF file"""
        try:
            if not HAS_XARRAY:
                self.add_log("xarray not installed, cannot load NetCDF")
                self.add_log("Install with: pip install xarray netCDF4")
                return None
                
            ds = xr.open_dataset(file_path, engine='netcdf4')
            
            # Find data variable
            data_vars = [var for var in ds.variables if var not in ds.dims]
            if not data_vars:
                self.add_log("No data variables found in NetCDF")
                return None
                
            var_name = data_vars[0]
            self.variable_name = var_name
            data = ds[var_name].values
            
            # Extract coordinates
            lat = None
            lon = None
            
            for coord in ['lat', 'latitude', 'y']:
                if coord in ds.coords:
                    lat = ds[coord].values
                    break
            if lat is None:
                for dim in ds[var_name].dims:
                    if 'lat' in dim.lower() or 'y' in dim.lower():
                        lat = ds[dim].values
                        break
            
            for coord in ['lon', 'longitude', 'x']:
                if coord in ds.coords:
                    lon = ds[coord].values
                    break
            if lon is None:
                for dim in ds[var_name].dims:
                    if 'lon' in dim.lower() or 'x' in dim.lower():
                        lon = ds[dim].values
                        break
            
            # Get time
            time = None
            for coord in ['time', 'Time']:
                if coord in ds.coords:
                    time = ds[coord].values
                    break
            
            self.data = data
            self.lat = lat
            self.lon = lon
            self.time = time
            
            self.add_log(f"Loaded NetCDF: {os.path.basename(file_path)}")
            self.add_log(f"  Variable: {var_name}, Shape: {data.shape}")
            if lat is not None:
                self.add_log(f"  Lat: {lat.min():.2f} to {lat.max():.2f}")
            if lon is not None:
                self.add_log(f"  Lon: {lon.min():.2f} to {lon.max():.2f}")
            
            ds.close()
            return data
            
        except Exception as e:
            self.add_log(f"Error loading NetCDF: {str(e)}")
            return None
    
    def detect_and_load(self, file_path):
        """Detect file type and load accordingly"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Check for GeoTIFF first
        if file_ext in ['.tif', '.tiff']:
            self.add_log(f"Detected GeoTIFF file: {os.path.basename(file_path)}")
            return self.load_geotiff(file_path)
        
        # Check for NetCDF
        elif file_ext in ['.nc', '.nc4', '.hdf', '.h5']:
            self.add_log(f"Detected NetCDF/HDF file: {os.path.basename(file_path)}")
            return self.load_netcdf(file_path)
        
        # Try to detect from content
        else:
            # Try NetCDF first
            try:
                data = self.load_netcdf(file_path)
                if data is not None:
                    return data
            except:
                pass
            
            # Try GeoTIFF
            try:
                data = self.load_geotiff(file_path)
                if data is not None:
                    return data
            except:
                pass
            
            self.add_log(f"Unknown file format: {os.path.basename(file_path)}")
            return None
    
    def calculate_area_average(self, data=None, lat=None, lon=None):
        """Calculate area-weighted average"""
        try:
            if data is None:
                data = self.data
            if lat is None:
                lat = self.lat
            if lon is None:
                lon = self.lon
                
            if data is None or lat is None or lon is None:
                return None
                
            # Create weight matrix based on latitude
            if len(data.shape) == 3:  # Time, lat, lon
                weights = np.cos(np.deg2rad(lat))
                weights = weights[np.newaxis, :, np.newaxis]
                weights = np.repeat(weights, data.shape[0], axis=0)
                
                weighted_sum = np.nansum(data * weights, axis=(1, 2))
                total_weight = np.nansum(weights, axis=(1, 2))
                area_avg = weighted_sum / total_weight
                
                return area_avg
                
            elif len(data.shape) == 2:  # 2D data
                weights = np.cos(np.deg2rad(lat))
                weights = weights[np.newaxis, :]
                weights = np.repeat(weights, data.shape[0], axis=0)
                
                weighted_sum = np.nansum(data * weights, axis=1)
                total_weight = np.nansum(weights, axis=1)
                area_avg = weighted_sum / total_weight
                
                return area_avg
                
            else:
                return np.nanmean(data)
                
        except Exception as e:
            self.add_log(f"Error calculating area average: {str(e)}")
            return None
    
    def create_time_series_plot(self, data, labels=None, title="Time Series", 
                              xlabel="Time", ylabel="Value", output_path=None):
        """Create time series plot"""
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            if labels is None:
                labels = [f"Series {i+1}" for i in range(len(data))]
            
            for i, d in enumerate(data):
                if isinstance(d, (list, np.ndarray)) and len(d) > 0:
                    ax.plot(d, label=labels[i], linewidth=2, marker='o', markersize=4)
                else:
                    ax.plot([d], label=labels[i], linewidth=2, marker='o', markersize=4)
            
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            ax.legend(loc='best')
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                self.add_log(f"Time series plot saved to: {output_path}")
                
            return fig
            
        except Exception as e:
            self.add_log(f"Error creating time series plot: {str(e)}")
            return None
    
    def create_spatial_map(self, data, lat, lon, time_idx=0, 
                          title="Spatial Map", output_path=None,
                          cmap='viridis', add_colorbar=True):
        """Create spatial map"""
        try:
            fig, ax = plt.subplots(figsize=(12, 8))
            
            if len(data.shape) == 3:
                plot_data = data[time_idx]
            else:
                plot_data = data
            
            plot_data = np.ma.masked_invalid(plot_data)
            
            im = ax.pcolormesh(lon, lat, plot_data, cmap=cmap, shading='auto')
            
            if add_colorbar:
                cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02)
                cbar.set_label(self.variable_name if self.variable_name else 'Value')
            
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_xlabel('Longitude', fontsize=12)
            ax.set_ylabel('Latitude', fontsize=12)
            ax.grid(True, alpha=0.2, linestyle='--')
            
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                self.add_log(f"Spatial map saved to: {output_path}")
                
            return fig
            
        except Exception as e:
            self.add_log(f"Error creating spatial map: {str(e)}")
            return None
    
    def create_combined_plot(self, data, lat, lon, time_avg, output_path=None):
        """Create combined plot"""
        try:
            fig = plt.figure(figsize=(15, 10))
            
            # Spatial map
            ax1 = plt.subplot(2, 2, (1, 2))
            plot_data = np.ma.masked_invalid(time_avg)
            im = ax1.pcolormesh(lon, lat, plot_data, cmap='viridis', shading='auto')
            ax1.set_title(f'Spatial Distribution - {self.variable_name}', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Longitude', fontsize=10)
            ax1.set_ylabel('Latitude', fontsize=10)
            ax1.grid(True, alpha=0.2, linestyle='--')
            cbar = plt.colorbar(im, ax=ax1, orientation='vertical', pad=0.02)
            cbar.set_label(self.variable_name if self.variable_name else 'Value')
            
            # Time series
            ax2 = plt.subplot(2, 2, 3)
            if len(data.shape) == 3:
                area_avg = self.calculate_area_average(data)
                if area_avg is not None:
                    ax2.plot(area_avg, linewidth=2, marker='o', markersize=4)
                    ax2.set_title('Area Average Time Series', fontsize=12, fontweight='bold')
                    ax2.set_xlabel('Time Step', fontsize=10)
                    ax2.set_ylabel(self.variable_name if self.variable_name else 'Value', fontsize=10)
                    ax2.grid(True, alpha=0.3)
            
            # Statistics
            ax3 = plt.subplot(2, 2, 4)
            ax3.axis('off')
            
            flat_data = plot_data.compressed() if hasattr(plot_data, 'compressed') else plot_data.flatten()
            flat_data = flat_data[~np.isnan(flat_data)]
            
            stats_text = f"""
            Statistics Summary
            {'='*30}
            
            Mean: {np.mean(flat_data):.4f}
            Std Dev: {np.std(flat_data):.4f}
            Min: {np.min(flat_data):.4f}
            Max: {np.max(flat_data):.4f}
            
            Data Points: {len(flat_data)}
            """
            
            if len(flat_data) > 2:
                x = np.arange(len(flat_data))
                z = np.polyfit(x, flat_data, 1)
                stats_text += f"\nTrend: {z[0]:.4f}"
            
            ax3.text(0.1, 0.5, stats_text, transform=ax3.transAxes,
                    fontsize=11, verticalalignment='center',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            plt.suptitle(f'Data Analysis - {self.variable_name}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            if output_path:
                plt.savefig(output_path, dpi=300, bbox_inches='tight')
                self.add_log(f"Combined plot saved to: {output_path}")
                
            return fig
            
        except Exception as e:
            self.add_log(f"Error creating combined plot: {str(e)}")
            return None
    
    def process_all_files(self, file_list, output_dir=None, bounding_box=None):
        """Process all downloaded files"""
        try:
            results = {
                'time_series': [],
                'spatial_maps': [],
                'stats': {},
                'combined_plots': [],
                'file_info': []
            }
            
            all_days_data = []
            
            if output_dir:
                plots_dir = os.path.join(output_dir, "plots")
                os.makedirs(plots_dir, exist_ok=True)
            else:
                plots_dir = None
            
            self.add_log(f"Processing {len(file_list)} files...")
            
            for i, file_path in enumerate(file_list):
                self.add_log(f"Processing file {i+1}/{len(file_list)}: {os.path.basename(file_path)}")
                
                # Detect and load file
                data = self.detect_and_load(file_path)
                
                if data is None:
                    self.add_log(f"Could not load file {os.path.basename(file_path)}")
                    continue
                
                results['file_info'].append({
                    'name': os.path.basename(file_path),
                    'path': file_path,
                    'shape': data.shape if hasattr(data, 'shape') else None,
                    'is_geotiff': self.is_geotiff
                })
                
                # Calculate area average
                area_avg = self.calculate_area_average()
                if area_avg is not None:
                    results['time_series'].append(area_avg)
                    if isinstance(area_avg, (list, np.ndarray)):
                        all_days_data.extend(area_avg)
                    else:
                        all_days_data.append(area_avg)
                
                # Create spatial map
                if plots_dir and self.lat is not None and self.lon is not None:
                    title = f"Day {i+1} - {os.path.basename(file_path)}"
                    output_path = os.path.join(plots_dir, f"spatial_map_day_{i+1:03d}.png")
                    fig = self.create_spatial_map(self.data, self.lat, self.lon, time_idx=0,
                                                 title=title, output_path=output_path)
                    if fig:
                        results['spatial_maps'].append(fig)
                        plt.close(fig)
            
            # Create time series plot
            if results['time_series']:
                labels = [f"File {i+1}" for i in range(len(results['time_series']))]
                output_path = os.path.join(plots_dir, "time_series_area_average.png") if plots_dir else None
                
                fig = self.create_time_series_plot(
                    results['time_series'], labels,
                    title=f"Area Average Time Series - {self.variable_name if self.variable_name else 'Value'}",
                    xlabel="Time Step", 
                    ylabel=self.variable_name if self.variable_name else "Value",
                    output_path=output_path
                )
                if fig:
                    results['time_series_plot'] = fig
                    plt.close(fig)
            
            # Create combined plot
            if hasattr(self, 'data') and self.data is not None and plots_dir and self.lat is not None and self.lon is not None:
                self.add_log("Creating combined analysis plot...")
                if len(self.data.shape) == 3:
                    time_avg = np.nanmean(self.data, axis=0)
                else:
                    time_avg = self.data
                
                output_path = os.path.join(plots_dir, "combined_analysis.png")
                fig = self.create_combined_plot(self.data, self.lat, self.lon, time_avg, output_path)
                if fig:
                    results['combined_plots'].append(fig)
                    plt.close(fig)
            
            # Calculate statistics
            if all_days_data:
                all_days_data = np.array(all_days_data).flatten()
                all_days_data = all_days_data[~np.isnan(all_days_data)]
                
                if len(all_days_data) > 0:
                    results['stats'] = {
                        'mean': np.mean(all_days_data),
                        'std': np.std(all_days_data),
                        'min': np.min(all_days_data),
                        'max': np.max(all_days_data),
                        'count': len(all_days_data)
                    }
            
            self.add_log(f"Processing complete! Generated {len(results['spatial_maps'])} spatial maps")
            return results
            
        except Exception as e:
            self.add_log(f"Error processing files: {str(e)}")
            import traceback
            traceback.print_exc()
            return None


class DownloadWorker(QThread):
    """Worker thread for downloading files"""
    
    progress_signal = pyqtSignal(int, int, int, int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, int, int, float)
    error_signal = pyqtSignal(str)
    processing_signal = pyqtSignal(object)
    
    def __init__(self, downloader: MOSDACDownloader, dataset_id: str, start_time: str, 
                 end_time: str, bounding_box: str, gid: str, count: int, process_data: bool = True):
        super().__init__()
        self.downloader = downloader
        self.dataset_id = dataset_id
        self.start_time = start_time
        self.end_time = end_time
        self.bounding_box = bounding_box
        self.gid = gid
        self.count = count
        self.is_running = True
        self.process_data = process_data
        
    def stop(self):
        self.is_running = False
        
    def run(self):
        try:
            start_time = time.time()
            self.log_signal.emit(f"Searching for files with dataset: {self.dataset_id}")
            self.log_signal.emit("Prioritizing GeoTIFF files if available...")
            
            total_results, total_size, entries = self.downloader.search_files(
                self.dataset_id, self.start_time, self.end_time,
                self.bounding_box, self.gid, self.count
            )
            
            if total_results == 0:
                self.error_signal.emit("No files found matching the search criteria")
                return
                
            size_str = self.format_size(total_size)
            self.log_signal.emit(f"Found {total_results} files, Total size: {size_str}")
            
            # Count GeoTIFF files
            geotiff_count = sum(1 for e in entries if e.get('identifier', '').lower().endswith(('.tif', '.tiff')))
            if geotiff_count > 0:
                self.log_signal.emit(f"Found {geotiff_count} GeoTIFF files (prioritized for download)")
            
            downloaded = 0
            skipped = 0
            
            for i, entry in enumerate(entries, 1):
                if not self.is_running:
                    break
                    
                record_id = entry.get("id")
                identifier = entry.get("identifier")
                prod_date = entry.get("updated")
                
                is_geotiff = identifier.lower().endswith(('.tif', '.tiff'))
                file_type = "GeoTIFF" if is_geotiff else "Other"
                
                self.log_signal.emit(f"Processing file {i}/{len(entries)}: {identifier} [{file_type}]")
                
                success, message = self.downloader.download_file(
                    record_id, identifier, prod_date, i, len(entries),
                    self.update_progress
                )
                
                if success:
                    if message == "File already exists":
                        skipped += 1
                        self.log_signal.emit(f"File skipped: {identifier} (already exists)")
                    else:
                        downloaded += 1
                        self.log_signal.emit(f"File downloaded: {identifier} [{file_type}]")
                else:
                    skipped += 1
                    self.log_signal.emit(f"File failed: {identifier} - {message}")
                    
            end_time = time.time()
            time_taken = end_time - start_time
            
            if self.process_data and self.downloader.downloaded_files:
                self.log_signal.emit("Processing downloaded data...")
                processor = DataProcessor()
                processor.set_log_callback(self.log_signal.emit)
                
                results = processor.process_all_files(
                    self.downloader.downloaded_files,
                    output_dir=self.downloader.download_path
                )
                
                if results:
                    self.processing_signal.emit(results)
                    self.log_signal.emit("Data processing completed")
                    self.log_signal.emit(f"Generated {len(results.get('spatial_maps', []))} spatial maps")
                else:
                    self.log_signal.emit("No data could be processed")
            
            self.finished_signal.emit(True, downloaded, skipped, time_taken)
            
        except Exception as e:
            self.error_signal.emit(f"Download error: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def update_progress(self, file_num, total_files, downloaded, total_size):
        self.progress_signal.emit(file_num, total_files, downloaded, total_size)
        
    def format_size(self, size_mb):
        if size_mb < 1024:
            return f"{size_mb:.2f} MB"
        elif size_mb < 1024 * 1024:
            size_gb = size_mb / 1024
            return f"{size_gb:.2f} GB"
        else:
            size_tb = size_mb / (1024 * 1024)
            return f"{size_tb:.2f} TB"


class VisualizationTab(QWidget):
    """Tab for displaying visualizations"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = None
        self.current_plot = None
        self.init_ui()
        
    def init_ui(self):
        """Initialize visualization UI"""
        layout = QVBoxLayout(self)
        
        # Control panel
        control_layout = QHBoxLayout()
        
        self.plot_type_combo = QComboBox()
        self.plot_type_combo.addItems(["Time Series", "Spatial Map", "Combined Analysis"])
        self.plot_type_combo.currentTextChanged.connect(self.refresh_plots)
        control_layout.addWidget(QLabel("Plot Type:"))
        control_layout.addWidget(self.plot_type_combo)
        
        control_layout.addStretch()
        
        self.save_plot_button = QPushButton("Save Current Plot")
        self.save_plot_button.clicked.connect(self.save_current_plot)
        control_layout.addWidget(self.save_plot_button)
        
        layout.addLayout(control_layout)
        
        # Figure canvas
        self.figure = Figure(figsize=(12, 8))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(500)
        layout.addWidget(self.canvas)
        
        # Info label
        self.info_label = QLabel("No data available for visualization")
        self.info_label.setStyleSheet("color: #7f8c8d; font-style: italic; padding: 5px;")
        layout.addWidget(self.info_label)
        
    def update_plots(self, results):
        """Update plots with processing results"""
        self.results = results
        self.refresh_plots()
        
    def refresh_plots(self):
        """Refresh the current plot"""
        if not self.results:
            self.figure.clear()
            self.info_label.setText("No data available for visualization")
            self.canvas.draw()
            return
            
        plot_type = self.plot_type_combo.currentText()
        self.figure.clear()
        
        if plot_type == "Time Series":
            self.plot_time_series()
        elif plot_type == "Spatial Map":
            self.plot_spatial_map()
        elif plot_type == "Combined Analysis":
            self.plot_combined_analysis()
            
        self.canvas.draw()
        
    def plot_time_series(self):
        """Plot time series data"""
        try:
            if 'time_series' in self.results and self.results['time_series']:
                ax = self.figure.add_subplot(111)
                
                for i, data in enumerate(self.results['time_series']):
                    if isinstance(data, (list, np.ndarray)) and len(data) > 0:
                        ax.plot(data, label=f"Series {i+1}", linewidth=2, marker='o', markersize=4)
                    else:
                        ax.plot([data], label=f"Series {i+1}", linewidth=2, marker='o', markersize=4)
                
                ax.set_title("Area Average Time Series", fontsize=14, fontweight='bold')
                ax.set_xlabel("Time Step", fontsize=12)
                ax.set_ylabel("Value", fontsize=12)
                ax.legend(loc='best')
                ax.grid(True, alpha=0.3)
                
                if 'stats' in self.results:
                    stats = self.results['stats']
                    stats_text = f"Mean: {stats.get('mean', 0):.4f}\nStd: {stats.get('std', 0):.4f}"
                    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                           fontsize=10, verticalalignment='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
                
                self.info_label.setText("Time Series Plot Displayed")
            else:
                self.info_label.setText("No time series data available")
        except Exception as e:
            self.info_label.setText(f"Error plotting time series: {str(e)}")
            
    def plot_spatial_map(self):
        """Plot spatial map info"""
        try:
            if 'spatial_maps' in self.results and self.results['spatial_maps']:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 
                       f"Spatial maps have been saved as PNG files.\n"
                       f"Total maps: {len(self.results['spatial_maps'])}\n\n"
                       f"Files are saved in the 'plots' folder\n"
                       f"of your output directory.",
                       ha='center', va='center', fontsize=12,
                       transform=ax.transAxes)
                ax.axis('off')
                
                self.info_label.setText(f"Spatial maps saved: {len(self.results['spatial_maps'])} files")
            else:
                self.info_label.setText("No spatial maps available")
        except Exception as e:
            self.info_label.setText(f"Error: {str(e)}")
            
    def plot_combined_analysis(self):
        """Plot combined analysis info"""
        try:
            if 'combined_plots' in self.results and self.results['combined_plots']:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 
                       f"Combined analysis plot has been saved.\n\n"
                       f"File: combined_analysis.png\n"
                       f"Location: 'plots' folder\n\n"
                       f"This plot includes:\n"
                       f"• Spatial distribution map\n"
                       f"• Time series analysis\n"
                       f"• Statistics summary",
                       ha='center', va='center', fontsize=12,
                       transform=ax.transAxes)
                ax.axis('off')
                
                self.info_label.setText("Combined analysis plot saved")
            else:
                self.info_label.setText("No combined analysis plot available")
        except Exception as e:
            self.info_label.setText(f"Error: {str(e)}")
    
    def save_current_plot(self):
        """Save the current plot"""
        if not self.results:
            QMessageBox.warning(self, "No Plot", "No plot available to save")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Plot", 
            f"plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*.*)"
        )
        
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight')
                QMessageBox.information(self, "Plot Saved", f"Plot saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"Could not save plot: {str(e)}")


class MOSDACGui(QMainWindow):
    """Main GUI window for MOSDAC Downloader"""
    
    def __init__(self):
        super().__init__()
        self.downloader = MOSDACDownloader()
        self.download_worker = None
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("MOSDAC Data Downloader with Visualization - GeoTIFF Priority")
        self.setGeometry(100, 100, 900, 800)
        self.setMinimumSize(850, 750)
        
        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
            QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit {
                padding: 5px;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
                border: 1px solid #4CAF50;
            }
            QTabWidget::pane {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: white;
            }
            QCheckBox {
                font-weight: normal;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        self.create_auth_tab()
        self.create_download_tab()
        self.create_visualization_tab()
        self.create_log_tab()
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - GeoTIFF files will be prioritized")
        
    def create_auth_tab(self):
        """Create authentication tab"""
        auth_tab = QWidget()
        self.tab_widget.addTab(auth_tab, "Authentication")
        
        layout = QVBoxLayout(auth_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("MOSDAC Data Downloader")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #2c3e50;")
        layout.addWidget(title)
        
        subtitle = QLabel("Authenticate with your MOSDAC credentials to access the data catalogue")
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 10pt;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        auth_group = QGroupBox("Credentials")
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(10)
        
        username_layout = QHBoxLayout()
        username_label = QLabel("Username / Email:")
        username_label.setMinimumWidth(150)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your MOSDAC username or email")
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        auth_layout.addLayout(username_layout)
        
        password_layout = QHBoxLayout()
        password_label = QLabel("Password:")
        password_label.setMinimumWidth(150)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your MOSDAC password")
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        auth_layout.addLayout(password_layout)
        
        verify_layout = QHBoxLayout()
        verify_layout.addStretch()
        self.verify_button = QPushButton("Verify Credentials")
        self.verify_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 20px;
                font-weight: bold;
                border-radius: 4px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.verify_button.clicked.connect(self.verify_credentials)
        verify_layout.addWidget(self.verify_button)
        auth_layout.addLayout(verify_layout)
        
        layout.addWidget(auth_group)
        
        status_group = QGroupBox("Authentication Status")
        status_layout = QVBoxLayout(status_group)
        
        self.auth_status = QLabel("Not authenticated")
        self.auth_status.setStyleSheet("color: #7f8c8d; padding: 5px;")
        status_layout.addWidget(self.auth_status)
        
        self.user_info = QLabel("")
        self.user_info.setStyleSheet("color: #7f8c8d; padding: 5px;")
        status_layout.addWidget(self.user_info)
        
        layout.addWidget(status_group)
        layout.addStretch()
        
    def create_download_tab(self):
        """Create download tab"""
        download_tab = QWidget()
        self.tab_widget.addTab(download_tab, "Download")
        self.tab_widget.setTabEnabled(1, False)
        
        layout = QVBoxLayout(download_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Info about GeoTIFF priority
        info_label = QLabel("⚠️ GeoTIFF files will be prioritized for download when available")
        info_label.setStyleSheet("color: #2196F3; font-weight: bold; padding: 5px; background-color: #e3f2fd; border-radius: 3px;")
        layout.addWidget(info_label)
        
        dataset_group = QGroupBox("Search Parameters")
        dataset_layout = QGridLayout(dataset_group)
        dataset_layout.setVerticalSpacing(10)
        dataset_layout.setHorizontalSpacing(10)
        
        dataset_layout.addWidget(QLabel("Dataset ID:"), 0, 0)
        self.dataset_combo = QComboBox()
        self.dataset_combo.setEditable(True)
        self.dataset_combo.setPlaceholderText("Enter dataset ID (e.g., 3RIMG_L2B_SST)")
        # Pre-populate with common datasets
        for dataset in self.downloader.get_complete_datasets():
            display_text = f"{dataset['title']} [{dataset['id']}]"
            self.dataset_combo.addItem(display_text, dataset['id'])
        dataset_layout.addWidget(self.dataset_combo, 0, 1)
        
        self.refresh_datasets_button = QPushButton("↻ Load Datasets")
        self.refresh_datasets_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                padding: 5px 10px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.refresh_datasets_button.clicked.connect(self.refresh_datasets)
        dataset_layout.addWidget(self.refresh_datasets_button, 0, 2)
        
        dataset_layout.addWidget(QLabel("Start Date:"), 1, 0)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-10))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        dataset_layout.addWidget(self.start_date, 1, 1)
        
        dataset_layout.addWidget(QLabel("End Date:"), 2, 0)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        dataset_layout.addWidget(self.end_date, 2, 1)
        
        dataset_layout.addWidget(QLabel("Bounding Box:"), 3, 0)
        self.bounding_box = QLineEdit()
        self.bounding_box.setPlaceholderText("min_lon,min_lat,max_lon,max_lat (e.g., 68,8,98,38)")
        self.bounding_box.textChanged.connect(self.on_bbox_changed)
        dataset_layout.addWidget(self.bounding_box, 3, 1, 1, 2)
        
        dataset_layout.addWidget(QLabel("gId:"), 4, 0)
        self.gid_input = QLineEdit()
        self.gid_input.setPlaceholderText("Geographic identifier (optional)")
        dataset_layout.addWidget(self.gid_input, 4, 1, 1, 2)
        
        dataset_layout.addWidget(QLabel("File Count:"), 5, 0)
        self.count_input = QSpinBox()
        self.count_input.setRange(0, 10000)
        self.count_input.setValue(0)
        self.count_input.setSpecialValueText("All")
        dataset_layout.addWidget(self.count_input, 5, 1)
        
        help_label = QLabel("Note: Leave File Count as 0 (All) to download all files")
        help_label.setStyleSheet("color: #7f8c8d; font-size: 9pt; font-style: italic; grid-column: 1 / 3;")
        dataset_layout.addWidget(help_label, 6, 0, 1, 2)
        
        layout.addWidget(dataset_group)
        
        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)
        
        output_row = QHBoxLayout()
        output_label = QLabel("Output Folder:")
        output_label.setMinimumWidth(100)
        self.output_folder = QLineEdit()
        self.output_folder.setText(os.path.join(os.getcwd(), "MOSDAC_Data"))
        self.output_folder.setPlaceholderText("Select output folder")
        output_row.addWidget(output_label)
        output_row.addWidget(self.output_folder)
        
        browse_button = QPushButton("Browse...")
        browse_button.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
        """)
        browse_button.clicked.connect(self.browse_output_folder)
        output_row.addWidget(browse_button)
        output_layout.addLayout(output_row)
        
        options_layout = QHBoxLayout()
        self.organize_by_date = QCheckBox("Organize files by date")
        self.organize_by_date.setChecked(False)
        options_layout.addWidget(self.organize_by_date)
        
        self.generate_logs = QCheckBox("Generate error logs")
        self.generate_logs.setChecked(True)
        options_layout.addWidget(self.generate_logs)
        
        self.process_data = QCheckBox("Process and visualize data after download")
        self.process_data.setChecked(True)
        options_layout.addWidget(self.process_data)
        
        options_layout.addStretch()
        output_layout.addLayout(options_layout)
        
        layout.addWidget(output_group)
        
        download_row = QHBoxLayout()
        download_row.addStretch()
        self.download_button = QPushButton("🔍 Search & Start Download")
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 10px 30px;
                font-weight: bold;
                font-size: 12pt;
                border-radius: 4px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.download_button.clicked.connect(self.start_download)
        download_row.addWidget(self.download_button)
        layout.addLayout(download_row)
        
        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to download")
        self.status_label.setStyleSheet("color: #7f8c8d;")
        progress_layout.addWidget(self.status_label)
        
        layout.addWidget(progress_group)
        
    def create_visualization_tab(self):
        """Create visualization tab"""
        self.visualization_tab = VisualizationTab()
        self.tab_widget.addTab(self.visualization_tab, "Visualization")
        self.tab_widget.setTabEnabled(2, False)
        
    def create_log_tab(self):
        """Create log tab"""
        log_tab = QWidget()
        self.tab_widget.addTab(log_tab, "Processing Log")
        self.tab_widget.setTabEnabled(3, False)
        
        layout = QVBoxLayout(log_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.log_text)
        
        control_layout = QHBoxLayout()
        
        clear_button = QPushButton("Clear Log")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        clear_button.clicked.connect(self.clear_log)
        control_layout.addWidget(clear_button)
        
        save_button = QPushButton("Save Log")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        save_button.clicked.connect(self.save_log)
        control_layout.addWidget(save_button)
        
        control_layout.addStretch()
        
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        control_layout.addWidget(self.auto_scroll)
        
        layout.addLayout(control_layout)
        
    def load_config(self):
        """Load saved configuration"""
        config_file = "mosdac_gui_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    
                if "username" in config:
                    self.username_input.setText(config["username"])
                if "output_folder" in config:
                    self.output_folder.setText(config["output_folder"])
                if "organize_by_date" in config:
                    self.organize_by_date.setChecked(config["organize_by_date"])
                if "generate_logs" in config:
                    self.generate_logs.setChecked(config["generate_logs"])
                if "process_data" in config:
                    self.process_data.setChecked(config["process_data"])
                if "last_dataset" in config:
                    self.dataset_combo.setCurrentText(config["last_dataset"])
                if "bounding_box" in config:
                    self.bounding_box.setText(config["bounding_box"])
                if "gid" in config:
                    self.gid_input.setText(config["gid"])
                    
            except Exception as e:
                print(f"Error loading config: {e}")
                
    def save_config(self):
        """Save current configuration"""
        config = {
            "username": self.username_input.text(),
            "output_folder": self.output_folder.text(),
            "organize_by_date": self.organize_by_date.isChecked(),
            "generate_logs": self.generate_logs.isChecked(),
            "process_data": self.process_data.isChecked(),
            "last_dataset": self.dataset_combo.currentText(),
            "bounding_box": self.bounding_box.text(),
            "gid": self.gid_input.text()
        }
        try:
            with open("mosdac_gui_config.json", 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def verify_credentials(self):
        """Verify user credentials"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Input Error", 
                              "Please enter both username and password")
            return
            
        self.verify_button.setEnabled(False)
        self.verify_button.setText("Verifying...")
        self.status_bar.showMessage("Verifying credentials...")
        
        class VerifyWorker(QThread):
            finished = pyqtSignal(bool, str)
            
            def __init__(self, downloader, username, password):
                super().__init__()
                self.downloader = downloader
                self.username = username
                self.password = password
                
            def run(self):
                success, message = self.downloader.authenticate(self.username, self.password)
                self.finished.emit(success, message)
                
        self.verify_worker = VerifyWorker(self.downloader, username, password)
        self.verify_worker.finished.connect(self.on_verification_complete)
        self.verify_worker.start()
        
    def on_verification_complete(self, success, message):
        """Handle verification result"""
        self.verify_button.setEnabled(True)
        self.verify_button.setText("Verify Credentials")
        
        if success:
            self.auth_status.setText("✓ VERIFIED")
            self.auth_status.setStyleSheet("color: #4CAF50; font-weight: bold; padding: 5px;")
            self.user_info.setText(f"Welcome, {self.downloader.username}!")
            self.user_info.setStyleSheet("color: #4CAF50; padding: 5px;")
            
            self.tab_widget.setTabEnabled(1, True)
            self.tab_widget.setCurrentIndex(1)
            
            self.refresh_datasets()
            
            self.status_bar.showMessage(f"Authenticated as {self.downloader.username}")
            self.save_config()
            
        else:
            self.auth_status.setText("✗ Authentication failed")
            self.auth_status.setStyleSheet("color: #f44336; font-weight: bold; padding: 5px;")
            self.user_info.setText("")
            
            QMessageBox.warning(self, "Authentication Failed", message)
            self.status_bar.showMessage("Authentication failed")
            
    def refresh_datasets(self):
        """Refresh dataset list"""
        if not self.downloader.is_authenticated:
            QMessageBox.warning(self, "Not Authenticated", 
                              "Please authenticate first before loading datasets")
            return
            
        self.refresh_datasets_button.setEnabled(False)
        self.refresh_datasets_button.setText("Loading...")
        self.status_bar.showMessage("Loading datasets...")
        
        class DatasetWorker(QThread):
            finished = pyqtSignal(list)
            
            def __init__(self, downloader):
                super().__init__()
                self.downloader = downloader
                
            def run(self):
                datasets = self.downloader.get_datasets()
                self.finished.emit(datasets)
                
        self.dataset_worker = DatasetWorker(self.downloader)
        self.dataset_worker.finished.connect(self.on_datasets_loaded)
        self.dataset_worker.start()
        
    def on_datasets_loaded(self, datasets):
        """Handle loaded datasets"""
        self.refresh_datasets_button.setEnabled(True)
        self.refresh_datasets_button.setText("↻ Load Datasets")
        
        current_text = self.dataset_combo.currentText()
        self.dataset_combo.clear()
        
        if not datasets:
            self.dataset_combo.addItem("No datasets available - type custom ID")
            self.status_bar.showMessage("No datasets available - you can type a custom dataset ID")
            return
            
        for dataset in datasets:
            display_text = f"{dataset['title']} [{dataset['id']}]"
            self.dataset_combo.addItem(display_text, dataset['id'])
            
        if current_text:
            index = self.dataset_combo.findText(current_text)
            if index >= 0:
                self.dataset_combo.setCurrentIndex(index)
            else:
                self.dataset_combo.setCurrentText(current_text)
            
        self.status_bar.showMessage(f"Loaded {len(datasets)} datasets")
        self.add_log(f"Loaded {len(datasets)} datasets from MOSDAC catalogue")
        
    def on_bbox_changed(self, text):
        """Validate bounding box"""
        if text:
            parts = text.split(',')
            if len(parts) == 4:
                try:
                    for part in parts:
                        float(part.strip())
                    self.bounding_box.setStyleSheet("border: 1px solid #4CAF50;")
                    return
                except:
                    pass
            self.bounding_box.setStyleSheet("border: 1px solid #FF9800;")
        else:
            self.bounding_box.setStyleSheet("")
        
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder.setText(folder)
            
    def start_download(self):
        """Start the download process"""
        if not self.downloader.is_authenticated:
            QMessageBox.warning(self, "Not Authenticated", 
                              "Please authenticate first")
            return
            
        dataset_text = self.dataset_combo.currentText()
        if not dataset_text or dataset_text == "No datasets available - type custom ID":
            QMessageBox.warning(self, "Input Error", 
                              "Please select or enter a dataset ID")
            return
            
        dataset_id = self.dataset_combo.currentData()
        if not dataset_id:
            dataset_id = dataset_text
            
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        
        if start_date > end_date:
            QMessageBox.warning(self, "Date Error", 
                              "Start date must be before end date")
            return
            
        bounding_box = self.bounding_box.text().strip()
        gid = self.gid_input.text().strip()
        count = self.count_input.value()
        
        if bounding_box:
            parts = bounding_box.split(',')
            if len(parts) == 4:
                try:
                    for part in parts:
                        float(part.strip())
                except:
                    QMessageBox.warning(self, "Invalid Bounding Box", 
                                      "Please enter a valid bounding box")
                    return
            else:
                QMessageBox.warning(self, "Invalid Bounding Box", 
                                  "Please enter a valid bounding box")
                return
        
        output_folder = self.output_folder.text().strip()
        if not output_folder:
            output_folder = os.getcwd()
            
        self.downloader.download_path = output_folder
        self.downloader.use_date_structure = self.organize_by_date.isChecked()
        self.downloader.downloaded_files = []
        self.downloader.prefer_geotiff = True
        
        if self.generate_logs.isChecked():
            self.downloader.setup_logging(os.path.join(output_folder, "error_logs"))
        else:
            self.downloader.generate_logs = False
            
        self.download_button.setEnabled(False)
        self.download_button.setText("Downloading...")
        
        self.tab_widget.setTabEnabled(3, True)
        
        self.log_text.clear()
        self.add_log("=== MOSDAC Data Download Started ===")
        self.add_log(f"Dataset: {dataset_id}")
        self.add_log(f"Date Range: {start_date} to {end_date}")
        self.add_log("Priority: GeoTIFF files will be downloaded first")
        if bounding_box:
            self.add_log(f"Bounding Box: {bounding_box}")
        if gid:
            self.add_log(f"gId: {gid}")
        if count > 0:
            self.add_log(f"File Count: {count}")
        else:
            self.add_log(f"File Count: All")
        self.add_log(f"Output Folder: {output_folder}")
        self.add_log("")
        
        self.download_worker = DownloadWorker(
            self.downloader, dataset_id, start_date, end_date,
            bounding_box, gid, count, self.process_data.isChecked()
        )
        
        self.download_worker.progress_signal.connect(self.update_progress)
        self.download_worker.log_signal.connect(self.add_log)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.error_signal.connect(self.on_download_error)
        self.download_worker.processing_signal.connect(self.on_processing_complete)
        
        self.download_worker.start()
        
        self.save_config()
        self.tab_widget.setCurrentIndex(3)
        
    def update_progress(self, file_num, total_files, downloaded, total_size):
        """Update progress"""
        if total_files > 0:
            progress = (file_num / total_files) * 100
            self.progress_bar.setValue(int(progress))
            
            size_mb = total_size / (1024 * 1024)
            self.status_label.setText(
                f"Downloading file {file_num}/{total_files} ({size_mb:.1f} MB)"
            )
            
    def add_log(self, message):
        """Add log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        self.log_text.append(log_line)
        
        if self.auto_scroll.isChecked():
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)
            
    def clear_log(self):
        """Clear log"""
        self.log_text.clear()
        
    def save_log(self):
        """Save log"""
        if not self.log_text.toPlainText():
            QMessageBox.information(self, "Log Empty", "No log content to save")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Log File", 
            f"download_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Log Saved", f"Log saved to {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Save Error", f"Could not save log: {str(e)}")
                
    def on_processing_complete(self, results):
        """Handle processing completion"""
        self.add_log("Data processing and visualization completed")
        
        self.tab_widget.setTabEnabled(2, True)
        self.visualization_tab.update_plots(results)
        self.tab_widget.setCurrentIndex(2)
        
        QMessageBox.information(self, "Processing Complete", 
                              "Data processing and visualization completed!\n\n"
                              "Plots have been saved to the 'plots' folder in your output directory.\n"
                              "You can also view them in the Visualization tab.")
        
    def on_download_finished(self, success, downloaded, skipped, time_taken):
        """Handle download completion"""
        self.download_button.setEnabled(True)
        self.download_button.setText("🔍 Search & Start Download")
        self.progress_bar.setValue(100)
        
        if time_taken >= 3600:
            time_str = f"{time_taken/3600:.1f} hours"
        elif time_taken >= 60:
            time_str = f"{time_taken/60:.1f} minutes"
        else:
            time_str = f"{time_taken:.1f} seconds"
            
        self.add_log("")
        self.add_log("=== Download Summary ===")
        self.add_log(f"Files downloaded: {downloaded}")
        self.add_log(f"Files skipped: {skipped}")
        self.add_log(f"Total time: {time_str}")
        
        self.status_label.setText(f"Download complete: {downloaded} files downloaded, {skipped} skipped")
        self.status_bar.showMessage("Download completed")
        
        if not self.process_data.isChecked():
            QMessageBox.information(self, "Download Complete", 
                                  f"Download completed!\n\n"
                                  f"Files downloaded: {downloaded}\n"
                                  f"Files skipped: {skipped}\n"
                                  f"Time taken: {time_str}")
        
        self.downloader.logout()
        self.add_log("Logged out from MOSDAC")
        
    def on_download_error(self, error_message):
        """Handle download error"""
        self.download_button.setEnabled(True)
        self.download_button.setText("🔍 Search & Start Download")
        
        self.add_log(f"ERROR: {error_message}")
        self.status_label.setText(f"Error: {error_message}")
        self.status_bar.showMessage("Download failed")
        
        QMessageBox.critical(self, "Download Error", 
                           f"Download failed:\n{error_message}")
        
    def closeEvent(self, event):
        """Handle window close"""
        if self.download_worker and self.download_worker.isRunning():
            reply = QMessageBox.question(
                self, "Download in Progress",
                "A download is still in progress. Are you sure you want to exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
                
            self.download_worker.stop()
            self.download_worker.wait()
            
        if self.downloader.is_authenticated:
            self.downloader.logout()
            
        self.save_config()
        event.accept()


def main():
    """Main application entry point"""
    # Check for required packages
    required_packages = {
        'xarray': 'xarray',
        'matplotlib': 'matplotlib',
        'scipy': 'scipy',
        'pandas': 'pandas',
    }
    
    missing_packages = []
    for package, install_name in required_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(install_name)
    
    if missing_packages:
        print("\n" + "="*60)
        print("Some optional packages are missing for full functionality:")
        for pkg in missing_packages:
            print(f"  - {pkg}")
        print("\nInstall them using:")
        print(f"  pip install {' '.join(missing_packages)}")
        print("The application will still work with basic functionality.")
        print("="*60 + "\n")
    
    # Check for GeoTIFF support
    if not HAS_RASTERIO:
        print("\n" + "="*60)
        print("WARNING: Rasterio not installed. GeoTIFF support is limited.")
        print("Install rasterio for GeoTIFF support:")
        print("  pip install rasterio")
        print("="*60 + "\n")
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setWindowIcon(QIcon())
    
    window = MOSDACGui()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()