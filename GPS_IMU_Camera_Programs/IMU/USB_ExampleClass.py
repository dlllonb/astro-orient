import serial
import serial.tools.list_ports

"""This Com Class is used to communciate with sensors connected over USB. 
This class can also be used to communicate to bluetooth devices that are 
registered under Windows COM ports by feeding in the portname and setting
the timeout higher."""
class UsbCom:
    def __init__(self, portName=None, timeout=0.05):
        self.baud = 115200
        self.sensor = None
        self.portName = portName
        # This setting may need to be changed on slower hardware
        self.timeout = timeout
    def open(self):
        if self.portName is None:
            self.portName = input("Enter sensor COM port name (<Enter> to autodetectport):").strip()
            if self.portName == "":
                ports = serial.tools.list_ports.comports()
                self.portName = None
                for port in ports:
                    # 9334 is the vendor id of 3 Space products
                    if port.vid is not None and port.vid == 9334:
                        self.portName = port.device
                        print("sensor discovered on port:", self.portName)
                        try:
                            self.sensor = serial.Serial(self.portName, 115200, timeout=self.timeout)
                            return
                        except:
                            print("Error opening port:",self.portName)
                if self.portName == None:
                    print("sensor not discovered.")
                    exit(0)
        self.sensor = serial.Serial(self.portName, 115200, timeout=self.timeout)
        self.read(self.sensor.in_waiting)

    def close(self):
        self.sensor.close()

    def write(self, data, length):
        self.sensor.write(data)

    def read(self, numToRead):
        return self.sensor.read(numToRead)

