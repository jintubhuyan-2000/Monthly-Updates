"""
MOSDAC Data Downloader GUI
A comprehensive GUI application for downloading satellite data from MOSDAC
"""

import sys
import os
import json
import re
import time
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
import requests
from typing import Optional, List, Dict, Any, Tuple

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
        """Fetch available datasets from MOSDAC"""
        try:
            response = requests.get(self.search_url, params={"count": 1000}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if "entries" in data:
                    # Extract dataset information
                    datasets = []
                    for entry in data["entries"]:
                        dataset_id = entry.get("id")
                        title = entry.get("title", dataset_id)
                        datasets.append({
                            "id": dataset_id,
                            "title": title,
                            "description": entry.get("description", "")
                        })
                    return datasets
            return []
        except Exception as e:
            print(f"Error fetching datasets: {e}")
            return []
    
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
                return total_results, total_size_mb, entries
            else:
                return 0, 0, []
                
        except Exception as e:
            print(f"Error searching files: {e}")
            return 0, 0, []
    
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
                    error_data = response.json() if response.text else {}
                    if error_data.get("code") == "NOT_RELEASED":
                        return False, "Product not released on Internet"
                    return False, "File not found"
                    
                if response.status_code == 429:
                    resp = response.json() if response.text else {}
                    err_type = resp.get('type', '')
                    if err_type == 'minute_limit':
                        time.sleep(20)
                        continue
                    elif err_type == 'daily_limit':
                        return False, "Daily download limit reached"
                        
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


class DownloadWorker(QThread):
    """Worker thread for downloading files"""
    
    progress_signal = pyqtSignal(int, int, int, int)  # file_num, total_files, downloaded, total_size
    log_signal = pyqtSignal(str)  # Status messages
    finished_signal = pyqtSignal(bool, int, int, float)  # success, downloaded, skipped, time_taken
    error_signal = pyqtSignal(str)  # Error messages
    
    def __init__(self, downloader: MOSDACDownloader, dataset_id: str, start_time: str, 
                 end_time: str, bounding_box: str, gid: str, count: int):
        super().__init__()
        self.downloader = downloader
        self.dataset_id = dataset_id
        self.start_time = start_time
        self.end_time = end_time
        self.bounding_box = bounding_box
        self.gid = gid
        self.count = count
        self.is_running = True
        
    def stop(self):
        self.is_running = False
        
    def run(self):
        try:
            start_time = time.time()
            self.log_signal.emit(f"Searching for files with dataset: {self.dataset_id}")
            
            # Search for files
            total_results, total_size, entries = self.downloader.search_files(
                self.dataset_id, self.start_time, self.end_time,
                self.bounding_box, self.gid, self.count
            )
            
            if total_results == 0:
                self.error_signal.emit("No files found matching the search criteria")
                return
                
            size_str = self.format_size(total_size)
            self.log_signal.emit(f"Found {total_results} files, Total size: {size_str}")
            
            # Process files
            downloaded = 0
            skipped = 0
            
            for i, entry in enumerate(entries, 1):
                if not self.is_running:
                    break
                    
                record_id = entry.get("id")
                identifier = entry.get("identifier")
                prod_date = entry.get("updated")
                
                self.log_signal.emit(f"Processing file {i}/{len(entries)}: {identifier}")
                
                # Download file
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
                        self.log_signal.emit(f"File downloaded: {identifier}")
                else:
                    skipped += 1
                    self.log_signal.emit(f"File failed: {identifier} - {message}")
                    
            end_time = time.time()
            time_taken = end_time - start_time
            
            self.finished_signal.emit(True, downloaded, skipped, time_taken)
            
        except Exception as e:
            self.error_signal.emit(f"Download error: {str(e)}")
            
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
        self.setWindowTitle("MOSDAC Data Downloader")
        self.setGeometry(100, 100, 900, 700)
        self.setMinimumSize(800, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_auth_tab()
        self.create_download_tab()
        self.create_log_tab()
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
    def create_auth_tab(self):
        """Create authentication tab"""
        auth_tab = QWidget()
        self.tab_widget.addTab(auth_tab, "Authentication")
        
        layout = QVBoxLayout(auth_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("MOSDAC Data Downloader")
        title.setStyleSheet("font-size: 18pt; font-weight: bold;")
        layout.addWidget(title)
        
        subtitle = QLabel("Authenticate with your MOSDAC credentials to access the data catalogue")
        subtitle.setStyleSheet("color: #666; font-size: 10pt;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # Authentication form
        auth_group = QGroupBox("Credentials")
        auth_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(10)
        
        # Username
        username_layout = QHBoxLayout()
        username_label = QLabel("Username / Email:")
        username_label.setMinimumWidth(150)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your MOSDAC username or email")
        username_layout.addWidget(username_label)
        username_layout.addWidget(self.username_input)
        auth_layout.addLayout(username_layout)
        
        # Password
        password_layout = QHBoxLayout()
        password_label = QLabel("Password:")
        password_label.setMinimumWidth(150)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your MOSDAC password")
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        auth_layout.addLayout(password_layout)
        
        # Verify button
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
        
        # Status display
        status_group = QGroupBox("Authentication Status")
        status_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        status_layout = QVBoxLayout(status_group)
        
        self.auth_status = QLabel("Not authenticated")
        self.auth_status.setStyleSheet("color: #666; padding: 5px;")
        status_layout.addWidget(self.auth_status)
        
        self.user_info = QLabel("")
        self.user_info.setStyleSheet("color: #666; padding: 5px;")
        status_layout.addWidget(self.user_info)
        
        layout.addWidget(status_group)
        layout.addStretch()
        
    def create_download_tab(self):
        """Create download tab"""
        download_tab = QWidget()
        self.tab_widget.addTab(download_tab, "Download")
        self.tab_widget.setTabEnabled(1, False)  # Disabled until authenticated
        
        layout = QVBoxLayout(download_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Dataset selection
        dataset_group = QGroupBox("Dataset Selection")
        dataset_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        dataset_layout = QVBoxLayout(dataset_group)
        
        dataset_row = QHBoxLayout()
        dataset_label = QLabel("Dataset:")
        dataset_label.setMinimumWidth(100)
        self.dataset_combo = QComboBox()
        self.dataset_combo.setEditable(True)
        self.dataset_combo.setPlaceholderText("Select or type dataset ID")
        self.dataset_combo.currentTextChanged.connect(self.on_dataset_changed)
        dataset_row.addWidget(dataset_label)
        dataset_row.addWidget(self.dataset_combo)
        dataset_layout.addLayout(dataset_row)
        
        # Refresh datasets button
        refresh_row = QHBoxLayout()
        refresh_row.addStretch()
        self.refresh_datasets_button = QPushButton("Refresh Dataset List")
        self.refresh_datasets_button.clicked.connect(self.refresh_datasets)
        refresh_row.addWidget(self.refresh_datasets_button)
        dataset_layout.addLayout(refresh_row)
        
        layout.addWidget(dataset_group)
        
        # Date range
        date_group = QGroupBox("Date Range")
        date_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        date_layout = QGridLayout(date_group)
        
        # Start date
        date_layout.addWidget(QLabel("Start Date:"), 0, 0)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-10))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self.start_date, 0, 1)
        
        # End date
        date_layout.addWidget(QLabel("End Date:"), 1, 0)
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        date_layout.addWidget(self.end_date, 1, 1)
        
        layout.addWidget(date_group)
        
        # Additional parameters
        params_group = QGroupBox("Additional Parameters")
        params_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        params_layout = QGridLayout(params_group)
        
        # Bounding Box
        params_layout.addWidget(QLabel("Bounding Box:"), 0, 0)
        self.bounding_box = QLineEdit()
        self.bounding_box.setPlaceholderText("min_lon,min_lat,max_lon,max_lat")
        params_layout.addWidget(self.bounding_box, 0, 1)
        
        # gId
        params_layout.addWidget(QLabel("gId:"), 1, 0)
        self.gid_input = QLineEdit()
        self.gid_input.setPlaceholderText("Geographic identifier (optional)")
        params_layout.addWidget(self.gid_input, 1, 1)
        
        # Count
        params_layout.addWidget(QLabel("File Count:"), 2, 0)
        self.count_input = QSpinBox()
        self.count_input.setRange(0, 10000)
        self.count_input.setValue(0)
        self.count_input.setSpecialValueText("All")
        params_layout.addWidget(self.count_input, 2, 1)
        
        layout.addWidget(params_group)
        
        # Output settings
        output_group = QGroupBox("Output Settings")
        output_group.setStyleSheet("QGroupBox { font-weight: bold; }")
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
        browse_button.clicked.connect(self.browse_output_folder)
        output_row.addWidget(browse_button)
        output_layout.addLayout(output_row)
        
        # Options
        options_layout = QHBoxLayout()
        self.organize_by_date = QCheckBox("Organize files by date")
        self.organize_by_date.setChecked(True)
        options_layout.addWidget(self.organize_by_date)
        
        self.generate_logs = QCheckBox("Generate error logs")
        self.generate_logs.setChecked(True)
        options_layout.addWidget(self.generate_logs)
        
        options_layout.addStretch()
        output_layout.addLayout(options_layout)
        
        layout.addWidget(output_group)
        
        # Download button
        download_row = QHBoxLayout()
        download_row.addStretch()
        self.download_button = QPushButton("Search & Start Download")
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 10px 30px;
                font-weight: bold;
                font-size: 12pt;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.download_button.clicked.connect(self.start_download)
        download_row.addWidget(self.download_button)
        layout.addLayout(download_row)
        
        # Download progress
        progress_group = QGroupBox("Download Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready to download")
        self.status_label.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.status_label)
        
        layout.addWidget(progress_group)
        
    def create_log_tab(self):
        """Create log tab"""
        log_tab = QWidget()
        self.tab_widget.addTab(log_tab, "Processing Log")
        self.tab_widget.setTabEnabled(2, False)
        
        layout = QVBoxLayout(log_tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        layout.addWidget(self.log_text)
        
        # Log controls
        control_layout = QHBoxLayout()
        
        clear_button = QPushButton("Clear Log")
        clear_button.clicked.connect(self.clear_log)
        control_layout.addWidget(clear_button)
        
        save_button = QPushButton("Save Log")
        save_button.clicked.connect(self.save_log)
        control_layout.addWidget(save_button)
        
        control_layout.addStretch()
        
        # Auto-scroll checkbox
        self.auto_scroll = QCheckBox("Auto-scroll")
        self.auto_scroll.setChecked(True)
        control_layout.addWidget(self.auto_scroll)
        
        layout.addLayout(control_layout)
        
    def load_config(self):
        """Load saved configuration if exists"""
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
                if "last_dataset" in config:
                    self.dataset_combo.setCurrentText(config["last_dataset"])
                    
            except Exception as e:
                print(f"Error loading config: {e}")
                
    def save_config(self):
        """Save current configuration"""
        config = {
            "username": self.username_input.text(),
            "output_folder": self.output_folder.text(),
            "organize_by_date": self.organize_by_date.isChecked(),
            "generate_logs": self.generate_logs.isChecked(),
            "last_dataset": self.dataset_combo.currentText()
        }
        try:
            with open("mosdac_gui_config.json", 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def verify_credentials(self):
        """Verify user credentials with MOSDAC"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Input Error", 
                              "Please enter both username and password")
            return
            
        self.verify_button.setEnabled(False)
        self.verify_button.setText("Verifying...")
        self.status_bar.showMessage("Verifying credentials...")
        
        # Verify in a separate thread
        def verify_thread():
            success, message = self.downloader.authenticate(username, password)
            return success, message
            
        # Use QThread for verification
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
            
            # Enable download tab
            self.tab_widget.setTabEnabled(1, True)
            self.tab_widget.setCurrentIndex(1)
            
            # Refresh dataset list
            self.refresh_datasets()
            
            self.status_bar.showMessage(f"Authenticated as {self.downloader.username}")
            
            # Save config
            self.save_config()
            
        else:
            self.auth_status.setText(f"✗ Authentication failed")
            self.auth_status.setStyleSheet("color: #f44336; font-weight: bold; padding: 5px;")
            self.user_info.setText("")
            
            QMessageBox.warning(self, "Authentication Failed", message)
            self.status_bar.showMessage("Authentication failed")
            
    def refresh_datasets(self):
        """Refresh the dataset list from MOSDAC"""
        if not self.downloader.is_authenticated:
            QMessageBox.warning(self, "Not Authenticated", 
                              "Please authenticate first before loading datasets")
            return
            
        self.refresh_datasets_button.setEnabled(False)
        self.refresh_datasets_button.setText("Loading...")
        self.status_bar.showMessage("Loading datasets...")
        
        def load_datasets():
            datasets = self.downloader.get_datasets()
            return datasets
            
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
        self.refresh_datasets_button.setText("Refresh Dataset List")
        
        # Clear existing items
        self.dataset_combo.clear()
        
        if not datasets:
            self.dataset_combo.addItem("No datasets available")
            self.status_bar.showMessage("No datasets available")
            return
            
        # Add datasets to combo box
        for dataset in datasets:
            display_text = f"{dataset['id']}"
            if dataset.get('title') and dataset['title'] != dataset['id']:
                display_text = f"{dataset['title']} [{dataset['id']}]"
            self.dataset_combo.addItem(display_text, dataset['id'])
            
        self.status_bar.showMessage(f"Loaded {len(datasets)} datasets")
        
    def on_dataset_changed(self, text):
        """Handle dataset selection change"""
        # If user types a custom dataset ID, store it
        if not text:
            return
            
        # Check if text is in the combo box
        index = self.dataset_combo.findText(text)
        if index >= 0:
            # It's an existing item
            dataset_id = self.dataset_combo.itemData(index)
            if dataset_id:
                self.status_bar.showMessage(f"Selected dataset: {dataset_id}")
        
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder.setText(folder)
            
    def start_download(self):
        """Start the download process"""
        # Validate inputs
        if not self.downloader.is_authenticated:
            QMessageBox.warning(self, "Not Authenticated", 
                              "Please authenticate first")
            return
            
        dataset_text = self.dataset_combo.currentText()
        if not dataset_text or dataset_text == "No datasets available":
            QMessageBox.warning(self, "Input Error", 
                              "Please select a dataset")
            return
            
        # Get dataset ID from combo data or text
        dataset_id = self.dataset_combo.currentData()
        if not dataset_id:
            # If custom text, use it as dataset ID
            dataset_id = dataset_text
            
        # Get dates
        start_date = self.start_date.date().toString("yyyy-MM-dd")
        end_date = self.end_date.date().toString("yyyy-MM-dd")
        
        if start_date > end_date:
            QMessageBox.warning(self, "Date Error", 
                              "Start date must be before end date")
            return
            
        # Get other parameters
        bounding_box = self.bounding_box.text().strip()
        gid = self.gid_input.text().strip()
        count = self.count_input.value()
        
        # Get output folder
        output_folder = self.output_folder.text().strip()
        if not output_folder:
            output_folder = os.getcwd()
            
        # Setup downloader
        self.downloader.download_path = output_folder
        self.downloader.use_date_structure = self.organize_by_date.isChecked()
        
        if self.generate_logs.isChecked():
            self.downloader.setup_logging(os.path.join(output_folder, "error_logs"))
        else:
            self.downloader.generate_logs = False
            
        # Disable download button
        self.download_button.setEnabled(False)
        self.download_button.setText("Downloading...")
        
        # Enable log tab
        self.tab_widget.setTabEnabled(2, True)
        
        # Clear previous log
        self.log_text.clear()
        self.add_log("=== MOSDAC Data Download Started ===")
        self.add_log(f"Dataset: {dataset_id}")
        self.add_log(f"Date Range: {start_date} to {end_date}")
        if bounding_box:
            self.add_log(f"Bounding Box: {bounding_box}")
        if gid:
            self.add_log(f"gId: {gid}")
        self.add_log(f"Output Folder: {output_folder}")
        self.add_log("")
        
        # Start download in worker thread
        self.download_worker = DownloadWorker(
            self.downloader, dataset_id, start_date, end_date,
            bounding_box, gid, count
        )
        
        self.download_worker.progress_signal.connect(self.update_progress)
        self.download_worker.log_signal.connect(self.add_log)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.error_signal.connect(self.on_download_error)
        
        self.download_worker.start()
        
        # Save config
        self.save_config()
        
        # Switch to log tab
        self.tab_widget.setCurrentIndex(2)
        
    def update_progress(self, file_num, total_files, downloaded, total_size):
        """Update download progress"""
        if total_files > 0:
            progress = (file_num / total_files) * 100
            self.progress_bar.setValue(int(progress))
            
            # Update status label
            size_mb = total_size / (1024 * 1024)
            self.status_label.setText(
                f"Downloading file {file_num}/{total_files} ({size_mb:.1f} MB)"
            )
            
    def add_log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        self.log_text.append(log_line)
        
        if self.auto_scroll.isChecked():
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)
            
    def clear_log(self):
        """Clear the log text"""
        self.log_text.clear()
        
    def save_log(self):
        """Save log to file"""
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
                
    def on_download_finished(self, success, downloaded, skipped, time_taken):
        """Handle download completion"""
        self.download_button.setEnabled(True)
        self.download_button.setText("Search & Start Download")
        self.progress_bar.setValue(100)
        
        # Format time
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
        
        QMessageBox.information(self, "Download Complete", 
                              f"Download completed!\n\n"
                              f"Files downloaded: {downloaded}\n"
                              f"Files skipped: {skipped}\n"
                              f"Time taken: {time_str}")
        
        # Logout
        self.downloader.logout()
        self.add_log("Logged out from MOSDAC")
        
    def on_download_error(self, error_message):
        """Handle download error"""
        self.download_button.setEnabled(True)
        self.download_button.setText("Search & Start Download")
        
        self.add_log(f"ERROR: {error_message}")
        self.status_label.setText(f"Error: {error_message}")
        self.status_bar.showMessage("Download failed")
        
        QMessageBox.critical(self, "Download Error", 
                           f"Download failed:\n{error_message}")
        
    def closeEvent(self, event):
        """Handle window close event"""
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
            
        # Logout if authenticated
        if self.downloader.is_authenticated:
            self.downloader.logout()
            
        # Save config
        self.save_config()
        
        event.accept()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set application icon
    app.setWindowIcon(QIcon())
    
    window = MOSDACGui()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
    