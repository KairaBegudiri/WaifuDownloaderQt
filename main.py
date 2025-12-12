import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QProgressBar, QFileDialog,
    QMessageBox, QFrame, QStyle, QComboBox
)
from PySide6.QtGui import QPixmap, QFont, QIcon
from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize
import sys
import os

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

API_SOURCES = {
    "Nekos.moe (Default)": {
        "api_url": "https://nekos.moe/api/v1/random/image",
        "base_url": "https://nekos.moe/image/",
        "path": ["images", 0, "id"],
        "notes": "Various Neko and anime images."
    },
    "Waifu.im": {
        "api_url": "https://api.waifu.im/search?is_nsfw=",
        "base_url": "",
        "path": ["images", 0, "url"],
        "notes": "High-resolution Waifu/Neko images."
    }
}

APP_TITLE = "WaifuDownloaderQt"

COLOR_BACKGROUND_DARK = "#1E1E2E"
COLOR_CONTAINER = "#181825"
COLOR_TEXT_PRIMARY = "#CDD6F4"
COLOR_ACCENT_PURPLE = "#CBA6F7"
COLOR_ACCENT_BLUE = "#89B4FA"
COLOR_DISABLED = "#45475A"
COLOR_SUBTLE = "#6C7086"

class ImageFetcherWorker(QThread):
    image_ready = Signal(bytes)
    operation_error = Signal(str)

    def __init__(self, api_config, nsfw_enabled, parent=None):
        super().__init__(parent)
        self.api_config = api_config
        self.nsfw_enabled = nsfw_enabled

    def run(self):
        api_url = self.api_config["api_url"]
        base_url = self.api_config["base_url"]
        path_keys = self.api_config["path"]

        with requests.Session() as session:
            session.headers.update({'User-Agent': 'MultiSourceNekoViewer (PySide6) v3.1'})

            try:
                params = {}
                target_url = api_url

                if "nekos.moe" in api_url:
                    params = {"nsfw": "true" if self.nsfw_enabled else "false"}
                elif "waifu.im" in api_url:
                    target_url = f"{api_url}{str(self.nsfw_enabled).lower()}"

                response = session.get(target_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                current_node = data
                try:
                    for key in path_keys:
                        current_node = current_node[key]

                    image_endpoint = current_node

                    if base_url:
                        final_image_url = f"{base_url}{image_endpoint}"
                    else:
                        final_image_url = image_endpoint

                except (KeyError, IndexError, TypeError):
                    self.operation_error.emit("API response structure changed or path invalid.")
                    return

                if not final_image_url or not final_image_url.startswith('http'):
                    self.operation_error.emit("Invalid image URL retrieved.")
                    return

                img_response = session.get(final_image_url, timeout=15)
                img_response.raise_for_status()

                self.image_ready.emit(img_response.content)

            except requests.exceptions.Timeout:
                self.operation_error.emit("Request timed out. Please check your connection.")
            except requests.exceptions.RequestException as e:
                self.operation_error.emit(f"Network Error: {e}")
            except Exception as e:
                self.operation_error.emit(f"Unexpected Error: {str(e)}")

class NekoViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setWindowIcon(QIcon(resource_path("moe.nyarchlinux.waifudownloader.png")))
        self.setMinimumSize(450, 550)
        self.resize(700, 800)

        self.current_pixmap = None
        self.worker = None
        self.last_size = None

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 25, 25, 25)

        selection_layout = QHBoxLayout()
        self.api_selector = QComboBox()
        self.api_selector.setFont(QFont("Sans-Serif", 10, QFont.Bold))
        self.api_selector.addItems(API_SOURCES.keys())

        selection_layout.addWidget(QLabel("Image Source:"))
        selection_layout.addWidget(self.api_selector, 1)
        main_layout.addLayout(selection_layout)

        self.image_frame = QFrame()
        self.image_frame.setFrameShape(QFrame.NoFrame)
        self.image_frame.setMinimumHeight(450)

        image_layout = QVBoxLayout(self.image_frame)
        image_layout.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel("Click 'Refresh Image' to load a new image.\nSource: Nekos.moe (Default)")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(False)

        image_layout.addWidget(self.image_label)
        main_layout.addWidget(self.image_frame, 1)

        status_bar_layout = QHBoxLayout()
        status_bar_layout.setSpacing(10)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet(f"color: {COLOR_SUBTLE}; font-style: italic;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setMaximumWidth(150)

        status_bar_layout.addWidget(self.status_label, 1)
        status_bar_layout.addWidget(self.progress_bar)
        main_layout.addLayout(status_bar_layout)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        self.nsfw_checkbox = QCheckBox("Allow NSFW Content")
        self.nsfw_checkbox.setCursor(Qt.PointingHandCursor)
        self.nsfw_checkbox.setFont(QFont("Sans-Serif", 10))
        control_layout.addWidget(self.nsfw_checkbox)

        control_layout.addStretch(1)

        refresh_icon = self.style().standardIcon(QStyle.SP_BrowserReload)
        self.refresh_button = QPushButton(refresh_icon, "Refresh Image")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setObjectName("refreshButton")

        download_icon = self.style().standardIcon(QStyle.SP_DialogSaveButton)
        self.download_button = QPushButton(download_icon, "Save")
        self.download_button.setCursor(Qt.PointingHandCursor)
        self.download_button.setDisabled(True)
        self.download_button.setObjectName("downloadButton")

        control_layout.addWidget(self.refresh_button)
        control_layout.addWidget(self.download_button)
        main_layout.addLayout(control_layout)

        self.refresh_button.clicked.connect(self.start_loading_image)
        self.download_button.clicked.connect(self.save_image)
        self.api_selector.currentIndexChanged.connect(self.update_source_info)
        self.nsfw_checkbox.stateChanged.connect(self.update_source_info)

        self.update_source_info()

    @Slot()
    def update_source_info(self):
        selected_name = self.api_selector.currentText()
        config = API_SOURCES.get(selected_name)

        has_nsfw_support = selected_name in ["Nekos.moe (Default)", "Waifu.im"]

        self.nsfw_checkbox.setEnabled(has_nsfw_support)
        if not has_nsfw_support:
            self.nsfw_checkbox.setChecked(False)

        notes = config.get("notes", "No additional info.")
        self.image_label.setText(
            f"Click 'Refresh Image' to load a new image.\nSource: {selected_name}\n({notes})"
        )
        self.image_label.setStyleSheet(f"QLabel#image_label {{ border: 3px dashed {COLOR_SUBTLE}; color: {COLOR_SUBTLE}; background-color: {COLOR_CONTAINER}; }}")
        self.current_pixmap = None
        self.download_button.setDisabled(True)

    def apply_styles(self):
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND_DARK};
                color: {COLOR_TEXT_PRIMARY};
                font-family: "Noto Sans", "Inter", sans-serif;
            }}

            QLabel#image_label {{
                background-color: {COLOR_CONTAINER};
                border: 3px dashed {COLOR_SUBTLE};
                border-radius: 12px;
                font-size: 16px;
                color: {COLOR_SUBTLE};
                padding: 20px;
            }}

            QComboBox {{
                padding: 5px 10px;
                border: 1px solid {COLOR_SUBTLE};
                border-radius: 6px;
                background-color: {COLOR_CONTAINER};
                color: {COLOR_TEXT_PRIMARY};
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                border: 1px solid {COLOR_ACCENT_PURPLE};
                background-color: {COLOR_CONTAINER};
                selection-background-color: {COLOR_ACCENT_PURPLE};
                color: {COLOR_TEXT_PRIMARY};
                outline: 0;
            }}

            QPushButton {{
                min-width: 120px;
                min-height: 35px;
                font-weight: 600;
                border-radius: 8px;
                padding: 6px 15px;
                border: none;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
            QPushButton:pressed {{ padding-top: 8px; }}

            QPushButton#refreshButton {{
                background-color: {COLOR_ACCENT_PURPLE};
                color: {COLOR_BACKGROUND_DARK};
            }}

            QPushButton#downloadButton {{
                background-color: {COLOR_ACCENT_BLUE};
                color: {COLOR_BACKGROUND_DARK};
            }}

            QPushButton:disabled {{
                background-color: {COLOR_DISABLED};
                color: {COLOR_SUBTLE};
            }}

            QCheckBox {{
                spacing: 8px;
                font-size: 14px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid {COLOR_SUBTLE};
                background-color: {COLOR_CONTAINER};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLOR_ACCENT_PURPLE};
                border-color: {COLOR_ACCENT_PURPLE};
            }}

            QProgressBar {{
                background-color: {COLOR_DISABLED};
                border-radius: 3px;
                height: 6px;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_ACCENT_PURPLE};
                border-radius: 3px;
            }}
        """)
        self.image_label.setObjectName("image_label")

    @Slot()
    def start_loading_image(self):
        selected_name = self.api_selector.currentText()
        api_config = API_SOURCES.get(selected_name)

        if not api_config:
            self.on_error("Selected API source not found.")
            return

        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.disconnect()
                self.worker.terminate()
                self.worker.wait()
            self.worker.deleteLater()
            self.worker = None

        self.refresh_button.setDisabled(True)
        self.download_button.setDisabled(True)
        self.api_selector.setDisabled(True)
        self.status_label.setText(f"Downloading from '{selected_name}'...")
        self.image_label.setText("Loading...")
        self.image_label.setStyleSheet(f"QLabel#image_label {{ border: 3px dashed {COLOR_ACCENT_PURPLE}; color: {COLOR_ACCENT_PURPLE}; }}")

        self.progress_bar.setRange(0, 0)

        self.worker = ImageFetcherWorker(api_config, self.nsfw_checkbox.isChecked())
        self.worker.image_ready.connect(self.on_image_loaded)
        self.worker.operation_error.connect(self.on_error)
        self.worker.start()

    @Slot(bytes)
    def on_image_loaded(self, image_data):
        self.reset_ui_state("Image loaded successfully.")

        pixmap = QPixmap()
        pixmap.loadFromData(image_data)

        if not pixmap.isNull():
            self.current_pixmap = pixmap
            self.image_label.setStyleSheet(f"QLabel#image_label {{ border: none; background-color: {COLOR_CONTAINER}; }}")
            self.update_scaled_image(force=True)
            self.download_button.setDisabled(False)
        else:
            self.on_error("Image data is corrupt or unreadable.")

    @Slot(str)
    def on_error(self, error_msg):
        self.reset_ui_state(f"ERROR: {error_msg}", is_error=True)
        self.image_label.setText("Loading Failed!")
        self.image_label.setStyleSheet(f"QLabel#image_label {{ border: 3px dashed #F38BA8; color: #F38BA8; }}")
        QMessageBox.critical(self, "Critical Error", error_msg)

    def reset_ui_state(self, status_message, is_error=False):
        self.refresh_button.setDisabled(False)
        self.api_selector.setDisabled(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        self.status_label.setText(status_message)
        color = "#F38BA8" if is_error else COLOR_SUBTLE
        font_style = "normal; font-weight: bold;" if is_error else "italic;"
        self.status_label.setStyleSheet(f"color: {color}; font-style: {font_style}")

    def update_scaled_image(self, force=False):
        if not self.current_pixmap:
            return

        current_size = self.image_label.size()

        if not force and self.last_size == current_size:
            return

        self.last_size = current_size

        scaled = self.current_pixmap.scaled(
            current_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_scaled_image()

    def closeEvent(self, event):
        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.disconnect()
                self.worker.terminate()
                self.worker.wait()
            self.worker.deleteLater()
        event.accept()

    @Slot()
    def save_image(self):
        if not self.current_pixmap:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image",
            "neko_image.png",
            "PNG Images (*.png);;JPEG Images (*.jpg);;All Files (*.*)"
        )

        if file_path:
            if self.current_pixmap.save(file_path):
                QMessageBox.information(self, "Success", f"Saved to '{file_path}'.")
            else:
                QMessageBox.warning(self, "Save Error", "Could not save the image.")

if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    window = NekoViewer()
    window.show()
    sys.exit(app.exec())
