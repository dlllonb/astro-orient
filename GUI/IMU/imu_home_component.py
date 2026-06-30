import sys
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

# PROJECT_ROOT = Path(__file__).resolve().parent.parent
# IMU_DRIVER_DIR = PROJECT_ROOT / "GPS_IMU_Camera_Programs" / "IMU"
# if IMU_DRIVER_DIR.exists():
#     sys.path.insert(0, str(IMU_DRIVER_DIR))

from .imu_orientation_component import Orientation3DView, ThreeSpaceQuaternionReader


class LiveImuOrientationWidget(QWidget):
    """Compact live IMU view for embedding in the Main-page 3D box."""

    angles_changed = Signal(float, float, float)
    sample_ready = Signal(object)
    status_changed = Signal(str)

    def __init__(self, port=None, render_fps: int = 30, parent=None):
        super().__init__(parent)
        self.reader = ThreeSpaceQuaternionReader(port=port, parent=self)
        self.last_sequence = 0
        self.has_rendered_sample = False

        self.view = Orientation3DView(self)
        self.view.gl_view.setMinimumSize(0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self.view.angles_changed.connect(self.angles_changed)
        self.reader.status_changed.connect(self.status_changed)

        self.render_timer = QTimer(self)
        self.render_timer.setInterval(max(1, round(1000 / render_fps)))
        self.render_timer.timeout.connect(self._render_latest)
        self.render_timer.start()

    def start(self) -> None:
        if self.reader.isRunning():
            return
        self.last_sequence = 0
        self.has_rendered_sample = False
        self.status_changed.emit("Starting...")
        self.reader.start()

    def stop(self) -> None:
        if self.reader.isRunning():
            self.reader.stop()
            self.reader.wait(1500)
        self.status_changed.emit("Stopped")

    def shutdown(self) -> None:
        self.render_timer.stop()
        self.stop()

    def tare(self) -> None:
        self.view.tare()

    def reset_tare(self) -> None:
        self.view.reset_tare()

    def set_component_enabled(self, component: str, enabled: bool) -> None:
        self.reader.set_component_enabled(component, enabled)

    def _render_latest(self) -> None:
        sequence, sample = self.reader.latest_after(self.last_sequence)
        if sample is None:
            return
        self.last_sequence = sequence
        self.view.set_matrix(sample.matrix)
        self.sample_ready.emit(sample)
        if not self.has_rendered_sample:
            self.has_rendered_sample = True
            self.status_changed.emit("Live")
