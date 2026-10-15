from dataclasses import dataclass


@dataclass(frozen=True)
class Field:
    key: str
    group: str
    source: str
    label: str
    columns: tuple[str, ...]
    default: bool = True
    unavailable: str = ""


FIELDS = (
    Field("imu_roll", "IMU", "imu", "Roll (deg)", ("imu_roll_deg",)),
    Field("imu_pitch", "IMU", "imu", "Pitch (deg)", ("imu_pitch_deg",)),
    Field("imu_yaw", "IMU", "imu", "Yaw (deg)", ("imu_yaw_deg",)),
    Field("imu_quaternion", "IMU", "imu", "Quaternion W, X, Y, Z", tuple(f"imu_quaternion_{a}" for a in "wxyz"), False),
    Field("imu_acceleration", "IMU", "imu", "Acceleration X, Y, Z (g)", tuple(f"imu_acceleration_{a}_g" for a in "xyz"), False),
    Field("imu_angular_velocity", "IMU", "imu", "Angular velocity X, Y, Z (rad/s)", tuple(f"imu_angular_velocity_{a}_rad_s" for a in "xyz"), False),
    Field("imu_magnetic_field", "IMU", "imu", "Magnetic field X, Y, Z (gauss)", tuple(f"imu_magnetic_field_{a}_gauss" for a in "xyz"), False),
    Field("imu_temperature", "IMU", "imu", "IMU temperature (C)", ("imu_temperature_c",), False),
    Field("imu_confidence", "IMU", "imu", "Confidence", ("imu_confidence",)),
    Field("imu_enabled", "IMU", "imu", "Enabled sensors", ("imu_gyro_enabled", "imu_accelerometer_enabled", "imu_compass_enabled")),
    Field("gps_latitude", "GPS", "gps", "Latitude (deg)", ("gps_latitude_deg",)),
    Field("gps_longitude", "GPS", "gps", "Longitude (deg)", ("gps_longitude_deg",)),
    Field("gps_altitude", "GPS", "gps", "Altitude (m)", ("gps_altitude_m",)),
    Field("gps_utc", "GPS", "gps", "GPS UTC date and time", ("gps_utc",)),
    Field("gps_fix", "GPS", "gps", "Fix quality", ("gps_fix_quality",)),
    Field("gps_satellites", "GPS", "gps", "Satellites used", ("gps_satellites_used",)),
    Field("gps_satellites_view", "GPS", "gps", "Satellites in view", ("gps_satellites_in_view",), False),
    Field("gps_hdop", "GPS", "gps", "HDOP", ("gps_hdop",)),
    Field("gps_pdop", "GPS", "gps", "PDOP", ("gps_pdop",), False),
    Field("gps_vdop", "GPS", "gps", "VDOP", ("gps_vdop",), False),
    Field("gps_speed", "GPS", "gps", "Speed (km/h)", ("gps_speed_km_h",), False),
    Field("gps_course", "GPS", "gps", "True course (deg)", ("gps_course_deg",), False),
    Field("gps_geoid", "GPS", "gps", "Geoidal separation (m)", ("gps_geoidal_separation_m",), False),
    Field("gps_mode", "GPS", "gps", "Fix type and mode", ("gps_fix_type", "gps_mode"), False),
    Field("temperature", "Environment", "pcb", "Temperature (C)", ("temperature_c",)),
    Field("humidity", "Environment", "pcb", "Humidity (%)", ("humidity_percent",)),
    Field("pressure", "Environment", "pcb", "Pressure (hPa)", ("pressure_hpa",)),
    Field("pcb_sensor_status", "Environment", "pcb", "Sensor validity", ("pcb_bme280_ok", "pcb_photoresistors_ok")),
    Field("ambient_light", "PCB", "pcb", "Ambient light (%)", ("ambient_light_percent",)),
    Field("raw_light_avg", "PCB", "pcb", "Raw light average (ADC counts)", ("raw_light_avg",)),
    Field("raw_light_1_avg", "PCB", "pcb", "Raw resistor 1 average (ADC counts)", ("raw_light_1_avg",)),
    Field("raw_light_2_avg", "PCB", "pcb", "Raw resistor 2 average (ADC counts)", ("raw_light_2_avg",)),
    Field("pcb_uptime", "PCB", "pcb", "MCU uptime (ms)", ("pcb_uptime_ms",)),
    Field("pcb_parse_errors", "PCB", "pcb", "Invalid JSON count", ("pcb_invalid_json_count",), False),
    Field("camera_frame", "Camera", "camera", "Images, frame number and UTC timestamp", ("camera_frame_number", "camera_frame_utc", "camera_image_path")),
    Field("camera_exposure", "Camera", "camera", "Exposure (driver value)", ("camera_exposure_driver_value",)),
    Field("camera_gain", "Camera", "camera", "Gain (driver value)", ("camera_gain_driver_value",)),
    Field("camera_brightness", "Camera", "camera", "Brightness (driver value)", ("camera_brightness_driver_value",), False),
    Field("camera_auto_exposure", "Camera", "camera", "Exposure mode", ("camera_exposure_mode",)),
    Field("camera_fps", "Camera", "camera", "Measured FPS", ("camera_measured_fps",)),
    Field("camera_format", "Camera", "camera", "Resolution and requested/driver FPS", ("camera_width_px", "camera_height_px", "camera_requested_fps", "camera_driver_fps")),
    Field("camera_platesolve", "Camera", "camera", "Plate-solved RA / Dec / status (unavailable)", ("camera_ra_hours", "camera_dec_deg", "camera_platesolve_status"), False, "Plate solving has not been implemented."),
)
FIELD_BY_KEY = {field.key: field for field in FIELDS}


def selected_fields(keys):
    keys = set(keys)
    unknown = keys - FIELD_BY_KEY.keys()
    if unknown:
        raise ValueError(f"Unknown log fields: {', '.join(sorted(unknown))}")
    if any(FIELD_BY_KEY[key].unavailable for key in keys):
        raise ValueError("An unavailable field was selected")
    if any(FIELD_BY_KEY[key].source == "camera" for key in keys):
        keys.add("camera_frame")
    return tuple(field for field in FIELDS if field.key in keys)
