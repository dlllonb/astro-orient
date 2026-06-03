# GPS_test_program.py

from GPSConnector import GPSReader


def main():
    gps = GPSReader(port="COM4", baudrate=9600, timeout=1.0)
    gps.connect()

    try:
        while True:
            data = gps.update_once()

            if data.has_fix:
                print(
                    f"Lat: {data.latitude:.6f}, "
                    f"Lon: {data.longitude:.6f}, "
                    f"Alt: {data.altitude} m, "
                    f"Sats: {data.satellites_in_view}, "
                    f"HDOP: {data.hdop}, "
                    f"speed: {data.speed_over_ground_kmph}"
                )
            else:
                print(
                    f"Waiting for GPS fix... "
                    f"Last sentence: {data.last_sentence_type}, "
                    f"Parse errors: {data.parse_errors}"
                )

    except KeyboardInterrupt:
        print("Stopping GPS reader.")

    finally:
        gps.close()


if __name__ == "__main__":
    main()