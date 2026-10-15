from PySide6.QtCore import Qt, Signal, Slot
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
    def __init__(
        self,
        name: str,
        value: str = "--",
        unit: str = "",
        value_width: int = 120,
    ):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        name_label = QLabel(name)
        name_label.setObjectName("fieldName")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("fieldValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setFixedWidth(value_width)
        unit_label = QLabel(unit)
        unit_label.setObjectName("fieldUnit")
        if unit:
            unit_label.setFixedWidth(42)

        self.setMinimumHeight(32)
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
        self.setMinimumWidth(360)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        self.layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        self.layout.addWidget(title_label)


class PCBDetailsTab(QWidget):
    disconnect_requested = Signal()
    reconnect_requested = Signal()
    baud_rate_change_requested = Signal(int)

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

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.addWidget(self._sensor_panel(), 0, 0)
        grid.addWidget(self._diagnostics_panel(), 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        content_layout.addLayout(grid)
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        root.addWidget(scroll_area)

    def _sensor_panel(self) -> DetailPanel:
        panel = DetailPanel("Environment / PCB")
        panel.layout.addWidget(self._add_row("temperature", "Temp", "--", "C"))
        panel.layout.addWidget(self._add_row("pressure", "Pressure", "--", "hPa"))
        panel.layout.addWidget(self._add_row("humidity", "Humidity", "--", "%"))
        panel.layout.addWidget(self._add_row("ambient_light", "Ambient light", "--", "%"))
        panel.layout.addWidget(self._add_row("raw_light_avg", "Raw light avg", "--"))
        panel.layout.addWidget(self._add_row("raw_light_1_avg", "Raw resistor 1 avg", "--"))
        panel.layout.addWidget(self._add_row("raw_light_2_avg", "Raw resistor 2 avg", "--"))
        panel.layout.addStretch(1)
        return panel

    def _diagnostics_panel(self) -> DetailPanel:
        panel = DetailPanel("Diagnostics")
        panel.layout.addWidget(self._add_row("com_port", "COM port", "--", "", 150))
        panel.layout.addWidget(
            self._add_row("connection_quality", "Connection quality", "not connected", "", 150)
        )
        panel.layout.addWidget(self._add_row("baudrate", "Baud rate", "115200", "", 150))

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 12, 0, 0)
        controls.setSpacing(10)
        baud_label = QLabel("Change baud rate")
        baud_label.setObjectName("fieldName")
        self.baud_selector = QComboBox()
        self.baud_selector.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_selector.setCurrentText("115200")
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
        panel.layout.addStretch(1)
        return panel

    def _add_row(
        self,
        key: str,
        name: str,
        value: str = "--",
        unit: str = "",
        value_width: int = 120,
    ) -> DetailRow:
        row = DetailRow(name, value, unit, value_width)
        self.rows[key] = row
        return row

    @Slot(dict)
    def update_data(self, data: dict) -> None:
        for key, value in data.items():
            if key in self.rows:
                self.rows[key].set_value(str(value))

    @Slot(str)
    def update_status(self, status: str) -> None:
        self.rows["connection_quality"].set_value(status)

    @Slot(str, int, str)
    def update_connection_details(self, com_port: str, baudrate: int, quality: str) -> None:
        self.rows["com_port"].set_value(com_port)
        self.rows["baudrate"].set_value(str(baudrate))
        self.rows["connection_quality"].set_value(quality)
        self.baud_selector.blockSignals(True)
        self.baud_selector.setCurrentText(str(baudrate))
        self.baud_selector.blockSignals(False)

    def _emit_baud_rate_change(self, baudrate: str) -> None:
        self.baud_rate_change_requested.emit(int(baudrate))
