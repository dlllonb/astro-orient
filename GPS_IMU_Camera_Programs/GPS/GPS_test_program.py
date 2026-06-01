import serial

ser = serial.Serial("/dev/ttyUSB0", baudrate=9600, timeout=3000)
while True:
    data = ser.readline()
    if len(data) > 0:
        print(data.decode('utf-8'))
ser.close()