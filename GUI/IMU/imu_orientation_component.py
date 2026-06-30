import math
import sys
import time
from dataclasses import dataclass
from threading import Lock

import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)




def identity_matrix():
    return np.eye(3, dtype=float)


def normalize_quaternion(w, x, y, z):
    quaternion = np.array([w, x, y, z], dtype=float)
    length = np.linalg.norm(quaternion)
    if length == 0:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=float)
    return quaternion / length


def quaternion_to_matrix(w, x, y, z):
    """Convert a w, x, y, z quaternion to a 3x3 active rotation matrix."""
    w, x, y, z = normalize_quaternion(w, x, y, z)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def matrix_to_pitch_roll_yaw(matrix):
    """Return conventional ZYX pitch, roll and yaw angles in degrees."""
    matrix = np.asarray(matrix, dtype=float)
    pitch_radians = math.asin(max(-1.0, min(1.0, -float(matrix[2, 0]))))
    if abs(math.cos(pitch_radians)) > 1e-7:
        roll_radians = math.atan2(float(matrix[2, 1]), float(matrix[2, 2]))
        yaw_radians = math.atan2(float(matrix[1, 0]), float(matrix[0, 0]))
    else:
        roll_radians = math.atan2(-float(matrix[1, 2]), float(matrix[1, 1]))
        yaw_radians = 0.0
    return tuple(map(math.degrees, (pitch_radians, roll_radians, yaw_radians)))


def relative_rotation(reference_matrix, current_matrix):
    """Express current_matrix relative to reference_matrix."""
    return np.asarray(reference_matrix).T @ np.asarray(current_matrix)


def rotated_top_vector(matrix):
    return np.asarray(matrix, dtype=float) @ np.array([0.0, 0.0, 1.0])


@dataclass(frozen=True)
class OrientationSample:
    quaternion: tuple
    matrix: np.ndarray
    timestamp: float
    gyro_rate: tuple | None = None
    accelerometer: tuple | None = None
    compass: tuple | None = None
    temperature_c: float | None = None
    confidence: float | None = None
    gyro_enabled: bool | None = None
    accelerometer_enabled: bool | None = None
    compass_enabled: bool | None = None


class ThreeSpaceQuaternionReader(QThread):
    """Read the newest ThreeSpace quaternion without queueing every sample."""

    status_changed = Signal(str)

    def __init__(self, port=None, poll_interval=0.01, parent=None):
        super().__init__(parent)
        self.port = port
        self.poll_interval = poll_interval
        self._running = False
        self._sensor = None
        self._lock = Lock()
        self._latest_sample = None
        self._sequence = 0
        self._pending_controls = []

    def run(self):
        self._running = True
        try:
            import USB_ExampleClass
            from ThreeSpaceAPI import ThreeSpaceSensor

            communication = USB_ExampleClass.UsbCom(portName=self.port)
            self._sensor = ThreeSpaceSensor(communication)
            port_name = self.port or getattr(communication, "portName", "auto")
            self.status_changed.emit(f"Connected: {port_name}")

            while self._running:
                self._apply_pending_controls()
                result = self._sensor.getTaredOrientation()
                if result != -1 and len(result) >= 4:
                    # The response can contain header values before the quaternion.
                    quaternion = tuple(float(value) for value in result[-4:])
                    gyro_rate, accelerometer, compass = self._read_component_vectors()
                    sample = OrientationSample(
                        quaternion=quaternion,
                        matrix=quaternion_to_matrix(*quaternion),
                        timestamp=time.monotonic(),
                        gyro_rate=gyro_rate,
                        accelerometer=accelerometer,
                        compass=compass,
                        temperature_c=self._read_scalar("getTemperatureC"),
                        confidence=self._read_scalar("getConfidenceFactor"),
                        gyro_enabled=self._read_enabled_state("getGyroscopeEnabledState"),
                        accelerometer_enabled=self._read_enabled_state("getAccelerometerEnabledState"),
                        compass_enabled=self._read_enabled_state("getCompassEnabledState"),
                    )
                    with self._lock:
                        self._latest_sample = sample
                        self._sequence += 1
                time.sleep(self.poll_interval)
        except (Exception, SystemExit) as exc:
            self.status_changed.emit(f"IMU error: {exc}")
        finally:
            self._cleanup_sensor()
            self._running = False

    def stop(self):
        self._running = False

    def set_component_enabled(self, component: str, enabled: bool):
        with self._lock:
            self._pending_controls.append((component, bool(enabled)))

    def latest_after(self, previous_sequence):
        with self._lock:
            if self._sequence == previous_sequence:
                return previous_sequence, None
            return self._sequence, self._latest_sample

    def _apply_pending_controls(self):
        with self._lock:
            controls = self._pending_controls
            self._pending_controls = []
        for component, enabled in controls:
            try:
                if component == "gyro":
                    self._sensor.setGyroscopeEnabled(enabled)
                elif component == "accelerometer":
                    self._sensor.setAccelerometerEnabled(enabled)
                elif component == "compass":
                    self._sensor.setCompassEnabled(enabled)
            except Exception as exc:
                self.status_changed.emit(f"IMU control error: {exc}")

    def _read_component_vectors(self):
        values = self._read_value("getAllCorrectedComponentSensorData")
        if values is None or len(values) < 9:
            return None, None, None
        values = tuple(float(value) for value in values[-9:])
        return values[0:3], values[3:6], values[6:9]

    def _read_scalar(self, method_name):
        values = self._read_value(method_name)
        if values is None:
            return None
        if isinstance(values, (list, tuple)):
            if not values:
                return None
            return float(values[-1])
        return float(values)

    def _read_enabled_state(self, method_name):
        values = self._read_value(method_name)
        if values is None:
            return None
        if isinstance(values, (list, tuple)):
            if not values:
                return None
            values = values[-1]
        return bool(values)

    def _read_value(self, method_name):
        try:
            value = getattr(self._sensor, method_name)()
        except Exception:
            return None
        if value == -1:
            return None
        return value

    def _cleanup_sensor(self):
        if self._sensor is not None:
            try:
                self._sensor.cleanup()
            except Exception:
                pass
            self._sensor = None


class Orientation3DView(QWidget):
    """Reusable OpenGL orientation view with GUI-local tare support."""

    angles_changed = Signal(float, float, float)
    top_state_changed = Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_matrix = identity_matrix()
        self.tare_matrix = identity_matrix()
        self.local_tare_enabled = True
        self.inverted = False

        self.base_vertices = np.array(
            [
                [-2.8, -1.4, -0.7],
                [2.8, -1.4, -0.7],
                [2.8, 1.4, -0.7],
                [-2.8, 1.4, -0.7],
                [-2.8, -1.4, 0.7],
                [2.8, -1.4, 0.7],
                [2.8, 1.4, 0.7],
                [-2.8, 1.4, 0.7],
            ],
            dtype=float,
        )
        self.faces = np.array(
            [
                [0, 1, 2], [0, 2, 3],
                [4, 6, 5], [4, 7, 6],
                [0, 5, 1], [0, 4, 5],
                [1, 6, 2], [1, 5, 6],
                [2, 7, 3], [2, 6, 7],
                [3, 4, 0], [3, 7, 4],
            ],
            dtype=int,
        )
        self.face_colors = np.array(
            [
                [0.90, 0.18, 0.17, 0.86], [0.90, 0.18, 0.17, 0.86],
                [0.10, 0.55, 1.00, 0.94], [0.10, 0.55, 1.00, 0.94],
                [0.98, 0.72, 0.19, 0.74], [0.98, 0.72, 0.19, 0.74],
                [0.34, 0.82, 0.45, 0.74], [0.34, 0.82, 0.45, 0.74],
                [0.63, 0.45, 0.89, 0.74], [0.63, 0.45, 0.89, 0.74],
                [0.20, 0.78, 0.85, 0.74], [0.20, 0.78, 0.85, 0.74],
            ],
            dtype=float,
        )

        self.gl_view = gl.GLViewWidget()
        self.gl_view.setMinimumSize(480, 360)
        self.gl_view.setBackgroundColor("#101820")
        self.gl_view.setCameraPosition(distance=12, elevation=24, azimuth=42)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.gl_view)
        self._build_scene()
        self.set_matrix(identity_matrix())

    def _build_scene(self):
        grid = gl.GLGridItem()
        grid.setSize(12, 12, 1)
        grid.setSpacing(1, 1, 1)
        self.gl_view.addItem(grid)

        self.mesh = gl.GLMeshItem(
            vertexes=self.base_vertices,
            faces=self.faces,
            faceColors=self.face_colors,
            drawEdges=True,
            edgeColor=(0.92, 0.96, 0.98, 1.0),
            smooth=False,
            shader="shaded",
        )
        self.gl_view.addItem(self.mesh)

        self.body_axes = []
        self._add_axis((4, 0, 0), (1.0, 0.18, 0.20, 1.0), rotate=False)
        self._add_axis((0, 4, 0), (0.25, 0.86, 0.55, 1.0), rotate=False)
        self._add_axis((0, 0, 4), (0.28, 0.67, 1.0, 1.0), rotate=False)
        self._add_axis((3.5, 0, 0), (1.0, 0.38, 0.40, 1.0), rotate=True)
        self._add_axis((0, 2.5, 0), (0.38, 0.90, 0.66, 1.0), rotate=True)
        self._add_axis((0, 0, 2.0), (0.45, 0.75, 1.0, 1.0), rotate=True)

    def _add_axis(self, endpoint, color, rotate):
        points = np.array([[0.0, 0.0, 0.0], endpoint], dtype=float)
        line = gl.GLLinePlotItem(pos=points, color=color, width=4, antialias=True)
        self.gl_view.addItem(line)
        if rotate:
            self.body_axes.append((line, points))

    def set_quaternion(self, w, x, y, z):
        self.set_matrix(quaternion_to_matrix(w, x, y, z))

    def set_matrix(self, matrix):
        self.raw_matrix = np.asarray(matrix, dtype=float)
        self._refresh()

    def tare(self):
        self.tare_matrix = self._effective_raw_matrix().copy()
        self._refresh()

    def reset_tare(self):
        self.tare_matrix = identity_matrix()
        self._refresh()

    def set_local_tare_enabled(self, enabled):
        self.local_tare_enabled = bool(enabled)
        self._refresh()

    def set_inverted(self, inverted):
        self.inverted = bool(inverted)
        self.reset_tare()

    def displayed_matrix(self):
        matrix = self._effective_raw_matrix()
        if self.local_tare_enabled:
            matrix = relative_rotation(self.tare_matrix, matrix)
        return matrix

    def _effective_raw_matrix(self):
        return self.raw_matrix.T if self.inverted else self.raw_matrix

    def _refresh(self):
        matrix = self.displayed_matrix()
        self.mesh.setMeshData(
            vertexes=self.base_vertices @ matrix.T,
            faces=self.faces,
            faceColors=self.face_colors,
        )
        for line, points in self.body_axes:
            line.setData(pos=points @ matrix.T)

        pitch, roll, yaw = matrix_to_pitch_roll_yaw(matrix)
        top_z = float(rotated_top_vector(matrix)[2])
        if top_z > 0.25:
            top_state = "up"
        elif top_z < -0.25:
            top_state = "down / inverted"
        else:
            top_state = "sideways"
        self.angles_changed.emit(pitch, roll, yaw)
        self.top_state_changed.emit(top_state, top_z)


class ImuOrientationPanel(QWidget):
    """Drop-in PySide6 panel containing the live view and standard controls."""

    angles_changed = Signal(float, float, float)
    orientation_changed = Signal(object)

    def __init__(self, port=None, render_fps=30, parent=None):
        super().__init__(parent)
        self.reader = ThreeSpaceQuaternionReader(port=port, parent=self)
        self.last_sequence = 0

        self.view = Orientation3DView()
        self.pitch_label = QLabel("Pitch 0.00 deg")
        self.roll_label = QLabel("Roll 0.00 deg")
        self.yaw_label = QLabel("Yaw 0.00 deg")
        self.top_label = QLabel("Top: up")
        self.status_label = QLabel("Stopped")

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.tare_button = QPushButton("Tare")
        self.reset_tare_button = QPushButton("Reset tare")
        self.local_tare_checkbox = QCheckBox("Local tare")
        self.invert_checkbox = QCheckBox("Invert rotation")
        self.local_tare_checkbox.setChecked(True)
        self.stop_button.setEnabled(False)

        readings = QHBoxLayout()
        readings.addWidget(self.pitch_label)
        readings.addWidget(self.roll_label)
        readings.addWidget(self.yaw_label)
        readings.addStretch(1)
        readings.addWidget(self.top_label)

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.tare_button)
        controls.addWidget(self.reset_tare_button)
        controls.addWidget(self.local_tare_checkbox)
        controls.addWidget(self.invert_checkbox)
        controls.addStretch(1)
        controls.addWidget(self.status_label)

        layout = QVBoxLayout(self)
        layout.addWidget(self.view, 1)
        layout.addLayout(readings)
        layout.addLayout(controls)

        self.start_button.clicked.connect(self.start)
        self.stop_button.clicked.connect(self.stop)
        self.tare_button.clicked.connect(self.view.tare)
        self.reset_tare_button.clicked.connect(self.view.reset_tare)
        self.local_tare_checkbox.toggled.connect(self.view.set_local_tare_enabled)
        self.invert_checkbox.toggled.connect(self.view.set_inverted)
        self.view.angles_changed.connect(self._update_angles)
        self.view.top_state_changed.connect(self._update_top_state)
        self.reader.status_changed.connect(self.status_label.setText)
        self.reader.finished.connect(self._reader_finished)

        self.render_timer = QTimer(self)
        self.render_timer.setInterval(max(1, round(1000 / render_fps)))
        self.render_timer.timeout.connect(self._render_latest)
        self.render_timer.start()

    def start(self):
        if self.reader.isRunning():
            return
        self.last_sequence = 0
        self.reader.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Starting...")

    def stop(self):
        if self.reader.isRunning():
            self.reader.stop()
            self.reader.wait(1500)
        self._reader_finished()

    def shutdown(self):
        self.render_timer.stop()
        self.stop()

    def tare(self):
        self.view.tare()

    def reset_tare(self):
        self.view.reset_tare()

    def _render_latest(self):
        sequence, sample = self.reader.latest_after(self.last_sequence)
        if sample is None:
            return
        self.last_sequence = sequence
        self.view.set_matrix(sample.matrix)
        self.orientation_changed.emit(sample)

    def _update_angles(self, pitch, roll, yaw):
        self.pitch_label.setText(f"Pitch {pitch:7.2f} deg")
        self.roll_label.setText(f"Roll {roll:7.2f} deg")
        self.yaw_label.setText(f"Yaw {yaw:7.2f} deg")
        self.angles_changed.emit(pitch, roll, yaw)

    def _update_top_state(self, state, top_z):
        self.top_label.setText(f"Top: {state}    z {top_z: .2f}")

    def _reader_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def closeEvent(self, event):
        self.shutdown()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    panel = ImuOrientationPanel()
    panel.resize(900, 650)
    panel.show()
    panel.start()
    sys.exit(app.exec())
