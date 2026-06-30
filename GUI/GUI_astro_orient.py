
import sys
from datetime import datetime, timezone
from pathlib import Path

import serial.tools.list_ports
from PySide6.QtCore import QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from GPS.gps_tab import GPSDetailsTab
from IMU.imu_home_component import LiveImuOrientationWidget
from IMU.imu_tab import IMUDetailsTab

# PROJECT_ROOT = Path(__file__).resolve().parent.parent
# GPS_MODULE_DIR = PROJECT_ROOT / "GPS_IMU_Camera_Programs" / "GPS"
# if GPS_MODULE_DIR.exists():
#     sys.path.insert(0, str(GPS_MODULE_DIR))

try:
    from GUI.GPS.GPSConnector import GPSReader
except ImportError:
    GPSReader = None


class GPSWorker(QThread):
    data_ready = Signal(dict)
    status_ready = Signal(str)
    connection_ready = Signal(str, int, str)

    def __init__(self, vendor_id: int = 4292, baudrate: int = 9600):
        super().__init__()
        self.vendor_id = vendor_id
        self.baudrate = baudrate
        self._running = True
        self._gps = None

    def stop(self) -> None:
        self._running = False
        self.wait(1500)

    def run(self) -> None:
        if GPSReader is None:
            self.status_ready.emit("GPSConnector import failed")
            return

        gps_port = self._find_gps_port()
        if gps_port is None:
            self.status_ready.emit("GPS not discovered")
            self.connection_ready.emit("--", self.baudrate, "not discovered")
            return

        try:
            self._gps = GPSReader(port=gps_port, baudrate=self.baudrate, timeout=1.0)
            self._gps.connect()
            self.status_ready.emit(f"Connected on {gps_port}")
            self.connection_ready.emit(gps_port, self.baudrate, "connected")

            while self._running:
                data = self._gps.update_once()
                self.data_ready.emit(self._to_display_dict(data))
        except Exception as error:
            self.status_ready.emit(f"GPS error: {error}")
            self.connection_ready.emit(gps_port, self.baudrate, "error")
        finally:
            if self._gps is not None:
                self._gps.close()
            if not self._running:
                self.connection_ready.emit("--", self.baudrate, "disconnected")

    def _find_gps_port(self) -> str | None:
        for port in serial.tools.list_ports.comports():
            if port.vid is not None and port.vid == self.vendor_id:
                return port.device
        return None

    def _to_display_dict(self, data) -> dict:
        return {
            "latitude": self._format_number(data.latitude, 6),
            "longitude": self._format_number(data.longitude, 6),
            "altitude": self._format_number(data.altitude, 1),
            "speed": self._format_number(data.speed_over_ground_kmph, 2),
            "satellites": self._format_value(data.satellites_in_view or data.num_sat_used),
            "num_sat_used": self._format_value(data.num_sat_used),
            "pdop": self._format_number(data.pdop, 2),
            "hdop": self._format_number(data.hdop, 2),
            "vdop": self._format_number(data.vdop, 2),
            "gps_quality": self._format_value(data.gps_quality),
            "geo_separation": self._format_number(data.geo_separation, 1),
            "magnetic_track": self._format_number(data.magnetic_track, 2),
            "rmc_status": self._format_value(data.status),
            "mode_indicator": self._format_value(data.mode_indicator),
            "mode": self._format_value(data.mode),
            "fix_type": self._format_value(data.fix_type),
            "last_sentence_type": self._format_value(data.last_sentence_type),
            "parse_errors": self._format_value(data.parse_errors),
            "raw_last_line": self._format_value(data.raw_last_line),
            "status": "fix" if data.has_fix else "no fix",
            "fix_status": "fix" if data.has_fix else "no fix",
            "age": self._age_seconds(data.last_update),
            "datestamp": self._format_date(data.datestamp),
            "utc": self._format_utc(data.timestamp),
        }

    @staticmethod
    def _format_value(value) -> str:
        return "--" if value is None else str(value)

    @staticmethod
    def _format_number(value, decimals: int) -> str:
        if value is None:
            return "--"
        return f"{float(value):.{decimals}f}"

    @staticmethod
    def _age_seconds(last_update) -> str:
        if last_update is None:
            return "--"
        return f"{(datetime.now(timezone.utc) - last_update).total_seconds():.1f}"

    @staticmethod
    def _format_utc(timestamp) -> str:
        if timestamp is None:
            return "--:--:--"
        return timestamp.strftime("%H:%M:%S")

    @staticmethod
    def _format_date(datestamp) -> str:
        if datestamp is None:
            return "yyyymmdd"
        if hasattr(datestamp, "strftime"):
            return datestamp.strftime("%Y%m%d")
        digits = "".join(character for character in str(datestamp) if character.isdigit())
        if len(digits) == 8:
            return digits
        return str(datestamp)


class AspectRatioBox(QWidget):
    def __init__(self, object_name: str, ratio_width: int = 16, ratio_height: int = 10):
        super().__init__()
        self.ratio_width = ratio_width
        self.ratio_height = ratio_height
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(180)
        self.box = QFrame(self)
        self.box.setObjectName(object_name)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return int(width * self.ratio_height / self.ratio_width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        available_width = self.width()
        available_height = self.height()
        target_height = self.heightForWidth(available_width)

        if target_height <= available_height:
            content_width = available_width
            content_height = target_height
        else:
            content_height = available_height
            content_width = int(content_height * self.ratio_width / self.ratio_height)

        left = (available_width - content_width) // 2
        top = (available_height - content_height) // 2
        self.box.setGeometry(left, top, content_width, content_height)


class ValueLabel(QWidget):
    def __init__(self, name: str, value: str = "--", unit: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("fieldName")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("fieldValue")
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("fieldUnit")

        self.setMinimumHeight(32)
        layout.addWidget(self.name_label)
        layout.addStretch(1)
        layout.addWidget(self.value_label)
        if unit:
            layout.addWidget(self.unit_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_value_width(self, width: int) -> None:
        self.value_label.setFixedWidth(width)
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )


class Panel(QFrame):
    def __init__(self, title: str = ""):
        super().__init__()
        self.setObjectName("panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        self.layout.setSpacing(14)

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("panelTitle")
            self.layout.addWidget(title_label)


class AstronomyPointingGui(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Astro-orient")
        self.resize(1280, 820)

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        title = QLabel("Astro-orient")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shell_layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setExpanding(True)
        tabs.tabBar().setUsesScrollButtons(False)
        self.gps_details_tab = GPSDetailsTab()
        self.imu_details_tab = IMUDetailsTab()
        self.gps_details_tab.baud_rate_change_requested.connect(self.change_gps_baud_rate)
        self.gps_details_tab.disconnect_requested.connect(self.disconnect_gps)
        self.gps_details_tab.reconnect_requested.connect(self.reconnect_gps)
        self.imu_details_tab.tare_requested.connect(self.apply_imu_tare)
        self.imu_details_tab.reset_tare_requested.connect(self.reset_imu_tare)
        self.imu_details_tab.disconnect_requested.connect(self.disconnect_imu)
        self.imu_details_tab.reconnect_requested.connect(self.reconnect_imu)
        self.imu_details_tab.baud_rate_change_requested.connect(self.change_imu_baud_rate)
        self.imu_details_tab.component_enable_requested.connect(self.set_imu_component_enabled)
        self.imu_details_tab.update_connection_details("auto-discover", "driver default")
        tabs.addTab(self.build_home_tab(), "Main")
        tabs.addTab(self.gps_details_tab, "GPS")
        tabs.addTab(self.imu_details_tab, "IMU")
        tabs.addTab(self.placeholder_tab("Camera"), "Camera")
        tabs.addTab(self.placeholder_tab("PCB"), "PCB")
        tabs.addTab(self.placeholder_tab("Log"), "Log")

        shell_layout.addWidget(tabs)
        self.setCentralWidget(shell)
        self.apply_styles()
        self.start_gps_worker()

    def build_home_tab(self) -> QWidget:
        page = QWidget()
        root = QHBoxLayout(page)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        left_column = QVBoxLayout()
        left_column.setSpacing(16)
        right_column = QVBoxLayout()
        right_column.setSpacing(16)

        summary = self.sensor_summary_panel()
        camera = self.camera_panel()
        gps = self.gps_panel()
        imu = self.imu_panel()

        left_column.addWidget(summary)
        left_column.addWidget(imu, stretch=1)

        right_column.addWidget(camera)
        right_column.addWidget(gps, stretch=1)

        root.addLayout(left_column, stretch=4)
        root.addLayout(right_column, stretch=5)

        return page

    @staticmethod
    def sensor_summary_panel() -> Panel:
        panel = Panel("Environment / PCB")

        values = QGridLayout()
        values.setHorizontalSpacing(10)
        values.setVerticalSpacing(5)
        values.addWidget(ValueLabel("Temp", "--", "C"), 0, 0)
        values.addWidget(ValueLabel("Pressure", "--", "hPa"), 1, 0)
        values.addWidget(ValueLabel("Humidity", "--", "%"), 2, 0)
        values.addWidget(ValueLabel("Light", "--", "lux"), 3, 0)

        status = QLabel("Status: waiting for PCB")
        status.setObjectName("statusText")

        panel.layout.addLayout(values)
        panel.layout.addStretch(1)
        panel.layout.addWidget(status)
        panel.setMinimumHeight(250)
        return panel

    def gps_panel(self) -> Panel:
        panel = Panel()

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("GPS")
        title.setObjectName("gpsTitle")

        self.gps_utc_label = QLabel("UTC time:  yyyymmdd --:--:--")
        self.gps_utc_label.setObjectName("utcBox")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.gps_utc_label)
        panel.layout.addLayout(header)

        top_fields = QHBoxLayout()
        top_fields.setContentsMargins(36, 5, 36, 2)
        top_fields.setSpacing(250)

        position_column = QVBoxLayout()
        position_column.setSpacing(1)
        self.gps_lat_label = ValueLabel("Lat", "--", "deg")
        self.gps_long_label = ValueLabel("Long", "--", "deg")
        self.gps_alt_label = ValueLabel("Alt", "--", "m")
        position_column.addWidget(self.gps_lat_label)
        position_column.addWidget(self.gps_long_label)
        position_column.addWidget(self.gps_alt_label)

        quality_column = QVBoxLayout()
        quality_column.setSpacing(1)
        self.gps_speed_label = ValueLabel("Speed", "--", "km/h")
        self.gps_satellites_label = ValueLabel("# satellites", "--", "")
        self.gps_pdop_label = ValueLabel("PDOP", "--", "")
        quality_column.addWidget(self.gps_speed_label)
        quality_column.addWidget(self.gps_satellites_label)
        quality_column.addWidget(self.gps_pdop_label)

        top_fields.addLayout(position_column, stretch=1)
        top_fields.addLayout(quality_column, stretch=1)
        panel.layout.addLayout(top_fields)

        divider = QFrame()
        divider.setObjectName("panelDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        panel.layout.addWidget(divider)

        bottom_fields = QHBoxLayout()
        bottom_fields.setContentsMargins(18, 5, 18, 0)
        bottom_fields.setSpacing(200)
        self.gps_status_label = ValueLabel("Status", "not connected", "")
        self.gps_age_label = ValueLabel("Age of GPS data", "--", "s")
        bottom_fields.addWidget(self.gps_status_label)
        bottom_fields.addWidget(self.gps_age_label)
        panel.layout.addLayout(bottom_fields)
        panel.layout.addStretch(1)

        panel.setMinimumHeight(240)
        return panel

    def start_gps_worker(self) -> None:
        self.gps_worker = GPSWorker(baudrate=getattr(self, "gps_baudrate", 9600))
        self.gps_worker.data_ready.connect(self.update_gps_display)
        self.gps_worker.status_ready.connect(self.update_gps_status)
        self.gps_worker.connection_ready.connect(self.update_gps_connection_details)
        self.gps_worker.start()

    def stop_gps_worker(self) -> None:
        if hasattr(self, "gps_worker") and self.gps_worker.isRunning():
            self.gps_worker.stop()

    @Slot(int)
    def change_gps_baud_rate(self, baudrate: int) -> None:
        self.gps_baudrate = baudrate
        self.reconnect_gps()

    @Slot()
    def disconnect_gps(self) -> None:
        self.stop_gps_worker()
        self.update_gps_status("disconnected")
        self.gps_details_tab.update_connection_details("--", getattr(self, "gps_baudrate", 9600), "disconnected")

    @Slot()
    def reconnect_gps(self) -> None:
        self.stop_gps_worker()
        self.update_gps_status("reconnecting")
        self.start_gps_worker()

    @Slot(dict)
    def update_gps_display(self, data: dict) -> None:
        self.gps_lat_label.set_value(data["latitude"])
        self.gps_long_label.set_value(data["longitude"])
        self.gps_alt_label.set_value(data["altitude"])
        self.gps_speed_label.set_value(data["speed"])
        self.gps_satellites_label.set_value(data["satellites"])
        self.gps_pdop_label.set_value(data["pdop"])
        self.gps_status_label.set_value(data["status"])
        self.gps_age_label.set_value(data["age"])
        self.gps_utc_label.setText(f"UTC time:  {data['datestamp']} {data['utc']}")
        self.gps_details_tab.update_data(data)

    @Slot(str)
    def update_gps_status(self, status: str) -> None:
        self.gps_status_label.set_value(status)
        self.gps_details_tab.update_status(status)

    @Slot(str, int, str)
    def update_gps_connection_details(self, com_port: str, baudrate: int, quality: str) -> None:
        self.gps_details_tab.update_connection_details(com_port, baudrate, quality)

    def closeEvent(self, event) -> None:
        self.stop_gps_worker()
        if hasattr(self, "imu_orientation_widget"):
            self.imu_orientation_widget.shutdown()
        super().closeEvent(event)

    @staticmethod
    def camera_panel() -> Panel:
        panel = Panel("Camera")

        feed = AspectRatioBox("cameraFeed")
        feed_layout = QVBoxLayout(feed.box)
        feed_layout.setContentsMargins(0, 0, 0, 0)
        feed_label = QLabel("Camera live feed")
        feed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        feed_label.setObjectName("cameraFeedText")
        feed_layout.addWidget(feed_label)
        panel.layout.addWidget(feed, stretch=1)

        coordinate_strip = QFrame()
        coordinate_strip.setObjectName("metricStrip")
        coordinate_strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        coordinates = QGridLayout()
        coordinates.setContentsMargins(80, 40, 80, 15)
        coordinates.setHorizontalSpacing(200)
        coordinates.setVerticalSpacing(4)
        coordinates.addWidget(ValueLabel("RA", "--", "h"), 0, 0)
        coordinates.addWidget(ValueLabel("Dec", "--", "deg"), 1, 0)
        coordinates.addWidget(ValueLabel("Alt", "--", "deg"), 0, 1)
        coordinates.addWidget(ValueLabel("Az", "--", "deg"), 1, 1)
        coordinate_strip.setLayout(coordinates)
        panel.layout.addWidget(coordinate_strip)

        return panel

    def imu_panel(self) -> Panel:
        panel = Panel("IMU")

        model = AspectRatioBox("modelBox")
        model_layout = QVBoxLayout(model.box)
        model_layout.setContentsMargins(0, 0, 0, 0)
        self.imu_orientation_widget = LiveImuOrientationWidget()
        self.imu_orientation_widget.angles_changed.connect(self.update_imu_angles)
        self.imu_orientation_widget.angles_changed.connect(self.imu_details_tab.update_angles)
        self.imu_orientation_widget.sample_ready.connect(self.imu_details_tab.update_orientation_sample)
        self.imu_orientation_widget.status_changed.connect(self.imu_details_tab.update_status)
        model_layout.addWidget(self.imu_orientation_widget)
        panel.layout.addWidget(model, stretch=1)

        attitude_strip = QFrame()
        attitude_strip.setObjectName("metricStrip")
        attitude_strip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        attitude = QGridLayout()
        attitude.setContentsMargins(0, 55, 0, 0)
        attitude.setHorizontalSpacing(30)
        attitude.setVerticalSpacing(8)
        self.imu_roll_label = ValueLabel("Roll", "--", "deg")
        self.imu_pitch_label = ValueLabel("Pitch", "--", "deg")
        self.imu_yaw_label = ValueLabel("Yaw", "--", "deg")
        for angle_label in (
                self.imu_roll_label,
                self.imu_pitch_label,
                self.imu_yaw_label,
        ):
            angle_label.set_value_width(76)
        attitude.addWidget(self.imu_roll_label, 0, 0)
        attitude.addWidget(self.imu_pitch_label, 0, 1)
        attitude.addWidget(self.imu_yaw_label, 0, 2)
        attitude.setColumnStretch(0, 1)
        attitude.setColumnStretch(1, 1)
        attitude.setColumnStretch(2, 1)
        attitude_strip.setLayout(attitude)
        panel.layout.addWidget(attitude_strip)

        self.imu_orientation_widget.start()

        return panel

    @Slot(float, float, float)
    def update_imu_angles(self, pitch: float, roll: float, yaw: float) -> None:
        self.imu_roll_label.set_value(f"{roll:.2f}")
        self.imu_pitch_label.set_value(f"{pitch:.2f}")
        self.imu_yaw_label.set_value(f"{yaw:.2f}")

    @Slot()
    def apply_imu_tare(self) -> None:
        self.imu_orientation_widget.tare()
        self.imu_details_tab.apply_tare()

    @Slot()
    def reset_imu_tare(self) -> None:
        self.imu_orientation_widget.reset_tare()
        self.imu_details_tab.reset_tare()

    @Slot()
    def disconnect_imu(self) -> None:
        self.imu_orientation_widget.stop()
        self.imu_details_tab.update_status("disconnected")

    @Slot()
    def reconnect_imu(self) -> None:
        self.imu_orientation_widget.start()
        self.imu_details_tab.update_status("starting")

    @Slot(int)
    def change_imu_baud_rate(self, baudrate: int) -> None:
        self.imu_details_tab.update_connection_details("auto-discover", baudrate)
        self.imu_details_tab.update_status("baud rate selected")

    @Slot(str, bool)
    def set_imu_component_enabled(self, component: str, enabled: bool) -> None:
        self.imu_orientation_widget.set_component_enabled(component, enabled)

    @staticmethod
    def placeholder_tab(name: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 28, 28, 28)
        title = QLabel(f"{name} tab")
        title.setObjectName("placeholderTitle")
        body = QLabel("Controls and live data will go here.")
        body.setObjectName("placeholderBody")
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f7f7f7;
                color: #1f2523;
                font-family: "Open Sans", Segoe UI, Arial, sans-serif;
                font-size: 15px;
            }
            QLabel {
                background: transparent;
            }
            QLabel#appTitle {
                background: #ffffff;
                border-bottom: 2px solid #1f2523;
                font-size: 34px;
                font-weight: 750;
                padding: 16px 0 14px 0;
            }
            QTabWidget::pane {
                border-top: 2px solid #1f2523;
            }
            QTabBar::tab {
                background: #d6d5ce;
                border: 1px solid transparent;
                border-right: 2px solid #1f2523;
                padding: 4px 0;
                font-size: 14px;
                font-weight: 600;
                min-width: 160px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: 4px solid #1f2523;
            }
            QFrame#panel {
                background: #ffffff;
                border: 2px solid #1f2523;
                border-radius: 6px;
            }
            QFrame#metricStrip {
                background: transparent;
                border: none;
                min-height: 92px;
                max-height: 108px;
            }
            QLabel#panelTitle {
                font-size: 21px;
                font-weight: 700;
            }
            QLabel#gpsTitle {
                font-size: 21px;
                font-weight: 700;
            }
            QFrame#panelDivider {
                background: #1f2523;
                border: none;
                max-height: 2px;
                min-height: 2px;
                margin: 8px 12px 0 12px;
            }
            QLabel#fieldName {
                font-weight: 650;
                color: #26312e;
                min-height: 26px;
            }
            QLabel#fieldValue {
                font-family: Consolas, monospace;
                color: #0f5e50;
                font-weight: 500;
                min-height: 20px;
            }
            QLabel#fieldUnit {
                color: #5d6864;
                min-height: 26px;
            }
            QLabel#statusText {
                border-top: 1px solid #c7cbc5;
                padding-top: 12px;
                font-weight: 650;
            }
            QLabel#utcBox {
                border: 2px solid #1f2523;
                border-radius: 4px;
                padding: 8px 22px;
                background: #ffffff;
                font-family: Consolas, monospace;
                font-weight: 700;
            }
            QFrame#cameraFeed, QFrame#modelBox {
                background: #121615;
                border: 2px solid #1f2523;
                border-radius: 4px;
                min-height: 180px;
            }
            QLabel#cameraFeedText, QLabel#modelText {
                color: #d8e5df;
                font-size: 28px;
                font-weight: 650;
            }
            QLabel#placeholderTitle {
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#placeholderBody {
                color: #5d6864;
                font-size: 16px;
            }
            QPushButton {
                border: 2px solid #1f2523;
                border-radius: 4px;
                padding: 8px 14px;
                background: #ffffff;
                font-weight: 650;
            }
            QPushButton:hover {
                background: #e6f3ef;
            }
            """
        )


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(QFont("Open Sans", 10))
    window = AstronomyPointingGui()
    window.show()
    QTimer.singleShot(0, window.showMaximized)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
