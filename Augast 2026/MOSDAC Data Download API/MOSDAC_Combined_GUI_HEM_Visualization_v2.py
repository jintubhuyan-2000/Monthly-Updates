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
try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False
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

# Embedded OSM map support
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    print("PyQtWebEngine is not installed. Embedded OSM map will be unavailable.")

import zipfile
import xml.etree.ElementTree as ET

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
    """Unified processor: generic GeoTIFF/NetCDF plus MOSDAC HEM_DLY analysis."""

    def __init__(self):
        self.data=None; self.lat=None; self.lon=None; self.time=None
        self.variable_name=None; self.log_callback=None; self.is_geotiff=False

    def set_log_callback(self, callback): self.log_callback=callback
    def add_log(self, message):
        if self.log_callback: self.log_callback(message)
        else: print(f"[Processor] {message}")

    def load_geotiff(self, file_path):
        try:
            if not HAS_RASTERIO:
                self.add_log("Rasterio not installed. Install: pip install rasterio"); return None
            with rasterio.open(file_path) as src:
                data=src.read(1)
                if src.nodata is not None: data=np.ma.masked_where(data==src.nodata,data)
                else: data=np.ma.masked_invalid(data)
                self.data=data[np.newaxis,:,:]
                self.lat=np.arange(src.height)*src.transform.e+src.transform.f
                self.lon=np.arange(src.width)*src.transform.a+src.transform.c
                self.variable_name=os.path.basename(file_path); self.is_geotiff=True
                self.add_log(f"Loaded GeoTIFF: {os.path.basename(file_path)}")
                return self.data
        except Exception as e:
            self.add_log(f"Error loading GeoTIFF: {e}"); return None

    def load_netcdf(self,file_path):
        try:
            if not HAS_XARRAY: return None
            ds=xr.open_dataset(file_path,engine='netcdf4')
            vars_=[v for v in ds.variables if v not in ds.dims]
            if not vars_: ds.close(); return None
            v=vars_[0]; data=ds[v].values
            lat=lon=t=None
            for c in ('lat','latitude','y'):
                if c in ds.coords: lat=ds[c].values; break
            for c in ('lon','longitude','x'):
                if c in ds.coords: lon=ds[c].values; break
            for c in ('time','Time'):
                if c in ds.coords: t=ds[c].values; break
            self.data,self.lat,self.lon,self.time=data,lat,lon,t
            self.variable_name=v; self.is_geotiff=False; ds.close()
            self.add_log(f"Loaded NetCDF: {os.path.basename(file_path)}")
            return data
        except Exception as e:
            self.add_log(f"Error loading NetCDF: {e}"); return None

    def detect_and_load(self,file_path):
        ext=os.path.splitext(file_path)[1].lower()
        if ext in ('.h5','.hdf5','.hdf') and HAS_H5PY:
            try:
                with h5py.File(file_path,'r') as h5:
                    if all(k in h5 for k in ('HEM_DLY','Latitude','Longitude')):
                        return self.load_hem(file_path)
            except Exception as e: self.add_log(f"HDF5 inspection failed: {e}")
        if ext in ('.tif','.tiff'): return self.load_geotiff(file_path)
        if ext in ('.nc','.nc4'): return self.load_netcdf(file_path)
        return None

    @staticmethod
    def _attr(ds,name,default):
        try: return float(np.asarray(ds.attrs.get(name,default)).flatten()[0])
        except Exception: return float(default)

    def load_hem(self,filename):
        with h5py.File(filename,'r') as h5:
            rds=h5['HEM_DLY']; rainfall=np.squeeze(rds[:]).astype(float)
            rf=self._attr(rds,'_FillValue',-999.0)
            rainfall[(rainfall==rf)|(~np.isfinite(rainfall))|(rainfall<0)]=np.nan
            lds=h5['Latitude']; lat=lds[:].astype(float)
            lf=self._attr(lds,'_FillValue',32767); lat[lat==lf]=np.nan
            lat=lat*self._attr(lds,'scale_factor',0.01)+self._attr(lds,'add_offset',0.0)
            lat[~np.isfinite(lat)]=np.nan
            ods=h5['Longitude']; lon=ods[:].astype(float)
            of=self._attr(ods,'_FillValue',32767); lon[lon==of]=np.nan
            lon=lon*self._attr(ods,'scale_factor',0.01)+self._attr(ods,'add_offset',0.0)
            lon[~np.isfinite(lon)]=np.nan
        if rainfall.shape!=lat.shape or rainfall.shape!=lon.shape:
            raise ValueError(f"HEM/coordinate shape mismatch: {rainfall.shape}, {lat.shape}, {lon.shape}")
        self.data=rainfall[None,:,:]; self.lat=lat; self.lon=lon
        self.variable_name='HEM_DLY'; self.is_geotiff=False
        return self.data

    @staticmethod
    def hem_date(filename):
        m=re.search(r'_(\d{1,2}[A-Za-z]{3}\d{4})_',os.path.basename(filename))
        if not m: m=re.search(r'(\d{1,2}[A-Za-z]{3}\d{4})',os.path.basename(filename))
        if not m: return None
        try: return pd.to_datetime(m.group(1),format='%d%b%Y')
        except Exception: return None

    @staticmethod
    def crop(data,lat,lon):
        ok=np.isfinite(lat)&np.isfinite(lon)
        rows=np.where(np.any(ok,axis=1))[0]; cols=np.where(np.any(ok,axis=0))[0]
        if not rows.size or not cols.size: raise ValueError("No valid geographic coordinates")
        a,b,c,d=rows.min(),rows.max()+1,cols.min(),cols.max()+1
        return data[a:b,c:d],lat[a:b,c:d],lon[a:b,c:d]

    @staticmethod
    def stats(r,lat,lon):
        ok=np.isfinite(r)&np.isfinite(lat)&np.isfinite(lon); v=r[ok]
        if not v.size:
            return dict(mean_rainfall_mm_day=np.nan,median_rainfall_mm_day=np.nan,
                        minimum_rainfall_mm_day=np.nan,maximum_rainfall_mm_day=np.nan,
                        std_rainfall_mm_day=np.nan,valid_pixels=0,total_pixels=r.size,coverage_percent=0)
        return dict(mean_rainfall_mm_day=float(v.mean()),median_rainfall_mm_day=float(np.median(v)),
                    minimum_rainfall_mm_day=float(v.min()),maximum_rainfall_mm_day=float(v.max()),
                    std_rainfall_mm_day=float(v.std()),valid_pixels=int(v.size),
                    total_pixels=int(r.size),coverage_percent=float(v.size/r.size*100))

    @staticmethod
    def vmax(arrays):
        vals=[]
        for a in arrays:
            v=a[np.isfinite(a)]
            if v.size: vals.append(np.percentile(v,99))
        x=max(vals) if vals else 100.
        if x<=10: x=np.ceil(x)
        elif x<=50: x=np.ceil(x/5)*5
        elif x<=100: x=np.ceil(x/10)*10
        elif x<=500: x=np.ceil(x/25)*25
        else: x=np.ceil(x/50)*50
        return max(float(x),1.0)

    def _map(self,data,lat,lon,title,label,path,vmax):
        d,la,lo=self.crop(data,lat,lon)
        fig,ax=plt.subplots(figsize=(12,9))
        m=ax.pcolormesh(lo,la,d,shading='auto',vmin=0,vmax=vmax)
        cb=fig.colorbar(m,ax=ax,pad=.02,shrink=.85); cb.set_label(label)
        ax.set_xlabel('Longitude (°E)'); ax.set_ylabel('Latitude (°N)')
        ax.set_title(title,fontsize=14,fontweight='bold'); ax.grid(True,alpha=.3,linestyle='--')
        fig.tight_layout(); fig.savefig(path,dpi=250,bbox_inches='tight'); plt.close(fig)

    def _hem_analysis(self,file_list,output_dir):
        if not HAS_H5PY: return None
        hfiles=[]
        for f in file_list:
            if os.path.splitext(f)[1].lower() not in ('.h5','.hdf5','.hdf'): continue
            try:
                with h5py.File(f,'r') as h5:
                    if all(k in h5 for k in ('HEM_DLY','Latitude','Longitude')): hfiles.append(f)
            except Exception: pass
        if not hfiles: return None
        hfiles.sort(key=lambda f:self.hem_date(f) or pd.Timestamp.max)
        daily=os.path.join(output_dir,'01_DAILY_SPATIAL_MAPS'); summary=os.path.join(output_dir,'02_SUMMARY')
        csvdir=os.path.join(output_dir,'03_CSV'); npydir=os.path.join(output_dir,'04_NUMPY')
        for d in (daily,summary,csvdir,npydir): os.makedirs(d,exist_ok=True)
        rec=[]; arrays=[]; dates=[]; lat0=lon0=None
        for f in hfiles:
            dt=self.hem_date(f)
            if dt is None: continue
            try:
                self.load_hem(f); r=self.data[0].copy(); la=self.lat.copy(); lo=self.lon.copy()
                s=self.stats(r,la,lo); rec.append({'date':dt,**s,'file':f,'rainfall_dataset':'HEM_DLY','rainfall_units':'mm/day'})
                arrays.append(r); dates.append(dt)
                if lat0 is None: lat0,lon0=la,lo
            except Exception as e: self.add_log(f"ERROR processing {os.path.basename(f)}: {e}")
        if not rec: return None
        df=pd.DataFrame(rec).sort_values('date').reset_index(drop=True)
        df.to_csv(os.path.join(csvdir,'MOSDAC_HEM_Daily_Rainfall.csv'),index=False)
        common=self.vmax(arrays)
        for r,dt in zip(arrays,dates):
            self._map(r,lat0,lon0,f"MOSDAC INSAT HEM Daily Precipitation\n{dt:%d %B %Y}",
                      'Daily precipitation (mm/day)',os.path.join(daily,f'MOSDAC_Rainfall_{dt:%Y%m%d}.png'),common)
        mean=maxi=total=None
        if len({a.shape for a in arrays})==1:
            stack=np.stack(arrays)
            mean=np.nanmean(stack,axis=0); maxi=np.nanmax(stack,axis=0); total=np.nansum(stack,axis=0)
            np.save(os.path.join(npydir,'Mean_Daily_Rainfall.npy'),mean)
            np.save(os.path.join(npydir,'Maximum_Daily_Rainfall.npy'),maxi)
            np.save(os.path.join(npydir,'Accumulated_Rainfall.npy'),total)
            st=f"{df.date.min():%d %B %Y} – {df.date.max():%d %B %Y}"
            self._map(mean,lat0,lon0,f"MOSDAC Mean Daily Precipitation\n{st}",
                      'Mean precipitation (mm/day)',os.path.join(summary,'Mean_Daily_Precipitation.png'),common)
            self._map(maxi,lat0,lon0,f"MOSDAC Maximum Daily Precipitation\n{st}",
                      'Maximum daily precipitation (mm/day)',os.path.join(summary,'Maximum_Daily_Precipitation.png'),self.vmax([maxi]))
            self._map(total,lat0,lon0,f"MOSDAC Accumulated Precipitation\n{st}",
                      'Accumulated precipitation (mm)',os.path.join(summary,'Accumulated_Precipitation.png'),self.vmax([total]))
        fig,ax=plt.subplots(figsize=(12,6)); ax.plot(df.date,df.mean_rainfall_mm_day,marker='o',linewidth=2)
        ax.set_xlabel('Date'); ax.set_ylabel('Spatial mean precipitation (mm/day)'); ax.set_title('MOSDAC Daily Spatial Mean Precipitation',fontweight='bold')
        ax.grid(True,alpha=.3,linestyle='--'); fig.autofmt_xdate(); fig.tight_layout()
        mean_ts=os.path.join(summary,'Daily_Spatial_Mean_Rainfall.png'); fig.savefig(mean_ts,dpi=250,bbox_inches='tight'); plt.close(fig)
        fig,ax=plt.subplots(figsize=(12,6)); ax.plot(df.date,df.maximum_rainfall_mm_day,marker='o',linewidth=2)
        ax.set_xlabel('Date'); ax.set_ylabel('Maximum precipitation (mm/day)'); ax.set_title('MOSDAC Daily Maximum Precipitation',fontweight='bold')
        ax.grid(True,alpha=.3,linestyle='--'); fig.autofmt_xdate(); fig.tight_layout()
        max_ts=os.path.join(summary,'Daily_Spatial_Maximum_Rainfall.png'); fig.savefig(max_ts,dpi=250,bbox_inches='tight'); plt.close(fig)
        summary_txt=os.path.join(csvdir,'Rainfall_Summary.txt')
        with open(summary_txt,'w',encoding='utf-8') as f:
            f.write('MOSDAC INSAT HEM DAILY PRECIPITATION ANALYSIS\n'+'='*70+'\n\n')
            f.write(f"Period: {df.date.min():%Y-%m-%d} to {df.date.max():%Y-%m-%d}\nFiles processed: {len(df)}\nRainfall units: mm/day\n\n")
            f.write(f"Mean of daily spatial means: {df.mean_rainfall_mm_day.mean():.4f} mm/day\n")
            f.write(f"Maximum daily spatial mean: {df.mean_rainfall_mm_day.max():.4f} mm/day\n")
            f.write(f"Maximum individual pixel rainfall: {df.maximum_rainfall_mm_day.max():.4f} mm/day\n")
            f.write(f"Accumulated rainfall based on daily spatial means: {df.mean_rainfall_mm_day.sum():.4f} mm\n")
        return {'type':'HEM_DLY','dates':dates,'df':df,'daily_arrays':arrays,'latitude':lat0,'longitude':lon0,
                'period_mean':mean,'period_max':maxi,'period_total':total,'common_vmax':common,
                'daily_map_dir':daily,'summary_dir':summary,'csv_dir':csvdir,'npy_dir':npydir,
                'csv_file':os.path.join(csvdir,'MOSDAC_HEM_Daily_Rainfall.csv'),'summary_file':summary_txt,
                'mean_ts':mean_ts,'max_ts':max_ts}

    def process_all_files(self,file_list,output_dir=None,bounding_box=None):
        output_dir=output_dir or os.getcwd(); os.makedirs(output_dir,exist_ok=True)
        hem=self._hem_analysis(file_list,output_dir)
        if hem:
            df=hem['df']
            return {'mode':'HEM_DLY','hem_analysis':hem,
                    'time_series':[df.mean_rainfall_mm_day.to_numpy()],
                    'spatial_maps':[],'combined_plots':[],
                    'stats':{'mean':float(df.mean_rainfall_mm_day.mean()),'std':float(df.mean_rainfall_mm_day.std(ddof=0)),
                             'min':float(df.mean_rainfall_mm_day.min()),'max':float(df.mean_rainfall_mm_day.max()),'count':len(df)},
                    'file_info':[{'name':os.path.basename(f),'path':f} for f in file_list]}
        self.add_log('No HEM_DLY files detected. Generic visualization is not available for this download.')
        return {'mode':'GENERIC','time_series':[],'spatial_maps':[],'combined_plots':[],'stats':{},'file_info':[]}


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
    """Interactive visualization of HEM products."""
    def __init__(self,parent=None):
        super().__init__(parent); self.results=None; self.init_ui()
    def init_ui(self):
        layout=QVBoxLayout(self); row=QHBoxLayout()
        row.addWidget(QLabel("Visualization:"))
        self.plot_type_combo=QComboBox()
        self.plot_type_combo.addItems(["Daily Mean Time Series","Daily Maximum Time Series","Daily Spatial Map","Period Mean Map","Period Maximum Map","Accumulated Rainfall Map","Statistics"])
        self.plot_type_combo.currentTextChanged.connect(self.refresh_plots); row.addWidget(self.plot_type_combo)
        row.addWidget(QLabel("Day:")); self.day_combo=QComboBox(); self.day_combo.currentIndexChanged.connect(self.refresh_plots); row.addWidget(self.day_combo)
        row.addStretch(); b=QPushButton("Save Current Plot"); b.clicked.connect(self.save_current_plot); row.addWidget(b)
        layout.addLayout(row)
        self.figure=Figure(figsize=(12,8)); self.canvas=FigureCanvas(self.figure); self.canvas.setMinimumHeight(550); layout.addWidget(self.canvas)
        self.info_label=QLabel("No data available for visualization"); layout.addWidget(self.info_label)
    def update_plots(self,results):
        self.results=results; self.day_combo.blockSignals(True); self.day_combo.clear()
        h=results.get('hem_analysis') if results else None
        if h:
            for i,d in enumerate(h['dates']): self.day_combo.addItem(d.strftime('%d %B %Y'),i)
        self.day_combo.blockSignals(False); self.refresh_plots()
    def refresh_plots(self):
        self.figure.clear(); h=self.results.get('hem_analysis') if self.results else None
        if not h:
            ax=self.figure.add_subplot(111); ax.text(.5,.5,'No HEM visualization available',ha='center',va='center'); ax.axis('off'); self.canvas.draw(); return
        k=self.plot_type_combo.currentText()
        if k=="Daily Mean Time Series": self.ts('mean_rainfall_mm_day','Daily Spatial Mean Precipitation','Spatial mean precipitation (mm/day)')
        elif k=="Daily Maximum Time Series": self.ts('maximum_rainfall_mm_day','Daily Maximum Precipitation','Maximum precipitation (mm/day)')
        elif k=="Daily Spatial Map": self.daily_map()
        elif k=="Period Mean Map": self.map_array(h['period_mean'],'MOSDAC Mean Daily Precipitation','Mean precipitation (mm/day)',h['common_vmax'])
        elif k=="Period Maximum Map": self.map_array(h['period_max'],'MOSDAC Maximum Daily Precipitation','Maximum daily precipitation (mm/day)',DataProcessor.vmax([h['period_max']]) if h['period_max'] is not None else 1)
        elif k=="Accumulated Rainfall Map": self.map_array(h['period_total'],'MOSDAC Accumulated Precipitation','Accumulated precipitation (mm)',DataProcessor.vmax([h['period_total']]) if h['period_total'] is not None else 1)
        else: self.statistics()
        self.canvas.draw()
    def ts(self,col,title,ylabel):
        df=self.results['hem_analysis']['df']; ax=self.figure.add_subplot(111); ax.plot(df.date,df[col],marker='o',linewidth=2,markersize=6)
        ax.set_title(title,fontweight='bold'); ax.set_xlabel('Date'); ax.set_ylabel(ylabel); ax.grid(True,alpha=.3,linestyle='--'); self.figure.autofmt_xdate()
        self.info_label.setText(f"{len(df)} daily observations")
    def daily_map(self):
        h=self.results['hem_analysis']; i=self.day_combo.currentData(); i=0 if i is None else int(i); i=max(0,min(i,len(h['daily_arrays'])-1))
        self.map_array(h['daily_arrays'][i],f"MOSDAC HEM Daily Precipitation\n{h['dates'][i]:%d %B %Y}",'Daily precipitation (mm/day)',h['common_vmax'])
    def map_array(self,data,title,label,vmax):
        ax=self.figure.add_subplot(111)
        if data is None: ax.text(.5,.5,'Multi-day product unavailable',ha='center',va='center'); ax.axis('off'); return
        h=self.results['hem_analysis']; d,lat,lon=DataProcessor.crop(data,h['latitude'],h['longitude'])
        m=ax.pcolormesh(lon,lat,d,shading='auto',vmin=0,vmax=max(float(vmax),1e-9)); self.figure.colorbar(m,ax=ax,pad=.02,shrink=.85).set_label(label)
        ax.set_xlabel('Longitude (°E)'); ax.set_ylabel('Latitude (°N)'); ax.set_title(title,fontweight='bold'); ax.grid(True,alpha=.3,linestyle='--'); self.info_label.setText(label)
    def statistics(self):
        df=self.results['hem_analysis']['df']; ax=self.figure.add_subplot(111); ax.axis('off'); a=df.loc[df.mean_rainfall_mm_day.idxmax()]; b=df.loc[df.maximum_rainfall_mm_day.idxmax()]
        txt=("MOSDAC INSAT HEM DAILY PRECIPITATION\n\n"+f"Files processed: {len(df)}\n"+f"Period: {df.date.min():%d %B %Y} – {df.date.max():%d %B %Y}\n\n"+f"Mean of daily spatial means: {df.mean_rainfall_mm_day.mean():.4f} mm/day\n"+f"Maximum daily spatial mean: {df.mean_rainfall_mm_day.max():.4f} mm/day\n"+f"Date of maximum spatial mean: {a.date:%d %B %Y}\n\n"+f"Maximum individual pixel rainfall: {df.maximum_rainfall_mm_day.max():.4f} mm/day\n"+f"Date of maximum pixel rainfall: {b.date:%d %B %Y}\n"+f"Accumulated rainfall from daily spatial means: {df.mean_rainfall_mm_day.sum():.4f} mm")
        ax.text(.08,.5,txt,transform=ax.transAxes,fontsize=13,va='center',bbox=dict(boxstyle='round',facecolor='white',alpha=.9)); self.info_label.setText("Statistics summary")
    def save_current_plot(self):
        if not self.results: QMessageBox.warning(self,'No Plot','No plot available to save'); return
        path,_=QFileDialog.getSaveFileName(self,'Save Plot',f"plot_{datetime.now():%Y%m%d_%H%M%S}.png",'PNG Files (*.png);;PDF Files (*.pdf);;All Files (*.*)')
        if path:
            try: self.figure.savefig(path,dpi=300,bbox_inches='tight'); QMessageBox.information(self,'Plot Saved',f'Plot saved to:\n{path}')
            except Exception as e: QMessageBox.warning(self,'Save Error',f'Could not save plot: {e}')


class OSMMapWidget(QWidget):
    """
    Embedded OpenStreetMap selector.

    Features:
      - OSM map stays inside the Download tab, on the right.
      - Rectangle selection returns min_lon,min_lat,max_lon,max_lat.
      - Drawing temporarily disables map dragging so the map does not move
        while the rectangle is being drawn.
      - KML/KMZ bounds can be loaded and displayed on the same map.
    """

    bounds_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_row = QHBoxLayout()

        title = QLabel("OpenStreetMap – Extent Selector")
        title.setStyleSheet(
            "font-weight:bold; font-size:11pt; padding:4px;"
        )
        title_row.addWidget(title)

        title_row.addStretch()

        self.load_vector_button = QPushButton("📂 Load KML/KMZ")
        self.load_vector_button.setToolTip(
            "Load a KML/KMZ file and use its geographic extent"
        )
        self.load_vector_button.clicked.connect(self.load_kml_kmz)
        self.load_vector_button.setStyleSheet("""
            QPushButton {
                background-color:#607D8B;
                color:white;
                padding:6px 10px;
                border-radius:4px;
            }
            QPushButton:hover { background-color:#546E7A; }
        """)
        title_row.addWidget(self.load_vector_button)

        self.clear_extent_button = QPushButton("✕ Clear")
        self.clear_extent_button.clicked.connect(self.clear_extent)
        self.clear_extent_button.setStyleSheet("""
            QPushButton {
                background-color:#9E9E9E;
                color:white;
                padding:6px 10px;
                border-radius:4px;
            }
            QPushButton:hover { background-color:#757575; }
        """)
        title_row.addWidget(self.clear_extent_button)

        layout.addLayout(title_row)

        self.map_status = QLabel(
            "Draw a rectangle on the map to select the latitude/longitude extent."
        )
        self.map_status.setWordWrap(True)
        self.map_status.setStyleSheet(
            "color:#546E7A; font-size:9pt; padding:3px;"
        )
        layout.addWidget(self.map_status)

        if not HAS_WEBENGINE:
            missing = QLabel(
                "Embedded OSM requires PyQtWebEngine.\n\n"
                "Install with:\n"
                "pip install PyQtWebEngine"
            )
            missing.setAlignment(Qt.AlignCenter)
            missing.setStyleSheet(
                "color:#c62828; padding:30px; font-weight:bold;"
            )
            layout.addWidget(missing, 1)
            self.web_view = None
            return

        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(500)
        layout.addWidget(self.web_view, 1)

        self.web_view.setHtml(self._build_map_html())

    def _build_map_html(self):
        # Leaflet + Leaflet.draw are loaded from their public CDNs.
        # OSM is the base map. The drawing code explicitly disables map
        # dragging during rectangle drawing.
        return r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<link rel="stylesheet"
 href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>

<link rel="stylesheet"
 href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css"/>

<style>
html, body, #map {
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
}
.leaflet-control-attribution {
    font-size: 9px;
}
</style>
</head>

<body>
<div id="map"></div>

<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>

<script>
let map = L.map('map', {
    center: [23.5, 80.0],
    zoom: 5,
    zoomControl: true,
    dragging: true
});

L.tileLayer(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }
).addTo(map);

let drawnItems = new L.FeatureGroup();
map.addLayer(drawnItems);

let currentRectangle = null;

let drawControl = new L.Control.Draw({
    position: 'topleft',
    draw: {
        polyline: false,
        polygon: false,
        circle: false,
        circlemarker: false,
        marker: false,
        rectangle: {
            shapeOptions: {
                color: '#ff6600',
                weight: 3,
                fillOpacity: 0.15
            }
        }
    },
    edit: {
        featureGroup: drawnItems,
        remove: true
    }
});
map.addControl(drawControl);

// IMPORTANT:
// Disable map dragging while drawing. This prevents the OSM map from
// shifting underneath the cursor during rectangle selection.
map.on(L.Draw.Event.DRAWSTART, function(e) {
    if (e.layerType === 'rectangle') {
        map.dragging.disable();
        map.doubleClickZoom.disable();
        map.scrollWheelZoom.disable();
    }
});

map.on(L.Draw.Event.DRAWSTOP, function(e) {
    map.dragging.enable();
    map.doubleClickZoom.enable();
    map.scrollWheelZoom.enable();
});

map.on(L.Draw.Event.CREATED, function(e) {
    drawnItems.clearLayers();

    if (currentRectangle) {
        map.removeLayer(currentRectangle);
    }

    currentRectangle = e.layer;
    drawnItems.addLayer(currentRectangle);

    const b = currentRectangle.getBounds();

    const minLat = b.getSouth();
    const minLon = b.getWest();
    const maxLat = b.getNorth();
    const maxLon = b.getEast();

    const bbox =
        minLon.toFixed(8) + ',' +
        minLat.toFixed(8) + ',' +
        maxLon.toFixed(8) + ',' +
        maxLat.toFixed(8);

    if (window.pybridge && window.pybridge.sendBounds) {
        window.pybridge.sendBounds(bbox);
    }
});

map.on(L.Draw.Event.EDITED, function(e) {
    e.layers.eachLayer(function(layer) {
        const b = layer.getBounds();

        const bbox =
            b.getWest().toFixed(8) + ',' +
            b.getSouth().toFixed(8) + ',' +
            b.getEast().toFixed(8) + ',' +
            b.getNorth().toFixed(8);

        if (window.pybridge && window.pybridge.sendBounds) {
            window.pybridge.sendBounds(bbox);
        }
    });
});

function showBounds(minLon, minLat, maxLon, maxLat) {
    drawnItems.clearLayers();

    if (currentRectangle) {
        map.removeLayer(currentRectangle);
    }

    currentRectangle = L.rectangle(
        [[minLat, minLon], [maxLat, maxLon]],
        {
            color: '#1976D2',
            weight: 3,
            fillOpacity: 0.15
        }
    ).addTo(drawnItems);

    map.fitBounds(
        [[minLat, minLon], [maxLat, maxLon]],
        {padding: [20, 20]}
    );
}

function clearBounds() {
    drawnItems.clearLayers();

    if (currentRectangle) {
        map.removeLayer(currentRectangle);
        currentRectangle = null;
    }
}

window.showBounds = showBounds;
window.clearBounds = clearBounds;
</script>
</body>
</html>"""

    def send_bounds_to_map(self, bbox):
        if not self.web_view:
            return
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) != 4:
                return
            min_lon, min_lat, max_lon, max_lat = parts

            js = (
                "showBounds("
                f"{min_lon},{min_lat},{max_lon},{max_lat}"
                ");"
            )
            self.web_view.page().runJavaScript(js)
        except Exception:
            pass

    def clear_extent(self):
        self.bounds_selected.emit("")

        if self.web_view:
            self.web_view.page().runJavaScript("clearBounds();")

        self.map_status.setText(
            "Draw a rectangle on the map to select the latitude/longitude extent."
        )

    def set_bounds(self, bbox, source=""):
        self.bounds_selected.emit(bbox)

        if self.web_view:
            try:
                parts = [float(x.strip()) for x in bbox.split(",")]
                if len(parts) == 4:
                    min_lon, min_lat, max_lon, max_lat = parts
                    self.send_bounds_to_map(bbox)
                    self.map_status.setText(
                        f"{source + ': ' if source else ''}"
                        f"Extent: {min_lon:.6f}, {min_lat:.6f}, "
                        f"{max_lon:.6f}, {max_lat:.6f}"
                    )
            except Exception:
                pass

    def load_kml_kmz(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load KML / KMZ",
            "",
            "KML/KMZ Files (*.kml *.kmz);;KML Files (*.kml);;"
            "KMZ Files (*.kmz);;All Files (*.*)"
        )

        if not file_path:
            return

        try:
            bbox = self._extract_kml_kmz_bounds(file_path)

            if bbox is None:
                QMessageBox.warning(
                    self,
                    "No Coordinates Found",
                    "The selected KML/KMZ file does not contain "
                    "recognizable geographic coordinates."
                )
                return

            self.set_bounds(
                ",".join(f"{v:.8f}" for v in bbox),
                source=os.path.basename(file_path)
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "KML/KMZ Error",
                f"Could not read the selected file:\n\n{e}"
            )

    @staticmethod
    def _extract_kml_kmz_bounds(file_path):
        """
        Extract geographic bounds from common KML geometries without requiring
        fastkml/shapely. Supports Point, LineString, LinearRing, Polygon and
        MultiGeometry through their coordinate elements.
        """
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".kmz":
            with zipfile.ZipFile(file_path, "r") as z:
                kml_names = [
                    n for n in z.namelist()
                    if n.lower().endswith(".kml")
                ]

                if not kml_names:
                    raise ValueError("KMZ archive contains no KML file.")

                # Prefer doc.kml, otherwise use the first KML.
                kml_name = next(
                    (n for n in kml_names if os.path.basename(n).lower() == "doc.kml"),
                    kml_names[0]
                )
                xml_bytes = z.read(kml_name)

        elif ext == ".kml":
            with open(file_path, "rb") as f:
                xml_bytes = f.read()
        else:
            raise ValueError("Only .kml and .kmz files are supported.")

        root = ET.fromstring(xml_bytes)

        # KML namespace handling: search by local-name so files with different
        # namespace declarations still work.
        coords = []

        for elem in root.iter():
            if elem.tag.split("}")[-1].lower() != "coordinates":
                continue

            raw = (elem.text or "").strip()

            # KML coordinates are lon,lat[,alt], separated by whitespace.
            for token in re.split(r"\s+", raw):
                if not token:
                    continue

                parts = token.split(",")
                if len(parts) < 2:
                    continue

                try:
                    lon = float(parts[0])
                    lat = float(parts[1])

                    if -180 <= lon <= 180 and -90 <= lat <= 90:
                        coords.append((lon, lat))
                except ValueError:
                    continue

        if not coords:
            return None

        lons = [p[0] for p in coords]
        lats = [p[1] for p in coords]

        return (
            min(lons),
            min(lats),
            max(lons),
            max(lats)
        )


class MapBridge(QObject):
    """JavaScript -> PyQt bridge for the Leaflet map."""

    bounds_received = pyqtSignal(str)

    @pyqtSlot(str)
    def sendBounds(self, bbox):
        self.bounds_received.emit(bbox)



class MOSDACGui(QMainWindow):
    """Main GUI window for MOSDAC Downloader"""
    
    def __init__(self):
        super().__init__()
        self.downloader = MOSDACDownloader()
        self.download_worker = None
        self.map_bridge = None
        self.map_widget = None
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
        """Create Download tab with an embedded OSM extent selector."""
        download_tab = QWidget()
        self.tab_widget.addTab(download_tab, "Download")
        self.tab_widget.setTabEnabled(1, False)

        outer_layout = QHBoxLayout(download_tab)
        outer_layout.setSpacing(10)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)
        outer_layout.addWidget(splitter)

        # ==============================================================
        # LEFT: existing MOSDAC controls
        # ==============================================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(10, 10, 10, 10)

        info_label = QLabel(
            "⚠️ GeoTIFF files will be prioritized for download when available"
        )
        info_label.setStyleSheet(
            "color:#2196F3; font-weight:bold; padding:5px;"
            "background-color:#e3f2fd; border-radius:3px;"
        )
        left_layout.addWidget(info_label)

        dataset_group = QGroupBox("Search Parameters")
        dataset_layout = QGridLayout(dataset_group)
        dataset_layout.setVerticalSpacing(10)
        dataset_layout.setHorizontalSpacing(10)

        dataset_layout.addWidget(QLabel("Dataset ID:"), 0, 0)
        self.dataset_combo = QComboBox()
        self.dataset_combo.setEditable(True)
        self.dataset_combo.setPlaceholderText(
            "Enter dataset ID (e.g., 3RIMG_L2B_SST)"
        )

        for dataset in self.downloader.get_complete_datasets():
            display_text = f"{dataset['title']} [{dataset['id']}]"
            self.dataset_combo.addItem(display_text, dataset['id'])

        dataset_layout.addWidget(self.dataset_combo, 0, 1)

        self.refresh_datasets_button = QPushButton("↻ Load Datasets")
        self.refresh_datasets_button.setStyleSheet("""
            QPushButton {
                background-color:#2196F3;
                padding:5px 10px;
                font-size:9pt;
            }
            QPushButton:hover { background-color:#1976D2; }
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
        self.bounding_box.setPlaceholderText(
            "min_lon,min_lat,max_lon,max_lat"
        )
        self.bounding_box.textChanged.connect(self.on_bbox_changed)
        dataset_layout.addWidget(self.bounding_box, 3, 1, 1, 2)

        # A direct button is useful when the user wants to jump to the map.
        self.select_extent_button = QPushButton("🗺 Select Extent on OSM")
        self.select_extent_button.setStyleSheet("""
            QPushButton {
                background-color:#00897B;
                color:white;
                padding:7px 10px;
                border-radius:4px;
                font-weight:bold;
            }
            QPushButton:hover { background-color:#00796B; }
        """)
        self.select_extent_button.clicked.connect(
            lambda: self.focus_osm_map()
        )
        dataset_layout.addWidget(self.select_extent_button, 4, 1)

        self.load_kml_button = QPushButton("📂 Load KML/KMZ")
        self.load_kml_button.setStyleSheet("""
            QPushButton {
                background-color:#607D8B;
                color:white;
                padding:7px 10px;
                border-radius:4px;
                font-weight:bold;
            }
            QPushButton:hover { background-color:#546E7A; }
        """)
        self.load_kml_button.clicked.connect(
            self.load_kml_kmz_from_left
        )
        dataset_layout.addWidget(self.load_kml_button, 4, 2)

        dataset_layout.addWidget(QLabel("gId:"), 5, 0)
        self.gid_input = QLineEdit()
        self.gid_input.setPlaceholderText(
            "Geographic identifier (optional)"
        )
        dataset_layout.addWidget(self.gid_input, 5, 1, 1, 2)

        dataset_layout.addWidget(QLabel("File Count:"), 6, 0)
        self.count_input = QSpinBox()
        self.count_input.setRange(0, 10000)
        self.count_input.setValue(0)
        self.count_input.setSpecialValueText("All")
        dataset_layout.addWidget(self.count_input, 6, 1)

        help_label = QLabel(
            "Use the OSM map on the right to draw the extent, "
            "or load a KML/KMZ file."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet(
            "color:#7f8c8d; font-size:9pt; font-style:italic;"
        )
        dataset_layout.addWidget(help_label, 7, 0, 1, 3)

        left_layout.addWidget(dataset_group)

        output_group = QGroupBox("Output Settings")
        output_layout = QVBoxLayout(output_group)

        output_row = QHBoxLayout()
        output_label = QLabel("Output Folder:")
        output_label.setMinimumWidth(100)

        self.output_folder = QLineEdit()
        self.output_folder.setText(
            os.path.join(os.getcwd(), "MOSDAC_Data")
        )
        self.output_folder.setPlaceholderText("Select output folder")

        output_row.addWidget(output_label)
        output_row.addWidget(self.output_folder)

        browse_button = QPushButton("Browse...")
        browse_button.setStyleSheet("""
            QPushButton { background-color:#607D8B; }
            QPushButton:hover { background-color:#546E7A; }
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

        self.process_data = QCheckBox(
            "Process and visualize data after download"
        )
        self.process_data.setChecked(True)
        options_layout.addWidget(self.process_data)

        options_layout.addStretch()
        output_layout.addLayout(options_layout)

        left_layout.addWidget(output_group)

        download_row = QHBoxLayout()
        download_row.addStretch()

        self.download_button = QPushButton(
            "🔍 Search & Start Download"
        )
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color:#FF9800;
                color:white;
                padding:10px 30px;
                font-weight:bold;
                font-size:12pt;
                border-radius:4px;
                min-width:200px;
            }
            QPushButton:hover { background-color:#F57C00; }
            QPushButton:disabled { background-color:#cccccc; }
        """)
        self.download_button.clicked.connect(self.start_download)
        download_row.addWidget(self.download_button)

        left_layout.addLayout(download_row)

        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to download")
        self.status_label.setStyleSheet("color:#7f8c8d;")
        progress_layout.addWidget(self.status_label)

        left_layout.addWidget(progress_group)
        left_layout.addStretch()

        # ==============================================================
        # RIGHT: embedded OSM
        # ==============================================================
        self.map_widget = OSMMapWidget()
        self.map_bridge = MapBridge()

        if self.map_widget.web_view:
            channel = QWebChannel(self.map_widget.web_view.page())
            channel.registerObject("pybridge", self.map_bridge)
            self.map_widget.web_view.page().setWebChannel(channel)

            # Inject the bridge object into JavaScript after page load.
            # QWebChannel must be loaded by the page first.
            self.map_widget.web_view.loadFinished.connect(
                self._setup_map_bridge
            )

        self.map_bridge.bounds_received.connect(
            self.on_map_bounds_received
        )

        splitter.addWidget(left_widget)
        splitter.addWidget(self.map_widget)

        # Initial proportions: controls 45%, map 55%.
        splitter.setSizes([500, 600])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

    def _setup_map_bridge(self, ok):
        """Expose the PyQt bridge to the Leaflet JavaScript page."""
        if not ok or not self.map_widget.web_view:
            return

        js = """
        if (typeof QWebChannel !== 'undefined') {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                window.pybridge = channel.objects.pybridge;
            });
        }
        """
        self.map_widget.web_view.page().runJavaScript(js)

    def focus_osm_map(self):
        """Move keyboard/focus to the OSM map."""
        if self.map_widget and self.map_widget.web_view:
            self.map_widget.web_view.setFocus()
            self.status_bar.showMessage(
                "Draw a rectangle on the OSM map to select the extent."
            )

    def on_map_bounds_received(self, bbox):
        """Receive the selected OSM/KML extent and put it in Bounding Box."""
        if not bbox:
            return

        self.bounding_box.setText(bbox)

        self.status_bar.showMessage(
            f"OSM extent selected: {bbox}"
        )

    def load_kml_kmz_from_left(self):
        """Open the same KML/KMZ loader used by the map panel."""
        if self.map_widget:
            self.map_widget.load_kml_kmz()

    def closeEvent(self, event):
        """Handle window close."""
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
    
    # Check for embedded OSM support
    if not HAS_WEBENGINE:
        print("\n" + "="*60)
        print("WARNING: PyQtWebEngine is not installed.")
        print("Install it for the embedded OSM extent selector:")
        print("  pip install PyQtWebEngine")
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