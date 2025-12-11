import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QProgressBar, QFileDialog,
    QMessageBox, QFrame, QStyle, QComboBox
)
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtCore import Qt, QThread, Signal

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

APP_TITLE = "AnimeGirlDownloaderQt"

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
        path = self.api_config["path"]

        try:
            params = {}
            target_url = api_url

            if "nekos.moe" in api_url:
                params = {"nsfw": "true" if self.nsfw_enabled else "false"}
            elif "waifu.im" in api_url:
                target_url = f"{api_url}{str(self.nsfw_enabled).lower()}"

            headers = {'User-Agent': 'MultiSourceNekoViewer (PySide6) v3.0'}

            response = requests.get(target_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            image_source = data
            try:
                for key in path:
                    image_source = image_source[key]

                if base_url:
                    image_url = f"{base_url}{image_source}"
                else:
                    image_url = image_source

            except (KeyError, IndexError, TypeError):
                self.operation_error.emit("API response structure is unexpected or image path not found.")
                return

            if not image_url or not image_url.startswith('http'):
                self.operation_error.emit("A valid image URL could not be obtained.")
                return

            img_response = requests.get(image_url, headers=headers, timeout=15)
            img_response.raise_for_status()

            self.image_ready.emit(img_response.content)

        except requests.exceptions.Timeout:
            self.operation_error.emit("Request timed out. Check your network connection.")
        except requests.exceptions.RequestException as e:
            self.operation_error.emit(f"Network Error: {e.__class__.__name__} - URL: {target_url}")
        except Exception as e:
            self.operation_error.emit(f"Unexpected Critical Error: {str(e)}")

class NekoViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(450, 550)
        self.resize(700, 800)

        self.current_pixmap = None
        self.worker = None

        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(25, 25, 25, 25)

        selection_layout = QHBoxLayout()
        self.api_selector = QComboBox()
        self.api_selector.setFont(QFont("Sans-Serif", 10, QFont.Bold))

        for name in API_SOURCES:
            self.api_selector.addItem(name)

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

        self.update_source_info()
        self.nsfw_checkbox.stateChanged.connect(self.update_source_info)


    def update_source_info(self):
        selected_name = self.api_selector.currentText()
        config = API_SOURCES.get(selected_name)

        has_nsfw_support = selected_name in ["Nekos.moe (Default)", "Waifu.im"]

        self.nsfw_checkbox.setDisabled(not has_nsfw_support)
        if not has_nsfw_support:
            self.nsfw_checkbox.setChecked(False)

        notes = config.get("notes", "No additional info.")

        self.image_label.setText(
            f"Click 'Refresh Image' to load a new image.\nSource: {selected_name}\n({notes})"
        )
        self.image_label.setStyleSheet(f"QLabel#image_label {{ border: 3px dashed {COLOR_SUBTLE}; color: {COLOR_SUBTLE}; background-color: {COLOR_CONTAINER}; }}")


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
            QComboBox::drop-down {{
                border: none;
            }}
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
                transition: all 0.2s;
            }}

            QPushButton:hover {{
                opacity: 0.9;
            }}

            QPushButton:pressed {{
                padding-top: 8px;
            }}

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


    def start_loading_image(self):
        selected_name = self.api_selector.currentText()
        api_config = API_SOURCES.get(selected_name)

        if not api_config:
            self.on_error("Selected API source not found.")
            return

        if self.worker is not None and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        self.refresh_button.setDisabled(True)
        self.download_button.setDisabled(True)
        self.api_selector.setDisabled(True)
        self.status_label.setText(f"Downloading image from '{selected_name}', please wait...")
        self.image_label.setText("Loading...")
        self.image_label.setStyleSheet(f"QLabel#image_label {{ border: 3px dashed {COLOR_ACCENT_PURPLE}; color: {COLOR_ACCENT_PURPLE}; }}")

        self.progress_bar.setRange(0, 0)

        self.worker = ImageFetcherWorker(api_config, self.nsfw_checkbox.isChecked())
        self.worker.image_ready.connect(self.on_image_loaded)
        self.worker.operation_error.connect(self.on_error)
        self.worker.start()

    def on_image_loaded(self, image_data):
        self.reset_ui_state("Image loaded successfully.")

        pixmap = QPixmap()
        pixmap.loadFromData(image_data)

        if not pixmap.isNull():
            self.current_pixmap = pixmap
            self.image_label.setStyleSheet(f"QLabel#image_label {{ border: none; background-color: {COLOR_CONTAINER}; }}")
            self.update_scaled_image()
            self.download_button.setDisabled(False)
        else:
            self.on_error("Image data is corrupt or unreadable.")

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
        if is_error:
            self.status_label.setStyleSheet("color: #F38BA8; font-style: normal; font-weight: bold;")
        else:
            self.status_label.setStyleSheet(f"color: {COLOR_SUBTLE}; font-style: italic;")

    def update_scaled_image(self):
        if self.current_pixmap:
            label_size = self.image_label.size()

            scaled = self.current_pixmap.scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.current_pixmap:
            self.update_scaled_image()

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        event.accept()

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
                QMessageBox.information(self, "Success", f"Image successfully saved to '{file_path}'.")
            else:
                QMessageBox.warning(self, "Save Error", "An error occurred while saving the image.")

if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    window = NekoViewer()
    window.show()
    sys.exit(app.exec())
