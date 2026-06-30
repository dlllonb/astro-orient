import serial
import pynmea2
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
# ser = serial.Serial("COM4", baudrate=9600, timeout=3000)
#
# datalist = []
# for i in range(30):
#     data = ser.readline()
#     if len(data) > 0:
#         datalist.append(data.decode("utf-8"))
# ser.close()
#
# logFile = open("GPS_test.txt","w")
# for data in datalist:
#     # Convert tuple to string, strips parenthesis, and adds new line before writing to file.
#     logFile.write(str(data).strip('\n'))
#
# logFile.close()

# file = open('GPS_test.txt', encoding='utf-8')
#
# for line in file.readlines():
#     try:
#         msg = pynmea2.parse(line)
#         #print(type(msg))
#         if isinstance(msg, pynmea2.types.talker.GGA):
#             print(msg.timestamp)
#             print(type(msg.timestamp))
#             print(msg.lat, msg.lat_dir)
#             print(type(msg.lat))
#             print(msg.lon, msg.lon_dir)
#             print(type(msg.lon_dir))
#             print()
#
#         #print(repr(msg))
#
#     except pynmea2.ParseError as e:
#         print('Parse error: {}'.format(e))
#         continue

@dataclass
class GPSData:
    parse_errors: int = 0

    #from GGA
    timestamp: datetime | None = None
    latitude: str | None = None
    latitude_dir: str | None = None
    longitude: str | None = None
    longitude_dir: str | None = None
    altitude: float | None = None
    alt_units: str | None = None
    age_of_gps_data: int | None = None
    num_sat_used: int | None = None
    geo_separation: int | None = None
    geo_separation_unit: str | None = None
    gps_quality: str | None = None

    #vtg
    magnetic_track: Decimal | None = None
    magnetic_track_sym: str | None = None
    speed_over_ground_kmph: float | None = None

    #rmc
    datestamp: str | None = None
    status: str | None = None
    mode_indicator: str | None = None

    #gsa
    mode: str | None = None
    fix_type: str | None = None
    pdop: str | None = None
    hdop: str | None = None
    vdop: str | None = None

    #gsv
    satellites_in_view: int | None = None

    last_sentence_type: str | None = None
    last_update: datetime | None = None
    raw_last_line: str | None = None

    @property
    def has_fix(self) -> bool:
        return (
                self.latitude is not None
                and self.longitude is not None
                and self.gps_quality not in (None, 0)
        )


class GPSReader:
    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.data = GPSData()

    def connect(self):
        self.ser = serial.Serial(
            self.port,
            baudrate=self.baudrate,
            timeout=self.timeout
        )

    def close(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def read_line(self):
        if self.ser is None:
            raise RuntimeError("GPS serial port is not connected.")

        raw = self.ser.readline()

        if not raw:
            return None

        return raw.decode("ascii", errors="replace").strip()

    def update_once(self) -> GPSData:
        line = self.read_line()

        if not line:
            return self.data

        self.data.raw_last_line = line

        try:
            msg = pynmea2.parse(line)
        except pynmea2.ParseError:
            self.data.parse_errors += 1
            return self.data

        self._update_from_message(msg)
        return self.data

    def _safe_float(self, value):
        try:
            if value in ("", None):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_int(self, value):
        try:
            if value in ("", None):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _update_from_message(self, msg):
        self.data.last_sentence_type = msg.sentence_type
        self.data.last_update = datetime.now(timezone.utc)

        if isinstance(msg, pynmea2.types.talker.GGA):
            self.data.timestamp = msg.timestamp
            self.data.latitude = self._safe_float(msg.latitude)
            self.data.latitude_dir = msg.lat_dir
            self.data.longitude = self._safe_float(msg.longitude)
            self.data.longitude_dir = msg.lon_dir
            self.data.altitude = self._safe_float(msg.altitude)
            self.data.alt_units = msg.altitude_units
            self.data.age_of_gps_data = msg.age_gps_data
            self.data.gps_quality = self._safe_int(msg.gps_qual)
            self.data.num_sat_used = self._safe_int(msg.num_sats)
            self.data.geo_separation = self._safe_float(msg.geo_sep)
            self.data.geo_separation_unit = msg.geo_sep_units



        elif isinstance(msg, pynmea2.types.talker.RMC):
            self.data.datestamp = msg.datestamp
            self.data.status= msg.status
            self.data.mode_indicator = msg.mode_indicator



        elif isinstance(msg, pynmea2.types.talker.GSA):
            self.data.mode = self._safe_int(msg.mode)
            self.data.fix_type = self._safe_int(msg.mode_fix_type)
            self.data.pdop = self._safe_float(msg.pdop)
            self.data.hdop = self._safe_float(msg.hdop)
            self.data.vdop = self._safe_float(msg.vdop)

        elif isinstance(msg, pynmea2.types.talker.VTG):
            self.data.magnetic_track = self._safe_float(msg.mag_track)
            self.data.magnetic_track_sym = msg.mag_track_sym
            self.data.speed_over_ground_kmph = self._safe_float(msg.spd_over_grnd_kmph)

        elif isinstance(msg, pynmea2.types.talker.GSV):
            self.data.satellites_in_view= self._safe_int(msg.num_sv_in_view)



