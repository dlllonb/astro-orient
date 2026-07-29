import json
import time
from threading import Lock
from typing import Any

import serial
from serial.tools import list_ports
from PySide6.QtCore import QThread, Signal


USB_VID = 0x0483
USB_PID = 0x5740


def available_ports() -> list[str]:
    matches: list[str] = []
    for port in list_ports.comports():
        product = (port.product or "").lower()
        description = (port.description or "").lower()
        if (
            (port.vid == USB_VID and port.pid == USB_PID)
            or "astro orient" in product
            or "astro orient" in description
        ):
            matches.append(port.device)
    return matches


def find_port(requested: str | None = None) -> str:
    if requested:
        return requested
    matches = available_ports()
    if not matches:
        visible = ", ".join(port.device for port in list_ports.comports()) or "none"
        raise RuntimeError(f"Astro Orient PCB was not found. Visible ports: {visible}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple PCB ports found: {', '.join(matches)}")
    return matches[0]


class AstroOrientSensor:
    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        timeout: float = 0.25,
    ) -> None:
        self.port = find_port(port)
        self.baudrate = baudrate
        self.serial = serial.Serial(self.port, baudrate, timeout=timeout)
        time.sleep(0.15)
        self.serial.reset_input_buffer()

    def close(self) -> None:
        if self.serial.is_open:
            self.serial.close()

    def send(self, command: str) -> None:
        self.serial.write((command.strip() + "\n").encode("ascii"))
        self.serial.flush()

    def read_message(self) -> dict[str, Any] | None:
        raw = self.serial.readline()
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return {
                "type": "client_error",
                "message": "invalid_json",
                "raw": raw.decode("utf-8", errors="replace").rstrip(),
                "detail": str(exc),
            }

    def set_streaming(self, enabled: bool) -> None:
        self.send("STREAM ON" if enabled else "STREAM OFF")

    def set_rate(self, interval_ms: int) -> None:
        if not 100 <= interval_ms <= 60000:
            raise ValueError("interval_ms must be between 100 and 60000")
        self.send(f"RATE {interval_ms}")

    def set_gps_status(self, connected: bool, locked: bool = False) -> None:
        if not connected:
            self.send("GPS OFF")
        elif locked:
            self.send("GPS LOCKED")
        else:
            self.send("GPS SEARCHING")

    def set_imu_status(self, connected: bool) -> None:
        self.send("IMU READY" if connected else "IMU OFF")


class PCBWorker(QThread):
    data_ready = Signal(dict)
    status_ready = Signal(str)
    connection_ready = Signal(str, int, str)

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        interval_ms: int = 500,
        parent=None,
    ):
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self.interval_ms = interval_ms
        self._running = False
        self._sensor = None
        self._lock = Lock()
        self._pending_commands: list[tuple[str, tuple]] = []

    def stop(self) -> None:
        self._running = False
        self.wait(1500)

    def set_gps_led(self, connected: bool, locked: bool = False) -> None:
        with self._lock:
            self._pending_commands.append(("gps", (connected, locked)))

    def set_imu_led(self, connected: bool) -> None:
        with self._lock:
            self._pending_commands.append(("imu", (connected,)))

    def run(self) -> None:
        self._running = True
        try:
            self._sensor = AstroOrientSensor(self.port, baudrate=self.baudrate)
            self.status_ready.emit(f"Connected on {self._sensor.port}")
            self.connection_ready.emit(self._sensor.port, self.baudrate, "connected")
            self._sensor.set_rate(self.interval_ms)
            self._sensor.set_streaming(True)
            self._sensor.send("PING")

            while self._running:
                self._apply_pending_commands()
                message = self._sensor.read_message()
                if message is not None:
                    self.data_ready.emit(self._to_display_dict(message))
        except Exception as exc:
            self.status_ready.emit(f"PCB error: {exc}")
            self.connection_ready.emit("--", self.baudrate, "error")
        finally:
            if self._sensor is not None:
                try:
                    self._sensor.set_streaming(False)
                except Exception:
                    pass
                self._sensor.close()
            self.connection_ready.emit("--", self.baudrate, "disconnected")
            self._running = False

    def _apply_pending_commands(self) -> None:
        with self._lock:
            commands = self._pending_commands
            self._pending_commands = []
        for command, args in commands:
            try:
                if command == "gps":
                    self._sensor.set_gps_status(*args)
                elif command == "imu":
                    self._sensor.set_imu_status(*args)
            except Exception as exc:
                self.status_ready.emit(f"PCB LED error: {exc}")

    def _to_display_dict(self, message: dict[str, Any]) -> dict[str, str]:
        ambient_light = self._first(
            message,
            "ambient_light",
            "ambient_light_percent",
            "ambient_percent",
            "light_percent",
            "light_percentage",
            "light_pct",
            "light",
            "brightness_percent",
        )
        raw_light_1 = self._first(
            message,
            "raw_light_1_avg",
            "raw_light1_avg",
            "light1_raw_avg",
            "raw_resistor_1_avg",
            "raw_resistor1_avg",
            "resistor_1_raw_avg",
            "photoresistor1_avg",
            "photoresistor_1_avg",
            "photoresistor1_raw_avg",
            "photoresistor_1_raw_avg",
            "ldr1_avg",
            "ldr_1_avg",
            "raw1",
            "raw_1",
            "adc1",
            "adc_1",
            "photo1",
            "photo_1",
            "resistor1_avg",
            "resistor_1_avg",
            "r1_avg",
            "light1",
            "light_1",
        )
        raw_light_2 = self._first(
            message,
            "raw_light_2_avg",
            "raw_light2_avg",
            "light2_raw_avg",
            "raw_resistor_2_avg",
            "raw_resistor2_avg",
            "resistor_2_raw_avg",
            "photoresistor2_avg",
            "photoresistor_2_avg",
            "photoresistor2_raw_avg",
            "photoresistor_2_raw_avg",
            "ldr2_avg",
            "ldr_2_avg",
            "raw2",
            "raw_2",
            "adc2",
            "adc_2",
            "photo2",
            "photo_2",
            "resistor2_avg",
            "resistor_2_avg",
            "r2_avg",
            "light2",
            "light_2",
        )
        raw_light_avg = self._first(
            message,
            "raw_light_avg",
            "raw_light_average",
            "light_raw_avg",
            "raw_resistor_avg",
            "raw_resistor_average",
            "resistor_raw_avg",
            "resistor_raw_average",
            "photoresistor_avg",
            "photoresistors_avg",
            "photoresistor_raw_avg",
            "photoresistors_raw_avg",
            "ldr_avg",
            "ldr_raw_avg",
            "resistor_avg",
            "raw_avg",
        )
        resistor_pair = self._first(message, "photoresistors", "resistors", "ldr", "raw_light")
        if isinstance(resistor_pair, (list, tuple)) and len(resistor_pair) >= 2:
            raw_light_1 = raw_light_1 if raw_light_1 is not None else resistor_pair[0]
            raw_light_2 = raw_light_2 if raw_light_2 is not None else resistor_pair[1]
        if raw_light_avg is None:
            raw_light_avg = self._average(raw_light_1, raw_light_2)
        display = {
            "message_type": self._format_value(message.get("type")),
        }
        self._add_number(
            display,
            "temperature",
            self._first(
                message,
                "temperature",
                "temperature_c",
                "temp",
                "temp_c",
                "bme_temp",
                "bme280_temperature",
            ),
            2,
        )
        self._add_number(
            display,
            "pressure",
            self._first(
                message,
                "pressure",
                "pressure_hpa",
                "press",
                "bme_pressure",
                "bme280_pressure",
            ),
            2,
        )
        self._add_number(
            display,
            "humidity",
            self._first(
                message,
                "humidity",
                "humidity_percent",
                "rh",
                "bme_humidity",
                "bme280_humidity",
            ),
            2,
        )
        self._add_number(display, "ambient_light", ambient_light, 2)
        self._add_number(display, "raw_light_avg", raw_light_avg, 2)
        self._add_number(display, "raw_light_1_avg", raw_light_1, 2)
        self._add_number(display, "raw_light_2_avg", raw_light_2, 2)
        return display

    @staticmethod
    def _first(message: dict[str, Any], *keys: str):
        flattened = PCBWorker._flatten(message)
        for key in keys:
            normalized_key = PCBWorker._normalize_key(key)
            if normalized_key in flattened:
                return flattened[normalized_key]
        return None

    @staticmethod
    def _flatten(message: dict[str, Any]) -> dict[str, Any]:
        flattened: dict[str, Any] = {}

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for item_key, item_value in value.items():
                    normalized_key = PCBWorker._normalize_key(item_key)
                    flattened[normalized_key] = item_value
                    visit(item_value)

        visit(message)
        return flattened

    @staticmethod
    def _normalize_key(key: Any) -> str:
        text = str(key).strip()
        normalized = []
        previous_was_separator = False
        for char in text:
            if char.isalnum():
                if char.isupper() and normalized and not previous_was_separator:
                    normalized.append("_")
                normalized.append(char.lower())
                previous_was_separator = False
            else:
                if normalized and not previous_was_separator:
                    normalized.append("_")
                previous_was_separator = True
        return "".join(normalized).strip("_")

    @staticmethod
    def _format_value(value) -> str:
        return "--" if value is None else str(value)

    @staticmethod
    def _format_number(value, decimals: int) -> str:
        if value is None:
            return "--"
        try:
            return f"{float(value):.{decimals}f}"
        except (TypeError, ValueError):
            return str(value)

    @classmethod
    def _add_number(cls, display: dict[str, str], key: str, value, decimals: int) -> None:
        if value is not None:
            display[key] = cls._format_number(value, decimals)

    @staticmethod
    def _average(first, second):
        try:
            return (float(first) + float(second)) / 2.0
        except (TypeError, ValueError):
            return None
