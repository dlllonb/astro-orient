import time
from threading import Lock

from PySide6.QtCore import QThread, Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    status_ready = Signal(str)
    settings_ready = Signal(dict)

    def __init__(
        self,
        keyword: str = "Arducam",
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        exposure: int | None = None,
        auto_exposure: bool = True,
        gain: int = 0,
        brightness: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.keyword = keyword
        self.width = width
        self.height = height
        self.fps = fps
        self.exposure = exposure
        self.auto_exposure = auto_exposure
        self.gain = gain
        self.brightness = brightness
        self._running = False
        self._lock = Lock()
        self._pending_controls = []

    def stop(self) -> None:
        self._running = False
        self.wait(1500)

    def set_exposure(self, exposure: int, auto_exposure: bool) -> None:
        with self._lock:
            self.exposure = exposure
            self.auto_exposure = auto_exposure
            self._pending_controls.append(("exposure", exposure, auto_exposure))

    def set_gain(self, gain: int) -> None:
        with self._lock:
            self.gain = gain
            self._pending_controls.append(("gain", gain))

    def set_brightness(self, brightness: int) -> None:
        with self._lock:
            self.brightness = brightness
            self._pending_controls.append(("brightness", brightness))

    def run(self) -> None:
        self._running = True
        cap = None
        try:
            import cv2
            from pygrabber.dshow_graph import FilterGraph

            camera_index, device_name = self._find_camera_by_name(FilterGraph, self.keyword)
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            self._apply_exposure(cv2, cap, self.exposure, self.auto_exposure)
            cap.set(cv2.CAP_PROP_GAIN, self.gain)
            cap.set(cv2.CAP_PROP_BRIGHTNESS, self.brightness)

            if not cap.isOpened():
                self.status_ready.emit("Camera failed to open")
                return

            self.status_ready.emit(f"Camera connected: {device_name}")
            self._emit_settings(cv2, cap, camera_index, device_name, "connected")
            frame_delay = 1.0 / max(1, self.fps)

            while self._running:
                self._apply_pending_controls(cv2, cap, camera_index, device_name)
                ret, frame = cap.read()
                if not ret:
                    self.status_ready.emit("Failed to grab frame")
                    time.sleep(0.05)
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb.shape
                bytes_per_line = channels * width
                image = QImage(
                    rgb.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,
                ).copy()
                self.frame_ready.emit(image)
                time.sleep(frame_delay)
        except Exception as exc:
            self.status_ready.emit(f"Camera error: {exc}")
        finally:
            if cap is not None:
                cap.release()
            self.settings_ready.emit(
                {
                    "connection_quality": "disconnected",
                    "device_name": "--",
                    "device_index": "--",
                }
            )
            self._running = False

    @staticmethod
    def _find_camera_by_name(filter_graph_class, keyword: str) -> tuple[int, str]:
        graph = filter_graph_class()
        devices = graph.get_input_devices()
        for index, name in enumerate(devices):
            if keyword.lower() in name.lower():
                return index, name
        raise RuntimeError(f"No camera found with name containing '{keyword}'")

    def _apply_pending_controls(self, cv2, cap, camera_index: int, device_name: str) -> None:
        with self._lock:
            controls = self._pending_controls
            self._pending_controls = []
        for control in controls:
            command = control[0]
            if command == "exposure":
                _, exposure, auto_exposure = control
                self._apply_exposure(cv2, cap, exposure, auto_exposure)
                self._emit_settings(cv2, cap, camera_index, device_name, "connected")
            elif command == "gain":
                _, gain = control
                cap.set(cv2.CAP_PROP_GAIN, gain)
                self._emit_settings(cv2, cap, camera_index, device_name, "connected")
            elif command == "brightness":
                _, brightness = control
                cap.set(cv2.CAP_PROP_BRIGHTNESS, brightness)
                self._emit_settings(cv2, cap, camera_index, device_name, "connected")

    @staticmethod
    def _apply_exposure(cv2, cap, exposure: int | None, auto_exposure: bool) -> None:
        # DirectShow commonly uses 0.75 for auto exposure and 0.25 for manual.
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75 if auto_exposure else 0.25)
        if exposure is not None and not auto_exposure:
            cap.set(cv2.CAP_PROP_EXPOSURE, exposure)

    def _emit_settings(self, cv2, cap, camera_index: int, device_name: str, quality: str) -> None:
        self.settings_ready.emit(
            {
                "device_name": device_name,
                "device_index": str(camera_index),
                "connection_quality": quality,
                "requested_resolution": f"{self.width} x {self.height}",
                "actual_resolution": (
                    f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))} x "
                    f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
                ),
                "requested_fps": str(self.fps),
                "actual_fps": f"{cap.get(cv2.CAP_PROP_FPS):.1f}",
                "auto_exposure": "auto" if self.auto_exposure else "manual",
                "exposure": f"{cap.get(cv2.CAP_PROP_EXPOSURE):.0f}",
                "gain": f"{cap.get(cv2.CAP_PROP_GAIN):.0f}",
                "brightness": f"{cap.get(cv2.CAP_PROP_BRIGHTNESS):.0f}",
            }
        )


class LiveCameraFeedWidget(QWidget):
    frame_ready = Signal(QImage)
    status_ready = Signal(str)
    settings_ready = Signal(dict)

    def __init__(self, keyword: str = "Arducam", parent=None):
        super().__init__(parent)
        self.keyword = keyword
        self.width = 1280
        self.height = 720
        self.fps = 30
        self.exposure = -6
        self.auto_exposure = True
        self.gain = 0
        self.brightness = 0
        self.latest_image = QImage()
        self.worker = None

        self.video_label = QLabel("Camera live feed")
        self.video_label.setObjectName("cameraFeedText")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setScaledContents(False)
        self.video_label.setMinimumSize(0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_label)
        self._create_worker()

    def start(self) -> None:
        if self.worker is None:
            self._create_worker()
        if not self.worker.isRunning():
            self.worker.start()

    def stop(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()

    def shutdown(self) -> None:
        self.stop()

    def reconnect(self) -> None:
        self.stop()
        self.latest_image = QImage()
        self.video_label.clear()
        self.video_label.setText("Camera live feed")
        self._create_worker()
        self.start()

    def set_format(self, width: int, height: int, fps: int) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.reconnect()

    def set_exposure(self, exposure: int, auto_exposure: bool) -> None:
        self.exposure = exposure
        self.auto_exposure = auto_exposure
        if self.worker is not None and self.worker.isRunning():
            self.worker.set_exposure(exposure, auto_exposure)

    def set_gain(self, gain: int) -> None:
        self.gain = gain
        if self.worker is not None and self.worker.isRunning():
            self.worker.set_gain(gain)

    def set_brightness(self, brightness: int) -> None:
        self.brightness = brightness
        if self.worker is not None and self.worker.isRunning():
            self.worker.set_brightness(brightness)

    def _create_worker(self) -> None:
        old_worker = self.worker
        self.worker = CameraWorker(
            keyword=self.keyword,
            width=self.width,
            height=self.height,
            fps=self.fps,
            exposure=self.exposure,
            auto_exposure=self.auto_exposure,
            gain=self.gain,
            brightness=self.brightness,
            parent=self,
        )
        self.worker.frame_ready.connect(self.update_frame)
        self.worker.frame_ready.connect(self.frame_ready)
        self.worker.status_ready.connect(self.set_status_text)
        self.worker.status_ready.connect(self.status_ready)
        self.worker.settings_ready.connect(self.settings_ready)
        if old_worker is not None:
            old_worker.deleteLater()

    @Slot(QImage)
    def update_frame(self, image: QImage) -> None:
        self.latest_image = image
        self._refresh_pixmap()

    @Slot(str)
    def set_status_text(self, status: str) -> None:
        if self.latest_image.isNull():
            self.video_label.setText(status)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_pixmap()

    def _refresh_pixmap(self) -> None:
        if self.latest_image.isNull():
            return
        pixmap = QPixmap.fromImage(self.latest_image)
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)
