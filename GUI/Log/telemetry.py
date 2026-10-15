from datetime import datetime, timedelta, timezone
import time

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QImageWriter

from IMU.imu_orientation_component import matrix_to_pitch_roll_yaw
from .recorder import CameraFrame, SessionRecorder, TelemetryStore, iso_utc


class TelemetryBridge(QObject):
    """Receive worker signals directly; only the locked store is mutated here."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = TelemetryStore()
        self._pcb_errors = 0

    @Slot(object)
    def gps_sample(self, packet):
        data = packet["data"]
        values = {}
        sentence = data.last_sentence_type
        has_fix = None
        if sentence == "GGA":
            fixed = bool(data.gps_quality and data.gps_quality > 0)
            has_fix = fixed
            values.update(
                gps_latitude=data.latitude if fixed else None,
                gps_longitude=data.longitude if fixed else None,
                gps_altitude=data.altitude if fixed else None,
                gps_fix=data.gps_quality,
                gps_satellites=data.num_sat_used,
                gps_hdop=data.hdop,
                gps_geoid=data.geo_separation,
            )
        elif sentence == "GSA":
            has_fix = data.fix_type is not None and data.fix_type > 1
            values.update(gps_hdop=data.hdop, gps_pdop=data.pdop, gps_vdop=data.vdop,
                          gps_mode=(data.fix_type, data.mode))
        elif sentence == "VTG":
            values.update(gps_speed=data.speed_over_ground_kmph, gps_course=data.course_over_ground)
        elif sentence == "RMC":
            has_fix = data.status == "A"
            values.update(gps_course=data.course_over_ground)
        elif sentence == "GSV":
            values["gps_satellites_view"] = data.satellites_in_view
        # RMC supplies date and time together, including across UTC midnight.
        if sentence == "RMC":
            values["gps_utc"] = (
                iso_utc(datetime.combine(data.datestamp, data.timestamp, tzinfo=timezone.utc))
                if data.datestamp is not None and data.timestamp is not None else None
            )
        if values:
            self.store.update("gps", values, monotonic=packet["monotonic"], utc=packet["utc"], has_fix=has_fix)

    @Slot(str, int, str)
    def gps_connection(self, port, baudrate, quality):
        self.store.set_connection("gps", quality == "connected", quality)

    @Slot(object)
    def imu_sample(self, sample):
        pitch, roll, yaw = matrix_to_pitch_roll_yaw(sample.matrix)
        received = datetime.now(timezone.utc) - timedelta(seconds=max(0, time.monotonic() - sample.timestamp))
        self.store.update("imu", {
            "imu_roll": roll, "imu_pitch": pitch, "imu_yaw": yaw,
            "imu_quaternion": tuple(sample.quaternion),
            "imu_acceleration": sample.accelerometer,
            "imu_angular_velocity": sample.gyro_rate,
            "imu_magnetic_field": sample.compass,
            "imu_temperature": sample.temperature_c,
            "imu_confidence": sample.confidence,
            "imu_enabled": (sample.gyro_enabled, sample.accelerometer_enabled, sample.compass_enabled),
        }, monotonic=sample.timestamp, utc=received)

    @Slot(str)
    def imu_status(self, status):
        if status.startswith("IMU control error:"):
            return
        connected = status.lower().startswith(("connected", "live"))
        self.store.set_connection("imu", connected, status)

    @Slot(object)
    def pcb_sample(self, packet):
        message = packet["message"]
        if message.get("type") == "client_error":
            self._pcb_errors += 1
            return
        if message.get("type") != "environment":
            return
        bme_ok = message.get("bme280_ok")
        photo_ok = message.get("photoresistors_ok")
        mapping = {
            "temperature": "temperature_c", "pressure": "pressure_hpa", "humidity": "humidity_percent",
            "ambient_light": "ambient_light_percent", "raw_light_avg": "ambient_light_raw_avg",
            "raw_light_1_avg": "light_1_raw_avg", "raw_light_2_avg": "light_2_raw_avg", "pcb_uptime": "timestamp_ms",
        }
        values = {key: message[wire_key] for key, wire_key in mapping.items() if wire_key in message}
        if bme_ok is False:
            values.update(temperature=None, pressure=None, humidity=None)
        if photo_ok is False:
            values.update(ambient_light=None, raw_light_avg=None, raw_light_1_avg=None, raw_light_2_avg=None)
        values["pcb_sensor_status"] = (bme_ok, photo_ok)
        values["pcb_parse_errors"] = self._pcb_errors
        self.store.update("pcb", values, monotonic=packet["monotonic"], utc=packet["utc"])

    @Slot(str, int, str)
    def pcb_connection(self, port, baudrate, quality):
        self.store.set_connection("pcb", quality == "connected", quality)

    @Slot(object)
    def camera_sample(self, packet):
        settings = packet["settings"]
        frame = CameraFrame(packet["identity"], packet["number"], packet["image"],
                            packet["monotonic"], packet["utc"], dict(settings))
        self.store.update("camera", {
            "camera_frame": (frame.number, iso_utc(frame.utc), None),
            "camera_exposure": settings.get("exposure"),
            "camera_gain": settings.get("gain"),
            "camera_brightness": settings.get("brightness"),
            "camera_auto_exposure": settings.get("auto_exposure"),
            "camera_fps": settings.get("measured_fps"),
            "camera_format": (frame.image.width(), frame.image.height(), settings.get("requested_fps"), settings.get("driver_fps")),
        }, monotonic=frame.monotonic, utc=frame.utc, frame=frame)

    @Slot(dict)
    def camera_settings(self, settings):
        quality = settings.get("connection_quality")
        if quality is not None:
            self.store.set_connection("camera", quality == "connected", quality)


def save_camera_image(image, path):
    writer = QImageWriter(str(path), b"png")
    # Lower PNG compression reduces encoding time without changing pixel values.
    writer.setCompression(20)
    if not writer.write(image):
        raise OSError(f"Could not save camera image: {writer.errorString()}")
    return True


class LogController(QObject):
    progress = Signal(dict)
    finished = Signal()
    _event = Signal(dict)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.worker = None
        self._stopping = False
        self._event.connect(self._handle_event)

    @property
    def running(self):
        return self.worker is not None

    def start(self, destination, keys, interval):
        if self.running:
            raise RuntimeError("Recording is already active")
        worker = SessionRecorder(self.store, destination, keys, interval,
                                 save_image=save_camera_image,
                                 notify=self._event.emit)
        self.worker = worker
        self._stopping = False
        self.progress.emit({"state": "starting", "rows": 0, "images": 0, "missed": 0, "elapsed": 0, "path": ""})
        try:
            worker.start()
        except Exception:
            self.worker = None
            self.progress.emit({"state": "finished"})
            raise

    def stop(self):
        if self.worker:
            self._stopping = True
            self.progress.emit({"state": "stopping"})
            self.worker.stop()

    @Slot(dict)
    def _handle_event(self, event):
        if event["state"] == "finished":
            if self.worker:
                self.worker.join()
            self.worker = None
            self.progress.emit(event)
            self.finished.emit()
        else:
            if self._stopping:
                event = dict(event, state="stopping")
            self.progress.emit(event)
