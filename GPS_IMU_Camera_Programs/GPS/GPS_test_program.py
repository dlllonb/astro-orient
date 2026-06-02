import serial
import pynmea2
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

file = open('GPS_test.txt', encoding='utf-8')

for line in file.readlines():
    try:
        msg = pynmea2.parse(line)
        #print(type(msg))
        if isinstance(msg, pynmea2.types.talker.GGA):
            print(msg.timestamp)
            print(msg.lat, msg.lat_dir)
            print(msg.lon, msg.lon_dir)
            print()

        #print(repr(msg))

    except pynmea2.ParseError as e:
        print('Parse error: {}'.format(e))
        continue