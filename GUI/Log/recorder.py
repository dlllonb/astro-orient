"""Thread-safe latest-value recording. No GUI or hardware dependencies."""

import csv
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any

from .fields import FIELD_BY_KEY, selected_fields


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate_interval(interval):
    interval = float(interval)
    if not math.isfinite(interval) or interval < 1 or not interval.is_integer():
        raise ValueError("Sample interval must be at least 1 s, in whole-second steps")
    return interval


@dataclass(frozen=True)
class Reading:
    values: tuple
    monotonic: float
    utc: datetime


@dataclass
class Source:
    connected: bool = False
    status: str = "not connected"
    sequence: int = 0
    monotonic: float | None = None
    utc: datetime | None = None
    has_fix: bool | None = None


@dataclass(frozen=True)
class CameraFrame:
    identity: str
    number: int
    image: Any
    monotonic: float
    utc: datetime
    settings: dict = field(default_factory=dict)


class TelemetryStore:
    def __init__(self):
        self._lock = Lock()
        self._readings = {}
        self._sources = {name: Source() for name in ("gps", "imu", "pcb", "camera")}
        self._frame = None

    def set_connection(self, source, connected, status):
        with self._lock:
            state = self._sources[source]
            if connected and not state.connected:
                self._readings = {
                    key: value for key, value in self._readings.items()
                    if FIELD_BY_KEY[key].source != source
                }
                state.monotonic = state.utc = None
                state.has_fix = None
                if source == "camera":
                    self._frame = None
            state.connected = bool(connected)
            state.status = str(status)

    def update(self, source, values, *, monotonic=None, utc=None, frame=None, has_fix=None):
        stamp = time.monotonic() if monotonic is None else monotonic
        received = utc_now() if utc is None else utc
        with self._lock:
            state = self._sources[source]
            state.connected = True
            state.status = "connected"
            state.sequence += 1
            state.monotonic, state.utc = stamp, received
            if has_fix is not None:
                state.has_fix = bool(has_fix)
            for key, value in values.items():
                definition = FIELD_BY_KEY[key]
                if definition.source != source:
                    raise ValueError(f"{key} does not belong to {source}")
                components = value if isinstance(value, tuple) else (value,)
                if value is None:
                    components = (None,) * len(definition.columns)
                if len(components) != len(definition.columns):
                    raise ValueError(f"Wrong number of values for {key}")
                self._readings[key] = Reading(components, stamp, received)
            if frame is not None:
                self._frame = frame

    def snapshot(self):
        with self._lock:
            return (
                dict(self._readings),
                {key: Source(**vars(value)) for key, value in self._sources.items()},
                self._frame,
                time.monotonic(),
                utc_now(),
            )


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


class SessionRecorder(Thread):
    def __init__(self, store, destination, keys, interval, *, save_image=None, notify=None):
        super().__init__(name="Astro-orient recorder", daemon=False)
        self.store = store
        self.destination = Path(destination).expanduser()
        self.fields = selected_fields(keys)
        if not self.fields:
            raise ValueError("Select at least one data field")
        self.interval = validate_interval(interval)
        self.sources = sorted({item.source for item in self.fields})
        self.camera_selected = "camera" in self.sources
        self.save_image = save_image
        if self.camera_selected and save_image is None:
            raise ValueError("An image writer is required for camera recording")
        self.notify = notify or (lambda event: None)
        self.stop_event = Event()
        self.session_path = None
        self.error = ""
        self.rows = self.images = self.missed = 0
        self.repeated_images = self.missing_images = 0
        self._previous_sequences = {}
        self._last_frame_id = self._last_image_path = None
        self._last_settings = None
        self._last_measured_fps = None
        self._first_frame_utc = self._last_frame_utc = None

    def stop(self):
        self.stop_event.set()

    def columns(self):
        columns = ["sample_index", "scheduled_utc", "recorded_utc", "elapsed_s", "lateness_ms", "missed_intervals"]
        for source in self.sources:
            columns += [f"{source}_connected", f"{source}_status", f"{source}_received_utc", f"{source}_age_s", f"{source}_new_sample"]
        for item in self.fields:
            columns.extend(item.columns)
            columns.append(f"{item.key}_age_s")
        if self.camera_selected:
            columns += ["camera_frame_id", "camera_image_status"]
        return columns

    def _write_image(self, frame, connected):
        if frame is None or not connected:
            self.missing_images += 1
            return "", "disconnected" if not connected else "no_frame"
        if frame.identity == self._last_frame_id:
            self.repeated_images += 1
            return self._last_image_path, "reused"
        # SSff is seconds plus hundredths; a suffix prevents any filename collision.
        stem = frame.utc.strftime("%H_%M_%S") + f"{frame.utc.microsecond // 10000:02d}"
        target = self.session_path / "Camera" / f"{stem}.png"
        counter = 2
        while target.exists():
            target = target.with_name(f"{stem}_{counter}.png")
            counter += 1
        if not self.save_image(frame.image, target):
            raise OSError(f"Could not save camera image: {target}")
        self.images += 1
        self._last_frame_id = frame.identity
        self._last_image_path = target.relative_to(self.session_path).as_posix()
        self._first_frame_utc = self._first_frame_utc or frame.utc
        self._last_frame_utc = frame.utc
        return self._last_image_path, "saved"

    def _make_row(self, snapshot, index, missed):
        readings, sources, frame, sampled_mono, sampled_utc = snapshot
        elapsed = sampled_mono - self.started_mono
        row = {
            "sample_index": index,
            "scheduled_utc": iso_utc(self.started_utc + timedelta(seconds=index * self.interval)),
            "recorded_utc": iso_utc(sampled_utc),
            "elapsed_s": round(elapsed, 6),
            "lateness_ms": round(max(0, elapsed - index * self.interval) * 1000, 3),
            "missed_intervals": missed,
        }
        for source in self.sources:
            state = sources[source]
            row.update({
                f"{source}_connected": int(state.connected),
                f"{source}_status": "no fix" if source == "gps" and state.connected and state.has_fix is not True else state.status,
                f"{source}_received_utc": iso_utc(state.utc) if state.utc else "",
                f"{source}_age_s": round(max(0, sampled_mono - state.monotonic), 6) if state.monotonic is not None else "",
                f"{source}_new_sample": int(state.sequence != self._previous_sequences.get(source, 0)),
            })
            self._previous_sequences[source] = state.sequence
        for item in self.fields:
            source = sources[item.source]
            if not source.connected:
                continue
            reading = readings.get(item.key)
            no_fix = item.source == "gps" and source.has_fix is not True
            fix_dependent = item.key in {
                "gps_latitude", "gps_longitude", "gps_altitude", "gps_speed", "gps_course", "gps_geoid",
            }
            values = reading.values if reading else (None,) * len(item.columns)
            if no_fix:
                values = tuple("N/A" if fix_dependent or csv_value(value) == "" else value for value in values)
            row.update(zip(item.columns, map(csv_value, values)))
            if reading:
                row[f"{item.key}_age_s"] = round(max(0, sampled_mono - reading.monotonic), 6)
        if self.camera_selected:
            path, status = self._write_image(frame, sources["camera"].connected)
            row["camera_image_path"] = path
            row["camera_image_status"] = status
            row["camera_frame_id"] = frame.identity if frame and sources["camera"].connected else ""
        return row

    def _camera_info(self, handle, frame):
        if frame is None:
            return
        self._last_measured_fps = frame.settings.get("measured_fps")
        settings = {key: value for key, value in frame.settings.items() if key != "measured_fps"}
        if settings != self._last_settings:
            handle.write(f"\nSettings at frame UTC {iso_utc(frame.utc)}:\n")
            for key, value in sorted(settings.items()):
                handle.write(f"  {key}: {value}\n")
            self._last_settings = settings
            handle.flush()

    def run(self):
        csv_handle = info = camera_info = None
        self.started_utc, self.started_mono = utc_now(), time.monotonic()
        try:
            if not self.destination.is_dir():
                raise ValueError("Choose an existing destination folder")
            path = self.destination / self.started_utc.strftime("%Y%m%d_%H_%M_%S")
            path.mkdir(exist_ok=False)
            self.session_path = path
            info = (path / "session_info.txt").open("x", encoding="utf-8")
            info.write(
                f"Start UTC: {iso_utc(self.started_utc)}\nSample interval seconds: {self.interval}\n"
                "Policy: latest available reading at each fixed monotonic deadline; first row after one interval.\n"
                "Host UTC timestamps are receipt times, not hardware exposure/measurement times.\n"
                "Each selected field has an age in seconds; GPS fields arrive in separate NMEA sentences.\n"
                "No interpolation. Disconnected sensor measurements are blank.\n"
                "Connected GPS without a confirmed fix uses N/A for fix-dependent or unavailable fields; valid diagnostics remain.\n"
                "Connected indicates transport state, not guaranteed fresh data; inspect ages and GPS fix quality.\n"
                "Slow writes skip missed deadlines, counted in missed_intervals; no backfilled samples.\n"
                "IMU Euler angles and quaternion use sensor orientation, before local display tare/inversion.\n"
                "Acceleration includes gravity (g); gyro is rad/s; magnetic field is gauss.\n"
                "Board uptime is firmware timestamp_ms (may reset/wrap). Invalid JSON is not packet loss.\n"
                f"Selected fields: {', '.join(item.key for item in self.fields)}\n"
            )
            info.flush()
            if self.camera_selected:
                (path / "Camera").mkdir()
                camera_info = (path / "Camera" / "capture_info.txt").open("x", encoding="utf-8")
                camera_info.write(
                    f"Start UTC: {iso_utc(self.started_utc)}\nSample interval seconds: {self.interval}\n"
                    "Mode: save the latest full-resolution frame once per logging interval, as PNG.\n"
                    "PNG compression setting: 20/100 (fast lossless encoding; pixels unchanged).\n"
                    "Repeated frames reuse their existing image path; no new exposure is triggered.\n"
                    "Names: HH_MM_SSff.png in UTC; ff is hundredths; collisions add _2, _3, etc.\n"
                    "Frame timestamp: host UTC immediately after capture read, not hardware exposure time.\n"
                    "Exposure/gain/brightness are driver-reported values, not calibrated physical units.\n"
                    "driver_fps is a negotiated setting; measured_fps comes from observed frame arrivals.\n"
                )
                self._camera_info(camera_info, self.store.snapshot()[2])
                camera_info.flush()
            csv_handle = (path / "data.csv").open("x", newline="", encoding="utf-8")
            writer = csv.DictWriter(csv_handle, fieldnames=self.columns())
            writer.writeheader()
            csv_handle.flush()
            self.notify({"state": "recording", "path": str(path)})
            next_index = 1
            while not self.stop_event.wait(max(0, self.started_mono + next_index * self.interval - time.monotonic())):
                snapshot = self.store.snapshot()
                index = max(next_index, int((snapshot[3] - self.started_mono) / self.interval))
                missed = index - next_index
                row = self._make_row(snapshot, index, missed)
                writer.writerow(row)
                csv_handle.flush()
                if camera_info:
                    self._camera_info(camera_info, snapshot[2])
                self.rows += 1
                self.missed += missed
                self.notify({"state": "recording", "path": str(path), "rows": self.rows, "images": self.images, "missed": self.missed, "elapsed": snapshot[3] - self.started_mono})
                next_index = index + 1
        except Exception as exc:
            self.error = str(exc)
        finally:
            ended = utc_now()
            duration = time.monotonic() - self.started_mono
            summary = (
                f"\nEnd UTC: {iso_utc(ended)}\nDuration seconds: {duration:.6f}\n"
                f"CSV rows: {self.rows}\nSaved images: {self.images}\nMissed intervals: {self.missed}\n"
                f"Result: {self.error or 'stopped normally'}\n"
            )
            for handle in (info, camera_info):
                if handle:
                    try:
                        handle.write(summary)
                        if handle is camera_info:
                            handle.write(f"Last measured FPS: {self._last_measured_fps if self._last_measured_fps is not None else ''}\n")
                            handle.write(f"Reused-frame rows: {self.repeated_images}\nMissing-frame rows: {self.missing_images}\n")
                            handle.write(f"First saved frame UTC: {iso_utc(self._first_frame_utc) if self._first_frame_utc else ''}\n")
                            handle.write(f"Last saved frame UTC: {iso_utc(self._last_frame_utc) if self._last_frame_utc else ''}\n")
                            handle.write(f"Saved-frame span seconds: {(self._last_frame_utc - self._first_frame_utc).total_seconds() if self._first_frame_utc else 0}\n")
                        handle.close()
                    except Exception as exc:
                        self.error = self.error or str(exc)
            if csv_handle:
                try:
                    csv_handle.close()
                except Exception as exc:
                    self.error = self.error or str(exc)
            self.notify({"state": "finished", "path": str(self.session_path or ""), "error": self.error, "rows": self.rows, "images": self.images, "elapsed": duration, "missed": self.missed})
