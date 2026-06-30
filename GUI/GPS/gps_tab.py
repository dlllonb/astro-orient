from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class DetailRow(QWidget):
    def __init__(self, name: str, value: str = "--", unit: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        name_label = QLabel(name)
        name_label.setObjectName("fieldName")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("fieldValue")
        unit_label = QLabel(unit)
        unit_label.setObjectName("fieldUnit")

        self.setMinimumHeight(20)
        layout.addWidget(name_label)
        layout.addStretch(1)
        layout.addWidget(self.value_label)
        if unit:
            layout.addWidget(unit_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class DetailPanel(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("panel")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        self.layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        self.layout.addWidget(title_label)


class GPSDetailsTab(QWidget):
    baud_rate_change_requested = Signal(int)
    disconnect_requested = Signal()
    reconnect_requested = Signal()

    def __init__(self):
        super().__init__()
        self.rows = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        status_panel = DetailPanel("GPS Status")
        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(300)
        status_grid.setVerticalSpacing(6)
        status_grid.addWidget(self._add_row("connection", "Connection", "not connected"), 0, 0)
        status_grid.addWidget(self._add_row("fix_status", "Fix status", "no fix"), 0, 1)
        status_grid.addWidget(self._add_row("utc_full", "UTC time", "yyyymmdd --:--:--"), 1, 0)
        status_grid.addWidget(self._add_row("age", "Age of GPS data", "--", "s"), 1, 1)
        status_panel.layout.addLayout(status_grid)
        content_layout.addWidget(status_panel)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.addWidget(self._position_panel(), 0, 0)
        grid.addWidget(self._quality_panel(), 0, 1)
        grid.addWidget(self._motion_panel(), 1, 0)
        grid.addWidget(self._diagnostics_panel(), 1, 1)
        content_layout.addLayout(grid)
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        root.addWidget(scroll_area)

    def _position_panel(self) -> DetailPanel:
        panel = DetailPanel("Position")
        panel.layout.addWidget(self._add_row("latitude", "Latitude", "--", "deg"))
        panel.layout.addWidget(self._add_row("longitude", "Longitude", "--", "deg"))
        panel.layout.addWidget(self._add_row("altitude", "Altitude", "--", "m"))
        panel.layout.addWidget(self._add_row("geo_separation", "Geoidal separation", "--", "m"))
        return panel

    def _quality_panel(self) -> DetailPanel:
        panel = DetailPanel("Fix Quality")
        panel.layout.addWidget(self._add_row("satellites", "Satellites in view", "--"))
        panel.layout.addWidget(self._add_row("num_sat_used", "Satellites used", "--"))
        panel.layout.addWidget(self._add_row("gps_quality", "GPS quality", "--"))
        panel.layout.addWidget(self._add_row("pdop", "PDOP", "--"))
        panel.layout.addWidget(self._add_row("hdop", "HDOP", "--"))
        panel.layout.addWidget(self._add_row("vdop", "VDOP", "--"))
        return panel

    def _motion_panel(self) -> DetailPanel:
        panel = DetailPanel("Motion")
        panel.layout.addWidget(self._add_row("speed", "Speed", "--", "km/h"))
        panel.layout.addWidget(self._add_row("magnetic_track", "Magnetic track", "--", "deg"))
        panel.layout.addWidget(self._add_row("rmc_status", "RMC status", "--"))
        panel.layout.addWidget(self._add_row("mode_indicator", "Mode indicator", "--"))
        return panel

    def _diagnostics_panel(self) -> DetailPanel:
        panel = DetailPanel("Diagnostics")
        panel.layout.addWidget(self._add_row("com_port", "COM port", "--"))
        panel.layout.addWidget(self._add_row("connection_quality", "Connection quality", "not connected"))
        panel.layout.addWidget(self._add_row("baudrate", "Baud rate", "--"))
        #panel.layout.addWidget(self._add_row("mode", "GSA mode", "--"))
        #panel.layout.addWidget(self._add_row("fix_type", "Fix type", "--"))
        #panel.layout.addWidget(self._add_row("last_sentence_type", "Last sentence", "--"))
        #panel.layout.addWidget(self._add_row("parse_errors", "Parse errors", "0"))

        # raw_line = self._add_row("raw_last_line", "Raw last line", "--")
        # raw_line.value_label.setWordWrap(True)
        # raw_line.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # panel.layout.addWidget(raw_line)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 12, 0, 0)
        controls.setSpacing(10)

        baud_label = QLabel("Change baud rate")
        baud_label.setObjectName("fieldName")
        self.baud_selector = QComboBox()
        self.baud_selector.addItems(["4800", "9600", "19200", "38400", "57600", "115200"])
        self.baud_selector.setCurrentText("9600")
        self.baud_selector.currentTextChanged.connect(self._emit_baud_rate_change)

        disconnect_button = QPushButton("Disconnect")
        reconnect_button = QPushButton("Reconnect")
        disconnect_button.clicked.connect(self.disconnect_requested.emit)
        reconnect_button.clicked.connect(self.reconnect_requested.emit)

        controls.addWidget(baud_label)
        controls.addWidget(self.baud_selector)
        controls.addStretch(1)
        controls.addWidget(disconnect_button)
        controls.addWidget(reconnect_button)
        panel.layout.addLayout(controls)
        return panel

    def _add_row(self, key: str, name: str, value: str = "--", unit: str = "") -> DetailRow:
        row = DetailRow(name, value, unit)
        self.rows[key] = row
        return row

    def update_data(self, data: dict) -> None:
        for key, row in self.rows.items():
            if key == "utc_full":
                row.set_value(f"{data.get('datestamp', 'yyyymmdd')} {data.get('utc', '--:--:--')}")
            elif key in data:
                row.set_value(data[key])

    def update_status(self, status: str) -> None:
        self.rows["connection"].set_value(status)

    def update_connection_details(self, com_port: str, baudrate: int, quality: str) -> None:
        self.rows["com_port"].set_value(com_port)
        self.rows["baudrate"].set_value(str(baudrate))
        self.rows["connection_quality"].set_value(quality)
        self.baud_selector.blockSignals(True)
        self.baud_selector.setCurrentText(str(baudrate))
        self.baud_selector.blockSignals(False)

    def _emit_baud_rate_change(self, baudrate: str) -> None:
        self.baud_rate_change_requested.emit(int(baudrate))
