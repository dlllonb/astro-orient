from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
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


class CameraPreview(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("cameraFeed")
        self.latest_image = QImage()

        self.label = QLabel("Camera live feed")
        self.label.setObjectName("cameraFeedText")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumSize(0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    @Slot(QImage)
    def update_frame(self, image: QImage) -> None:
        self.latest_image = image
        self._refresh_pixmap()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self.latest_image.isNull():
            return
        pixmap = QPixmap.fromImage(self.latest_image)
        scaled = pixmap.scaled(
            self.label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.label.setPixmap(scaled)


class CameraDetailsTab(QWidget):
    disconnect_requested = Signal()
    reconnect_requested = Signal()
    format_change_requested = Signal(int, int, int)
    exposure_change_requested = Signal(int, bool)
    gain_change_requested = Signal(int)
    brightness_change_requested = Signal(int)

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
        top_grid.addWidget(self._preview_panel(), 0, 0, 2, 1)
        top_grid.addWidget(self._image_controls_panel(), 0, 1)
        top_grid.addWidget(self._connection_panel(), 1, 1)
        top_grid.setColumnStretch(0, 3)
        top_grid.setColumnStretch(1, 2)
        content_layout.addLayout(top_grid)

        metadata_grid = QGridLayout()
        metadata_grid.setHorizontalSpacing(16)
        metadata_grid.addWidget(self._pointing_panel(), 0, 0)
        metadata_grid.addWidget(self._capture_info_panel(), 0, 1)
        content_layout.addLayout(metadata_grid)
        content_layout.addStretch(1)

        scroll_area.setWidget(content)
        root.addWidget(scroll_area)

    def _preview_panel(self) -> DetailPanel:
        panel = DetailPanel("Live Feed")
        self.preview = CameraPreview()
        panel.layout.addWidget(self.preview, stretch=1)
        return panel

    def _image_controls_panel(self) -> DetailPanel:
        panel = DetailPanel("Capture Controls")

        exposure_layout = QGridLayout()
        exposure_layout.setHorizontalSpacing(10)
        exposure_layout.setVerticalSpacing(8)

        self.auto_exposure = QCheckBox("Auto exposure")
        self.auto_exposure.setChecked(True)
        self.exposure_slider = QSlider(Qt.Orientation.Horizontal)
        self.exposure_slider.setRange(-13, 0)
        self.exposure_slider.setValue(-6)
        self.exposure_spin = QSpinBox()
        self.exposure_spin.setRange(-13, 0)
        self.exposure_spin.setValue(-6)
        self.exposure_slider.valueChanged.connect(self.exposure_spin.setValue)
        self.exposure_spin.valueChanged.connect(self.exposure_slider.setValue)
        self.exposure_slider.valueChanged.connect(self._emit_exposure_change)
        self.auto_exposure.toggled.connect(self._emit_exposure_change)

        exposure_layout.addWidget(self.auto_exposure, 0, 0, 1, 3)
        exposure_layout.addWidget(QLabel("Exposure"), 1, 0)
        exposure_layout.addWidget(self.exposure_slider, 1, 1)
        exposure_layout.addWidget(self.exposure_spin, 1, 2)
        panel.layout.addLayout(exposure_layout)

        panel.layout.addSpacing(12)

        image_layout = QGridLayout()
        image_layout.setHorizontalSpacing(10)
        image_layout.setVerticalSpacing(8)

        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(0, 255)
        self.gain_slider.setValue(0)
        self.gain_spin = QSpinBox()
        self.gain_spin.setRange(0, 255)
        self.gain_spin.setValue(0)
        self.gain_slider.valueChanged.connect(self.gain_spin.setValue)
        self.gain_spin.valueChanged.connect(self.gain_slider.setValue)
        self.gain_slider.valueChanged.connect(self.gain_change_requested.emit)

        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(0, 255)
        self.brightness_slider.setValue(0)
        self.brightness_spin = QSpinBox()
        self.brightness_spin.setRange(0, 255)
        self.brightness_spin.setValue(0)
        self.brightness_slider.valueChanged.connect(self.brightness_spin.setValue)
        self.brightness_spin.valueChanged.connect(self.brightness_slider.setValue)
        self.brightness_slider.valueChanged.connect(self.brightness_change_requested.emit)

        image_layout.addWidget(QLabel("Gain"), 0, 0)
        image_layout.addWidget(self.gain_slider, 0, 1)
        image_layout.addWidget(self.gain_spin, 0, 2)
        image_layout.addWidget(QLabel("Brightness"), 1, 0)
        image_layout.addWidget(self.brightness_slider, 1, 1)
        image_layout.addWidget(self.brightness_spin, 1, 2)
        panel.layout.addLayout(image_layout)

        panel.layout.addSpacing(12)
        self.resolution_selector = QComboBox()
        self.resolution_selector.addItems(
            [
                "1920 x 1080",
                "1280 x 720",
                "1024 x 576",
                "640 x 480",
            ]
        )
        self.resolution_selector.setCurrentText("1280 x 720")

        self.fps_selector = QComboBox()
        self.fps_selector.addItems(["5", "10", "15", "30"])
        self.fps_selector.setCurrentText("30")

        format_layout = QGridLayout()
        format_layout.setHorizontalSpacing(10)
        format_layout.setVerticalSpacing(10)
        format_layout.addWidget(QLabel("Resolution"), 0, 0)
        format_layout.addWidget(self.resolution_selector, 0, 1)
        format_layout.addWidget(QLabel("FPS"), 1, 0)
        format_layout.addWidget(self.fps_selector, 1, 1)

        apply_button = QPushButton("Apply format")
        apply_button.clicked.connect(self._emit_format_change)
        format_layout.addWidget(apply_button, 2, 0, 1, 2)
        panel.layout.addLayout(format_layout)
        panel.layout.addStretch(1)
        return panel

    def _connection_panel(self) -> DetailPanel:
        panel = DetailPanel("USB Camera")
        panel.layout.addWidget(self._add_row("device_name", "Device", "Arducam"))
        panel.layout.addWidget(self._add_row("device_index", "Device index", "--"))
        panel.layout.addWidget(self._add_row("connection_quality", "Connection quality", "not connected"))
        panel.layout.addWidget(self._add_row("interface", "Interface", "USB UVC / DirectShow"))

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 12, 0, 0)
        disconnect_button = QPushButton("Disconnect")
        reconnect_button = QPushButton("Reconnect")
        disconnect_button.clicked.connect(self.disconnect_requested.emit)
        reconnect_button.clicked.connect(self.reconnect_requested.emit)
        controls.addStretch(1)
        controls.addWidget(disconnect_button)
        controls.addWidget(reconnect_button)
        panel.layout.addLayout(controls)
        return panel

    def _capture_info_panel(self) -> DetailPanel:
        panel = DetailPanel("Capture Info")
        panel.layout.addWidget(self._add_row("requested_resolution", "Requested resolution", "1280 x 720"))
        panel.layout.addWidget(self._add_row("actual_resolution", "Actual resolution", "--"))
        panel.layout.addWidget(self._add_row("requested_fps", "Requested FPS", "30"))
        panel.layout.addWidget(self._add_row("actual_fps", "Actual FPS", "--"))
        panel.layout.addWidget(self._add_row("auto_exposure", "Exposure mode", "auto"))
        panel.layout.addWidget(self._add_row("exposure", "Exposure value", "--"))
        panel.layout.addWidget(self._add_row("gain", "Gain", "--"))
        panel.layout.addWidget(self._add_row("brightness", "Brightness", "--"))
        return panel

    def _pointing_panel(self) -> DetailPanel:
        panel = DetailPanel("Pointing")
        panel.layout.addWidget(self._add_row("ra", "RA", "--", "h"))
        panel.layout.addWidget(self._add_row("dec", "Dec", "--", "deg"))
        panel.layout.addWidget(self._add_row("alt", "Alt", "--", "deg"))
        panel.layout.addWidget(self._add_row("az", "Az", "--", "deg"))
        panel.layout.addWidget(self._add_row("platesolve_status", "Platesolve status", "not run"))
        panel.layout.addWidget(self._add_row("time_since_platesolve", "Time since last platesolve", "--", "s"))
        return panel

    def _add_row(self, key: str, name: str, value: str = "--", unit: str = "") -> DetailRow:
        row = DetailRow(name, value, unit)
        self.rows[key] = row
        return row

    @Slot(QImage)
    def update_frame(self, image: QImage) -> None:
        self.preview.update_frame(image)

    @Slot(str)
    def update_status(self, status: str) -> None:
        self.rows["connection_quality"].set_value(status)

    @Slot(dict)
    def update_settings(self, settings: dict) -> None:
        for key, value in settings.items():
            if key in self.rows:
                self.rows[key].set_value(str(value))
        if "requested_resolution" in settings:
            self.resolution_selector.blockSignals(True)
            self.resolution_selector.setCurrentText(settings["requested_resolution"])
            self.resolution_selector.blockSignals(False)
        if "requested_fps" in settings:
            self.fps_selector.blockSignals(True)
            self.fps_selector.setCurrentText(settings["requested_fps"])
            self.fps_selector.blockSignals(False)
        if "auto_exposure" in settings:
            self.auto_exposure.blockSignals(True)
            self.auto_exposure.setChecked(settings["auto_exposure"] == "auto")
            self.auto_exposure.blockSignals(False)
        if "gain" in settings:
            self._set_spin_slider_pair(self.gain_spin, self.gain_slider, settings["gain"])
        if "brightness" in settings:
            self._set_spin_slider_pair(
                self.brightness_spin,
                self.brightness_slider,
                settings["brightness"],
            )

    def _emit_format_change(self) -> None:
        width_text, height_text = self.resolution_selector.currentText().split(" x ")
        self.format_change_requested.emit(
            int(width_text),
            int(height_text),
            int(self.fps_selector.currentText()),
        )

    def _emit_exposure_change(self, *args) -> None:
        self.exposure_change_requested.emit(
            self.exposure_spin.value(),
            self.auto_exposure.isChecked(),
        )

    @staticmethod
    def _set_spin_slider_pair(spinbox: QSpinBox, slider: QSlider, value: str) -> None:
        try:
            numeric_value = int(float(value))
        except ValueError:
            return
        numeric_value = max(slider.minimum(), min(slider.maximum(), numeric_value))
        spinbox.blockSignals(True)
        slider.blockSignals(True)
        spinbox.setValue(numeric_value)
        slider.setValue(numeric_value)
        spinbox.blockSignals(False)
        slider.blockSignals(False)
