from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .imu_orientation_component import Orientation3DView


class DetailRow(QWidget):
    def __init__(
        self,
        name: str,
        value: str = "--",
        unit: str = "",
        value_width: int | None = None,
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
        if value_width is not None:
            self.value_label.setFixedWidth(value_width)
        unit_label = QLabel(unit)
        unit_label.setObjectName("fieldUnit")

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

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 16, 18, 16)
        self.layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("panelTitle")
        self.layout.addWidget(title_label)


class IMUDetailsTab(QWidget):
    tare_requested = Signal()
    reset_tare_requested = Signal()
    disconnect_requested = Signal()
    reconnect_requested = Signal()
    baud_rate_change_requested = Signal(int)
    component_enable_requested = Signal(str, bool)

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

        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(16)
        top_grid.setVerticalSpacing(16)
        top_grid.addWidget(self._orientation_panel(), 0, 0, 2, 1)
        top_grid.addWidget(self._calibration_panel(), 0, 1)
        top_grid.addWidget(self._diagnostics_panel(), 1, 1)
        top_grid.setColumnStretch(0, 3)
        top_grid.setColumnStretch(1, 2)
        content_layout.addLayout(top_grid)

        readings_grid = QGridLayout()
        readings_grid.setHorizontalSpacing(16)
        readings_grid.setVerticalSpacing(16)
        readings_grid.addWidget(self._motion_panel(), 0, 0)
        readings_grid.addWidget(self._raw_sensor_panel(), 0, 1)
        content_layout.addLayout(readings_grid)
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        root.addWidget(scroll_area)

    def _orientation_panel(self) -> DetailPanel:
        panel = DetailPanel("Orientation")
        self.view = Orientation3DView()
        self.view.gl_view.setMinimumSize(0, 0)
        self.view.setMinimumHeight(360)
        self.view.top_state_changed.connect(self._update_top_state)
        panel.layout.addWidget(self.view, stretch=1)

        angle_grid = QGridLayout()
        angle_grid.setHorizontalSpacing(30)
        angle_grid.setVerticalSpacing(8)
        angle_grid.addWidget(self._add_row("roll", "Roll", "--", "deg"), 0, 0)
        angle_grid.addWidget(self._add_row("pitch", "Pitch", "--", "deg"), 0, 1)
        angle_grid.addWidget(self._add_row("yaw", "Yaw", "--", "deg"), 0, 2)
        panel.layout.addLayout(angle_grid)
        return panel

    def _calibration_panel(self) -> DetailPanel:
        panel = DetailPanel("Calibration")
        reset_button = QPushButton("Reset base offset")
        tare_button = QPushButton("Set base offset to current orientation")
        reset_button.clicked.connect(self.reset_tare_requested.emit)
        tare_button.clicked.connect(self.tare_requested.emit)

        self.local_tare_checkbox = QCheckBox("Use local base offset")
        self.local_tare_checkbox.setChecked(True)
        self.invert_checkbox = QCheckBox("Invert orientation")
        self.local_tare_checkbox.toggled.connect(self.view.set_local_tare_enabled)
        self.invert_checkbox.toggled.connect(self.view.set_inverted)

        panel.layout.addWidget(reset_button)
        panel.layout.addWidget(tare_button)
        panel.layout.addSpacing(8)
        panel.layout.addWidget(self.local_tare_checkbox)
        panel.layout.addWidget(self.invert_checkbox)
        panel.layout.addStretch(1)
        return panel

    def _diagnostics_panel(self) -> DetailPanel:
        panel = DetailPanel("Diagnostics")
        panel.layout.addWidget(self._add_row("com_port", "COM port", "--"))
        panel.layout.addWidget(self._add_row("connection_quality", "Connection quality", "not connected"))
        panel.layout.addWidget(self._add_row("baudrate", "Baud rate", "--"))
        panel.layout.addWidget(self._add_row("top_state", "Top orientation", "--"))

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 12, 0, 0)
        controls.setSpacing(10)

        baud_label = QLabel("Change baud rate")
        baud_label.setObjectName("fieldName")
        self.baud_selector = QComboBox()
        self.baud_selector.addItems(["9600", "19200", "38400", "57600", "115200", "921600"])
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
        return panel

    def _motion_panel(self) -> DetailPanel:
        panel = DetailPanel("Motion")
        vector_width = 310
        panel.layout.addWidget(self._add_row("gyro_rate", "Gyro rate", "--", "rad/s", vector_width))
        panel.layout.addWidget(self._add_row("accelerometer", "Accelerometer", "--", "G", vector_width))
        panel.layout.addWidget(self._add_row("compass", "Compass", "--", "gauss", vector_width))
        panel.layout.addWidget(self._add_row("confidence", "Confidence factor", "--"))
        panel.layout.addWidget(self._add_row("imu_temp", "IMU temp", "--", "C"))
        return panel

    def _raw_sensor_panel(self) -> DetailPanel:
        panel = DetailPanel("Sensor Channels")
        self.gyro_toggle = QCheckBox("Enable gyroscope")
        self.accel_toggle = QCheckBox("Enable accelerometer")
        self.compass_toggle = QCheckBox("Enable compass")
        self.gyro_toggle.setChecked(True)
        self.accel_toggle.setChecked(True)
        self.compass_toggle.setChecked(True)
        self.gyro_toggle.toggled.connect(
            lambda enabled: self.component_enable_requested.emit("gyro", enabled)
        )
        self.accel_toggle.toggled.connect(
            lambda enabled: self.component_enable_requested.emit("accelerometer", enabled)
        )
        self.compass_toggle.toggled.connect(
            lambda enabled: self.component_enable_requested.emit("compass", enabled)
        )
        panel.layout.addWidget(self.gyro_toggle)
        panel.layout.addWidget(self.accel_toggle)
        panel.layout.addWidget(self.compass_toggle)
        panel.layout.addStretch(1)
        return panel

    def _add_row(
        self,
        key: str,
        name: str,
        value: str = "--",
        unit: str = "",
        value_width: int | None = None,
    ) -> DetailRow:
        row = DetailRow(name, value, unit, value_width)
        self.rows[key] = row
        return row

    @Slot(float, float, float)
    def update_angles(self, pitch: float, roll: float, yaw: float) -> None:
        self.rows["roll"].set_value(f"{roll:.2f}")
        self.rows["pitch"].set_value(f"{pitch:.2f}")
        self.rows["yaw"].set_value(f"{yaw:.2f}")

    @Slot(object)
    def update_orientation_sample(self, sample) -> None:
        self.view.set_matrix(sample.matrix)
        self.rows["gyro_rate"].set_value(self._format_vector(sample.gyro_rate))
        self.rows["accelerometer"].set_value(self._format_vector(sample.accelerometer))
        self.rows["compass"].set_value(self._format_vector(sample.compass))
        self.rows["confidence"].set_value(self._format_scalar(sample.confidence, 3))
        self.rows["imu_temp"].set_value(self._format_scalar(sample.temperature_c, 2))
        self._set_toggle_state(self.gyro_toggle, sample.gyro_enabled)
        self._set_toggle_state(self.accel_toggle, sample.accelerometer_enabled)
        self._set_toggle_state(self.compass_toggle, sample.compass_enabled)

    @Slot(str)
    def update_status(self, status: str) -> None:
        self.rows["connection_quality"].set_value(status)

    def update_connection_details(self, com_port: str = "--", baudrate: int | str = "--") -> None:
        self.rows["com_port"].set_value(str(com_port))
        self.rows["baudrate"].set_value(str(baudrate))
        if str(baudrate) in [self.baud_selector.itemText(i) for i in range(self.baud_selector.count())]:
            self.baud_selector.blockSignals(True)
            self.baud_selector.setCurrentText(str(baudrate))
            self.baud_selector.blockSignals(False)

    def apply_tare(self) -> None:
        self.view.tare()

    def reset_tare(self) -> None:
        self.view.reset_tare()

    def _update_top_state(self, state: str, top_z: float) -> None:
        self.rows["top_state"].set_value(f"{state} ({top_z:.2f})")

    def _emit_baud_rate_change(self, baudrate: str) -> None:
        self.baud_rate_change_requested.emit(int(baudrate))

    @staticmethod
    def _format_vector(values) -> str:
        if values is None:
            return "--"
        return "x {0:+08.3f}   y {1:+08.3f}   z {2:+08.3f}".format(*values)

    @staticmethod
    def _format_scalar(value, decimals: int) -> str:
        if value is None:
            return "--"
        return f"{value:.{decimals}f}"

    @staticmethod
    def _set_toggle_state(toggle: QCheckBox, enabled) -> None:
        if enabled is None:
            return
        toggle.blockSignals(True)
        toggle.setChecked(bool(enabled))
        toggle.blockSignals(False)
