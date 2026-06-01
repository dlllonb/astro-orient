import USB_ExampleClass
from ThreeSpaceAPI import *

# Create communication object instance.
com = USB_ExampleClass.UsbCom()
# Create sensor instance. This will call the open function of the communication object.
sensor = ThreeSpaceSensor(com)
# Create list to hold data
dataList = []
# Specify the amount of data points we want.
amountToLog = 250
print("Starting data collection!")
for i in range(amountToLog):
    # Get reading from sensor, returns as tuple.
    reading = sensor.getTaredOrientation()
    # save reading to data list
    dataList.append(reading)
# close communication object and join any spawned threads
sensor.cleanup()
print("Logging data to file!")
# Create log file
logFile = open("exampleLog.txt","w")
for data in dataList:
    # Convert tuple to string, strips parenthesis, and adds new line before writing to file.
    logFile.write(str(data).strip('()') + '\n')

logFile.close()
print("Done!")
