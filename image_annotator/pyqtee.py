import sys
import os
import subprocess
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QPoint, Qt, QRect, QTemporaryFile
import json
from PyQt5.QtGui import QPixmap, QPainter
import subprocess
from PyQt5.QtGui import QPainter, QPen, QColor, QPixmap
import geopandas as gpd
from dotenv import load_dotenv

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
)
from PyQt5.QtWidgets import (
    QComboBox,
    QCheckBox,
)

load_dotenv()

api_key = os.getenv("api_key")

# Load the data
unique_substations_gdf = gpd.read_file("substations_filtered.geojson")
unique_substations_gdf["SS_ID"] = unique_substations_gdf["substation"]

# Make sure the CRS is set to EPSG:4326
unique_substations_gdf = unique_substations_gdf.to_crs(epsg=4326)

# Create lat and lon from geom points
unique_substations_gdf["lat"] = unique_substations_gdf.geometry.y
unique_substations_gdf["lon"] = unique_substations_gdf.geometry.x

# Transmission lines
transmission_lines_gdf = gpd.read_file("split_lines_filtered.geojson")

# Make sure crs is set to EPSG:4326
transmission_lines_gdf = transmission_lines_gdf.to_crs(epsg=4326)


class CropLabel(QLabel):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setPixmap(pixmap)
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.drawing = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.end_point = event.pos()
            self.drawing = False
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.start_point.isNull() and not self.end_point.isNull():
            painter = QPainter(self)
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
            painter.drawRect(QRect(self.start_point, self.end_point))

    def get_cropped_pixmap(self, target_size=(1280, 1280)):
        x = min(self.start_point.x(), self.end_point.x())
        y = min(self.start_point.y(), self.end_point.y())
        width = abs(self.start_point.x() - self.end_point.x())
        height = abs(self.start_point.y() - self.end_point.y())

        # Crop the pixmap
        cropped_pixmap = self.pixmap().copy(x, y, width, height)

        # Resize the cropped pixmap
        resized_pixmap = cropped_pixmap.scaled(
            target_size[0], target_size[1], Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        # If the resized pixmap is smaller than the target size, pad it
        if (
            resized_pixmap.width() != target_size[0]
            or resized_pixmap.height() != target_size[1]
        ):
            padded_pixmap = QPixmap(target_size[0], target_size[1])
            padded_pixmap.fill(Qt.black)  # Fill with black, you can change this color

            # Calculate position to center the resized image
            x_offset = (target_size[0] - resized_pixmap.width()) // 2
            y_offset = (target_size[1] - resized_pixmap.height()) // 2

            # Draw the resized image onto the padded pixmap
            painter = QPainter(padded_pixmap)
            painter.drawPixmap(x_offset, y_offset, resized_pixmap)
            painter.end()

            return padded_pixmap

        return resized_pixmap


class ScreenshotPreviewDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screenshot Preview")
        layout = QVBoxLayout()

        preview_label = QLabel()
        preview_label.setPixmap(
            pixmap.scaled(600, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        layout.addWidget(preview_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Retry | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Retry).clicked.connect(self.retry)
        layout.addWidget(button_box)

        self.setLayout(layout)
        self.result = ""

    def retry(self):
        self.result = "retry"
        self.accept()


class SubstationMapApp(QMainWindow):
    def __init__(self, gdf, tl_gdf, api_key):
        super().__init__()
        self.gdf = gdf
        self.tl_gdf = tl_gdf
        self.api_key = api_key
        self.current_index = 0
        self.filtered_gdf = self.gdf
        self.ss_type = "All Types"
        self.show_transmission_lines = False
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Substation Viewer with LabelMe Integration")
        self.setGeometry(100, 100, 1200, 900)

        layout = QVBoxLayout()

        # Web view
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, stretch=1)

        # Search layout
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Enter Substation ID")
        search_layout.addWidget(self.search_box)

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_substation)
        search_layout.addWidget(self.search_button)

        # SS_TYPE filter dropdown
        self.ss_type_dropdown = QComboBox()
        self.ss_type_dropdown.addItem("All Types")
        self.ss_type_dropdown.addItems(sorted(self.gdf["SS_TYPE"].unique()))
        self.ss_type_dropdown.currentTextChanged.connect(self.on_ss_type_changed)
        search_layout.addWidget(self.ss_type_dropdown)

        layout.addLayout(search_layout)

        button_layout = QHBoxLayout()

        self.next_button = QPushButton("Next Substation")
        self.next_button.clicked.connect(self.next_substation)
        button_layout.addWidget(self.next_button)

        self.preview_button = QPushButton("Preview and Annotate")
        self.preview_button.clicked.connect(self.preview_and_annotate)
        button_layout.addWidget(self.preview_button)

        # Transmission lines toggle
        self.show_lines_checkbox = QCheckBox("Show Transmission Lines")
        self.show_lines_checkbox.stateChanged.connect(self.toggle_transmission_lines)
        button_layout.addWidget(self.show_lines_checkbox)

        layout.addLayout(button_layout)

        self.status_label = QLabel(
            "Use 'Preview and Annotate' to take a screenshot and annotate."
        )
        layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.load_map_page()

    def load_map_page(self):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Google Maps</title>
            <script src="https://maps.googleapis.com/maps/api/js?key={self.api_key}"></script>
            <style>
                #map {{
                    height: 100%;
                    width: 100%;
                }}
                html, body {{
                    height: 100%;
                    margin: 0;
                    padding: 0;
                }}
                .ui-button {{
                    background-color: #fff;
                    border: 2px solid #fff;
                    border-radius: 3px;
                    box-shadow: 0 2px 6px rgba(0,0,0,.3);
                    color: rgb(25,25,25);
                    cursor: pointer;
                    font-family: Roboto,Arial,sans-serif;
                    font-size: 16px;
                    margin: 10px;
                    padding: 5px 10px;
                    text-align: center;
                }}
                .ui-button:hover {{
                    background-color: #ebebeb;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                var map;
                var transmissionLines = [];

                function initMap(lat, lng) {{
                    map = new google.maps.Map(document.getElementById("map"), {{
                        center: {{ lat: lat, lng: lng }},
                        zoom: 18,
                        heading: 0,
                        tilt: 0,
                        mapId: "90f87356969d889c",
                        mapTypeId: 'satellite'
                    }});

                    const buttons = [
                        ["Rotate Left", "rotate", 20, google.maps.ControlPosition.LEFT_CENTER],
                        ["Rotate Right", "rotate", -20, google.maps.ControlPosition.RIGHT_CENTER],
                        ["Tilt Down", "tilt", 20, google.maps.ControlPosition.TOP_CENTER],
                        ["Tilt Up", "tilt", -20, google.maps.ControlPosition.BOTTOM_CENTER],
                    ];

                    buttons.forEach(([text, mode, amount, position]) => {{
                        const controlDiv = document.createElement("div");
                        const controlUI = document.createElement("button");

                        controlUI.classList.add("ui-button");
                        controlUI.innerText = `${{text}}`;
                        controlUI.addEventListener("click", () => {{
                            adjustMap(mode, amount);
                        }});
                        controlDiv.appendChild(controlUI);
                        map.controls[position].push(controlDiv);
                    }});
                }}

                function adjustMap(mode, amount) {{
                    switch (mode) {{
                        case "tilt":
                            map.setTilt(map.getTilt() + amount);
                            break;
                        case "rotate":
                            map.setHeading(map.getHeading() + amount);
                            break;
                    }}
                }}

                function addTransmissionLines(lines) {{
                    clearTransmissionLines();
                    lines.forEach(line => {{
                        const path = line.map(coord => new google.maps.LatLng(coord[1], coord[0]));
                        const polyline = new google.maps.Polyline({{
                            path: path,
                            geodesic: true,
                            strokeColor: '#FF0000',
                            strokeOpacity: 1.0,
                            strokeWeight: 2
                        }});
                        polyline.setMap(map);
                        transmissionLines.push(polyline);
                    }});
                }}

                function clearTransmissionLines() {{
                    transmissionLines.forEach(line => line.setMap(null));
                    transmissionLines = [];
                }}
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html, QUrl(""))

    def update_filter(self):
        if self.ss_type == "All Types":
            self.filtered_gdf = self.gdf
        else:
            self.filtered_gdf = self.gdf[self.gdf["SS_TYPE"] == self.ss_type]
        self.current_index = 0

    def on_ss_type_changed(self, new_ss_type):
        self.ss_type = new_ss_type
        self.update_filter()
        self.update_display()

    def update_display(self):
        if len(self.filtered_gdf) > 0:
            substation = self.filtered_gdf.iloc[self.current_index]
            self.display_substation(substation)
        else:
            self.status_label.setText("No substations found with the current filter.")

    def toggle_transmission_lines(self, state):
        self.show_transmission_lines = state == 2  # 2 is checked state
        self.update_display()

    def next_substation(self):
        self.current_index += 1
        if self.current_index >= len(self.filtered_gdf):
            self.current_index = 0
        self.update_display()

    def search_substation(self):
        ss_id = self.search_box.text().strip()
        if not ss_id:
            self.status_label.setText("Please enter a Substation ID.")
            return

        try:
            ss_id = int(ss_id)
            substation = self.filtered_gdf[self.filtered_gdf["SS_ID"] == ss_id]
            if not substation.empty:
                self.current_index = self.filtered_gdf.index.get_loc(
                    substation.index[0]
                )
                self.update_display()
            else:
                self.status_label.setText(
                    f"Substation ID {ss_id} not found in the current filter."
                )
        except ValueError:
            self.status_label.setText("Invalid Substation ID. Please enter a number.")

    def display_substation(self, substation_row):
        ss_id = substation_row.SS_ID
        latitude, longitude = substation_row.lat, substation_row.lon

        # Update the map view
        js = f"initMap({latitude}, {longitude});"
        self.web_view.page().runJavaScript(js)

        if self.show_transmission_lines:
            related_lines = self.tl_gdf[
                (self.tl_gdf["substation_a"] == ss_id)
                | (self.tl_gdf["substation_b"] == ss_id)
            ]
            lines_json = (
                related_lines["geometry"].apply(lambda x: list(x.coords)).tolist()
            )
            lines_str = json.dumps(lines_json)
            self.web_view.page().runJavaScript(f"addTransmissionLines({lines_str});")
        else:
            self.web_view.page().runJavaScript("clearTransmissionLines();")

        self.status_label.setText(f"Displaying Substation ID: {ss_id}")

    def preview_and_annotate(self):
        # Capture the entire window, including the map
        full_screenshot = self.grab()

        # Show the crop window with the full screenshot
        crop_dialog = QDialog(self)
        crop_layout = QVBoxLayout(crop_dialog)
        crop_label = CropLabel(full_screenshot, crop_dialog)
        crop_layout.addWidget(crop_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(crop_dialog.accept)
        button_box.rejected.connect(crop_dialog.reject)
        crop_layout.addWidget(button_box)

        if crop_dialog.exec_() == QDialog.Accepted:
            cropped_pixmap = crop_label.get_cropped_pixmap()

            ss_id = self.filtered_gdf.iloc[self.current_index].SS_ID
            temp_file_name = f"screenshot_{ss_id}.png"
            if cropped_pixmap.save(temp_file_name):
                self.launch_labelme(temp_file_name)
            else:
                self.status_label.setText(
                    "Error: Could not save cropped image for annotation."
                )
        else:
            self.status_label.setText("Cropping cancelled. You can try again.")

    def launch_labelme(self, image_path):
        try:
            subprocess.Popen(["labelme", image_path])
            self.status_label.setText("LabelMe launched for annotation.")
        except Exception as e:
            self.status_label.setText(f"Error launching LabelMe: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = SubstationMapApp(unique_substations_gdf, transmission_lines_gdf, api_key)
    ex.show()
    sys.exit(app.exec_())
