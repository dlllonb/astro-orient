"""USB serial client for the Astro Orient STM32 environmental sensor."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Iterator

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:  # pragma: no cover - friendly command-line failure
    raise SystemExit("pyserial is required. Install it with: pip install pyserial") from exc


USB_VID = 0x0483
USB_PID = 0x5740


def available_ports() -> list[str]:
    """Return likely Astro Orient virtual COM ports."""
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
        raise RuntimeError(
            "Astro Orient USB serial port was not found. "
            f"Visible ports: {visible}. Pass --port COMx if needed."
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple matching devices were found ({', '.join(matches)}); use --port."
        )
    return matches[0]


class AstroOrientSensor:
    """Small reusable interface intended for GUI or command-line programs."""

    def __init__(self, port: str | None = None, timeout: float = 0.25) -> None:
        self.port = find_port(port)
        self.serial = serial.Serial(self.port, 115200, timeout=timeout)
        time.sleep(0.15)
        self.serial.reset_input_buffer()

    def close(self) -> None:
        if self.serial.is_open:
            self.serial.close()

    def __enter__(self) -> "AstroOrientSensor":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def send(self, command: str) -> None:
        """Send a newline-terminated firmware command."""
        self.serial.write((command.strip() + "\n").encode("ascii"))
        self.serial.flush()

    def read_message(self) -> dict[str, Any] | None:
        """Read one JSON message; return None when the timeout expires."""
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

    def messages(self) -> Iterator[dict[str, Any]]:
        """Yield messages continuously; suitable for a GUI worker thread."""
        while self.serial.is_open:
            message = self.read_message()
            if message is not None:
                yield message

    def set_streaming(self, enabled: bool) -> None:
        self.send("STREAM ON" if enabled else "STREAM OFF")

    def set_rate(self, interval_ms: int) -> None:
        if not 100 <= interval_ms <= 60_000:
            raise ValueError("interval_ms must be between 100 and 60000")
        self.send(f"RATE {interval_ms}")

    def set_led(self, led: int, red: int, green: int, blue: int) -> None:
        """Set D2 or D3 to a host-selected RGB color."""
        if led not in (2, 3):
            raise ValueError("Only D2 and D3 are controlled by the laptop")
        if not all(0 <= value <= 255 for value in (red, green, blue)):
            raise ValueError("RGB values must be between 0 and 255")
        self.send(f"LED D{led} RGB {red} {green} {blue}")

    def set_gps_status(self, connected: bool, locked: bool = False) -> None:
        """D2: red if disconnected, yellow if searching, green if locked."""
        if not connected:
            self.send("GPS OFF")
        elif locked:
            self.send("GPS LOCKED")
        else:
            self.send("GPS SEARCHING")

    def set_imu_status(self, connected: bool, ready: bool = False) -> None:
        """D3: red if disconnected, yellow if connected, green if ready."""
        if not connected:
            self.send("IMU OFF")
        elif ready:
            self.send("IMU READY")
        else:
            self.send("IMU CONNECTED")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read live BME280 data from the Astro Orient PCB."
    )
    parser.add_argument("--port", help="COM port, for example COM6 (auto-detected by default)")
    parser.add_argument(
        "--rate", type=int, default=500, help="stream interval in milliseconds (default: 500)"
    )
    args = parser.parse_args()

    try:
        with AstroOrientSensor(args.port) as sensor:
            print(f"Connected to {sensor.port}. Press Ctrl+C to stop.")
            sensor.set_rate(args.rate)
            sensor.set_streaming(True)
            sensor.send("PING")
            for message in sensor.messages():
                print(json.dumps(message, separators=(",", ":")), flush=True)
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError, ValueError, serial.SerialException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
