"""
Copyright 2022, Yost Labs Inc
Released under Yost Labs 3-Space Open Source License
https://yostlabs.com/support/open-source-license/
Authors: Eric McCaw, Patrick Redoutey
"""

import struct
import types
import threading
import time
import sys

if not sys.version_info >= (3, 5):
    print("Warning: Python version {}.{} is lower than recommended 3.5 or greater!!".format(*sys.version_info))


class _Command:
    def __init__(self, name, num, returnFormat, parameterFormat, sensorTypes, docString, subCommand=None):
        self.name = name
        self.num = num
        self.subCommand = subCommand
        self.returnFormat = returnFormat
        self.startByte = 0xf7
        self.code = None
        self.docString = docString
        if len(parameterFormat) > 0:
            parameterFormat = parameterFormat.split()
            self.parameterFormat = parameterFormat[0]
            self.parameterNames = parameterFormat[1]
            self.parameterList = ""
            # We dont include the first element because it is a comma with nothing on the left side
            for param in self.parameterNames[1:].split(','):
                name = param.split(':')
                if "list" in name[1]:
                    name = "*" + name[0]
                else:
                    name = name[0]
                self.parameterList += "," + name
        else:
            self.parameterFormat = ""
            self.parameterNames = ""
            self.parameterList = ""
        self.sensorTypes = sensorTypes


    def generateCode(self, wireless=False):
        if 'DNG' not in self.sensorTypes and wireless is True:
            startByte = 0xfa
        else:
            startByte = 0xf9

        code = "def {name}(self{params}{logicalID}):\n"
        code += '''\t"""{docString}"""\n'''
        code += "\tretries = 3\n"
        code += "\tretData = None\n"
        code += "\twhile retries > 0:\n"
        code += "\t\ttry:\n"
        code += "\t\t\tcmd = bytearray()\n"
        code += "\t\t\tcmd.append({startByte})\n"
        if wireless and "DNG" not in self.sensorTypes:
            code += "\t\t\tcmd.append(logicalID)\n"
        code += "\t\t\tcmd.append({cmdNumber})\n"
        if self.subCommand is not None:
            code += "\t\t\tcmd.append({subCmdNumber})\n"
        if len(self.parameterList) > 0:
            code += "\t\t\tcmd += struct.pack('>{paramFormat}'{paramList})\n"
        code += "\t\t\tcmd.append((sum(cmd) - {startByte})%256)\n"
        code += "\t\t\tself.comClass.write(cmd,len(cmd))\n"
        if len(self.returnFormat) > 0:
            if "DNG" in self.sensorTypes:
                code += "\t\t\tretData = self._readcommandouput({retlen})\n"
                code += "\t\t\tretData = struct.unpack('>'+'{retFormat}',retData)\n"
            else:
                code += "\t\t\tretData = self._readcommandouput({retlen} + struct.calcsize('>'+{header}))\n"
                code += "\t\t\tretData = struct.unpack('>'+{header}+'{retFormat}',retData)\n"
            code += "\t\t\treturn retData\n"
        else:
            code += "\t\t\tif len({header})>0:\n"
            code += "\t\t\t\tretData = self._readcommandouput(struct.calcsize('>'+{header}))\n"
            code += "\t\t\t\tretData = struct.unpack('>'+{header},retData)\n"
            code += "\t\t\treturn retData\n"

        code += "\t\texcept:\n"
        code += "\t\t\tretries -=1\n"
        code += "\treturn -1\n"

        code = code.format(name=self.name, params=self.parameterNames, docString=self.docString,
                           logicalID="" if "DNG" in self.sensorTypes else ",logicalID=0", paramList=self.parameterList,
                           paramFormat=self.parameterFormat,
                           startByte=startByte, cmdNumber=self.num, subCmdNumber=self.subCommand,
                           retlen=struct.calcsize('>'+self.returnFormat), retFormat=self.returnFormat, header='self.header')
        self.code = code


# Streamable functions
class Streamable:
    """All available commands to stream are listed here."""
    READ_TARED_ORIENTATION_AS_QUAT = 0 #: :meta hide-value:
    READ_TARED_ORIENTATION_AS_EULER = 1#: :meta hide-value:
    READ_TARED_ORIENTATION_AS_MAT = 2#: :meta hide-value:
    READ_TARED_ORIENTATION_AS_AXIS_ANGLE = 3#: :meta hide-value:
    READ_TARED_ORIENTATION_AS_VECTOR = 4#: :meta hide-value:
    READ_DIFFERENCE_QUAT = 5#: :meta hide-value:
    READ_UNTARED_ORIENTATION_AS_QUAT = 6#: :meta hide-value:
    READ_UNTARED_ORIENTATION_AS_EULER = 7#: :meta hide-value:
    READ_UNTARED_ORIENTATION_AS_MAT = 8#: :meta hide-value:
    READ_UNTARED_ORIENTATION_AS_AXIS_ANGLE = 9#: :meta hide-value:
    READ_UNTARED_ORIENTATION_AS_VECTOR = 10#: :meta hide-value:
    READ_TARED_TWO_VECTOR_IN_SENSOR_FRAME = 11#: :meta hide-value:
    READ_UNTARED_TWO_VECTOR_IN_SENSOR_FRAME = 12#: :meta hide-value:
    READ_ALL_NORMALIZED_COMPONENT_SENSOR_DATA = 32#: :meta hide-value:
    READ_NORMALIZED_GYROSCOPE_VECTOR = 33#: :meta hide-value:
    READ_NORMALIZED_ACCELEROMETER_VECTOR = 34#: :meta hide-value:
    READ_NORMALIZED_COMPASS_VECTOR = 35#: :meta hide-value:
    READ_ALL_CORRECTED_COMPONENT_SENSOR_DATA = 37#: :meta hide-value:
    READ_CORRECTED_GYROSCOPE_VECTOR = 38#: :meta hide-value:
    READ_CORRECTED_ACCELEROMETER_VECTOR = 39#: :meta hide-value:
    READ_CORRECTED_COMPASS_VECTOR = 40#: :meta hide-value:
    READ_CORRECTED_LINEAR_ACCELERATION = 41#: :meta hide-value:
    READ_TEMPERATURE_C = 43#: :meta hide-value:
    READ_TEMPERATURE_F = 44#: :meta hide-value:
    READ_CONFIDENCE_FACTOR = 45#: :meta hide-value:
    READ_ALL_RAW_COMPONENT_SENSOR_DATA = 64#: :meta hide-value:
    READ_RAW_GYROSCOPE_VECTOR = 65#: :meta hide-value:
    READ_RAW_ACCELEROMETER_VECTOR = 66#: :meta hide-value:
    READ_RAW_COMPASS_VECTOR = 67#: :meta hide-value:
    READ_BATTERY_VOLTAGE = 201#: :meta hide-value:
    READ_BATTERY_PERCENTAGE = 202#: :meta hide-value:
    READ_BATTERY_STATUS = 203#: :meta hide-value:
    READ_BUTTON_STATE = 250#: :meta hide-value:
    NO_COMMAND = 255#: :meta hide-value:


_streamingCommands = {
    Streamable.READ_TARED_ORIENTATION_AS_QUAT: '4f',
    Streamable.READ_TARED_ORIENTATION_AS_EULER: '3f',
    Streamable.READ_TARED_ORIENTATION_AS_MAT: '9f',
    Streamable.READ_TARED_ORIENTATION_AS_AXIS_ANGLE: '3f f',
    Streamable.READ_TARED_ORIENTATION_AS_VECTOR: '3f 3f',
    Streamable.READ_DIFFERENCE_QUAT: '4f',
    Streamable.READ_UNTARED_ORIENTATION_AS_QUAT: '4f',
    Streamable.READ_UNTARED_ORIENTATION_AS_EULER: '3f',
    Streamable.READ_UNTARED_ORIENTATION_AS_MAT: '9f',
    Streamable.READ_UNTARED_ORIENTATION_AS_AXIS_ANGLE: '3f f',
    Streamable.READ_UNTARED_ORIENTATION_AS_VECTOR: '3f 3f',
    Streamable.READ_TARED_TWO_VECTOR_IN_SENSOR_FRAME: '3f 3f',
    Streamable.READ_UNTARED_TWO_VECTOR_IN_SENSOR_FRAME: '3f 3f',
    Streamable.READ_ALL_NORMALIZED_COMPONENT_SENSOR_DATA: '3f 3f 3f',
    Streamable.READ_NORMALIZED_GYROSCOPE_VECTOR: '3f',
    Streamable.READ_NORMALIZED_ACCELEROMETER_VECTOR: '3f',
    Streamable.READ_NORMALIZED_COMPASS_VECTOR: '3f',
    Streamable.READ_ALL_CORRECTED_COMPONENT_SENSOR_DATA: '3f 3f 3f',
    Streamable.READ_CORRECTED_GYROSCOPE_VECTOR: '3f',
    Streamable.READ_CORRECTED_ACCELEROMETER_VECTOR: '3f',
    Streamable.READ_CORRECTED_COMPASS_VECTOR: '3f',
    Streamable.READ_CORRECTED_LINEAR_ACCELERATION: '3f',
    Streamable.READ_TEMPERATURE_C: 'f',
    Streamable.READ_TEMPERATURE_F: 'f',
    Streamable.READ_CONFIDENCE_FACTOR: 'f',
    Streamable.READ_ALL_RAW_COMPONENT_SENSOR_DATA: '3f 3f 3f',
    Streamable.READ_RAW_GYROSCOPE_VECTOR: '3f',
    Streamable.READ_RAW_ACCELEROMETER_VECTOR: '3f',
    Streamable.READ_RAW_COMPASS_VECTOR: '3f',
    Streamable.READ_BATTERY_VOLTAGE: 'f',
    Streamable.READ_BATTERY_PERCENTAGE: 'B',
    Streamable.READ_BATTERY_STATUS: 'B',
    Streamable.READ_BUTTON_STATE: 'B',
    Streamable.NO_COMMAND: ''
}

STREAM_CONTINUOUSLY = 0xffffffff  # Max U32 : :meta hide-value:


class ThreeSpaceSensor:
    """Every instance of this class will dynamically generate functions based on the connected sensor type.
    When creating an instance of this class we will need a communication class with 4 methods(open, close, read, write)."""
    def __init__(self, comClass, streamingBufferLen=1000):
        self.comClass = comClass
        self.maxStreamingBufferLength = streamingBufferLen
        self.streamingBufferLock = threading.Lock()
        self.streamingThread = None
        self.comClass.open()
        self.whileStreamingBuffer = []
        self.sensorType = self._getsensortype()
        if "DNG" in self.sensorType:
            self.wireless = True
        else:
            self.wireless = False
        if self.wireless:
            self.streaming = [False] * 15
            self.streamingBuffer = [[], [], [], [], [], [], [], [], [], [], [], [], [], [], []]
        else:
            self.streaming = False
            self.streamingBuffer = []
        self.header, self.importantfields = self._parseresponseheader(self._getheader())
        self.funcs = {}
        for cmd in commandList:
            if cmd.sensorTypes[0] == '*':
                if self.sensorType in cmd.sensorTypes:
                    continue
            elif self.sensorType not in cmd.sensorTypes:
                continue
            cmd.generateCode(self.wireless)
            exec(cmd.code, globals(), self.funcs)
            setattr(self, cmd.name, types.MethodType(self.funcs[cmd.name], self))

        self.streamingDuration = self._getstreamingtiming()
        self.streamingFormat = self._getstreamingformat()

    def _getsensortype(self):
        cmd = bytearray((247, 230))
        cmd.append((sum(cmd) - 0xf7) % 256)
        self.comClass.write(cmd, len(cmd))
        retData = self.comClass.read(32)
        retData = struct.unpack('>32s', retData)
        return retData[0].decode("utf-8")[4:-10].strip()

    def _getheader(self):
        retries = 3
        while retries > 0:
            try:
                cmd = 222
                if self.wireless:
                    cmd = 220
                cmd = bytearray((247, cmd))
                cmd.append((sum(cmd) - 247) % 256)
                self.comClass.write(cmd, len(cmd))
                retData = self.comClass.read(4)
                retData = struct.unpack('>I', retData)
                if self.wireless:
                    neededFields = 0x55
                else:
                    neededFields = 0x44

                if retData[0] & neededFields != neededFields:
                    retData = retData[0] | neededFields
                    self.setResponseHeaderBitfield(retData)
                    return retData
                return retData[0]
            except:
                retries -= 1
        return -1

    def _readstreamingdata(self, packetSize):
        buffer = bytearray()
        reading = 1
        commandEchoIndex, dataLengthIndex = self.importantfields
        headersize = struct.calcsize('>' + self.header)
        streamingPacket = True
        size = None
        stopTime = None
        while self.streaming or reading:
            currentTime = time.time()
            reading = self.comClass.read(1)
            buffer += reading
            if size is None and len(buffer) >= headersize:
                if (buffer[dataLengthIndex] +headersize == packetSize) or (buffer[commandEchoIndex] != 255):
                    if buffer[commandEchoIndex] != 255:
                        streamingPacket = False
                    else:
                        streamingPacket = True
                    size = buffer[dataLengthIndex] + headersize
                else:
                    # something is wrong and we need to find the start of a new packet
                    buffer.pop(0)
                    size = None


            if len(buffer) == size:
                # if we should not be streaming but at least one sensor has continued to stream we need to stop it
                if not self.streaming and stopTime is None:
                    stopTime = currentTime
                elif stopTime is not None:
                    if currentTime - stopTime > 1:
                        self.stopStreaming()
                        stopTime = currentTime
                if streamingPacket:
                    read = struct.unpack(self.streamingFormat, buffer)
                    with self.streamingBufferLock:
                        self.streamingBuffer.append(read)
                        while -1 < self.maxStreamingBufferLength < len(self.streamingBuffer):
                            self.streamingBuffer.pop(0)
                else:
                    with self.streamingBufferLock:
                        self.whileStreamingBuffer.append(buffer.copy())

                size = None
                buffer.clear()

            elif len(buffer) > 100:
                size = None
                buffer.clear()

            if self.streaming and self.streamingDuration[0] >= 0:
                if currentTime - self.streamingDuration[1] > self.streamingDuration[0]:
                    self.streaming = False

    def _readstreamingdatawireless(self):
        buffer = bytearray()
        size = None
        logicalID = 0
        countlist = []
        for i in self.streamingFormat:
            temp = struct.calcsize(i)
            if temp > 0:
                countlist.append(temp)
        reading = 1
        stopTime = None
        # Fields for parsing header
        successIndex,commandEchoIndex,logicalIDIndex,dataLengthIndex  = self.importantfields
        headersize = struct.calcsize('>'+self.header)
        streamingPacket = True
        while any(self.streaming) or reading:
            currentTime = time.time()
            reading = self.comClass.read(1)
            buffer += reading
            if size is None and len(buffer) >= headersize:
                if buffer[successIndex] == 0 and 14 >= buffer[logicalIDIndex] >= 0 and ((buffer[dataLengthIndex] +headersize in countlist) or (buffer[commandEchoIndex] != 255)):
                    if buffer[commandEchoIndex] != 255:
                        streamingPacket = False
                    else:
                        streamingPacket = True
                    logicalID = buffer[logicalIDIndex]
                    size = buffer[dataLengthIndex] + headersize

                else:
                    # something is wrong and we need to find the start of a new packet
                    buffer.pop(0)
                    size = None


            if len(buffer) == size:
                # if we should not be streaming but at least one sensor has continued to stream we need to stop it
                if not any(self.streaming) and stopTime is None:
                    stopTime = currentTime
                elif stopTime is not None:
                    if currentTime - stopTime > 1:
                        self.stopStreaming(logicalID)
                        stopTime = currentTime
                if streamingPacket:
                    read = struct.unpack(self.streamingFormat[logicalID], buffer)
                    with self.streamingBufferLock:
                        self.streamingBuffer[logicalID].append(read)
                        while -1 < self.maxStreamingBufferLength < len(self.streamingBuffer[logicalID]):
                            self.streamingBuffer[logicalID].pop(0)
                else:
                    with self.streamingBufferLock:
                        self.whileStreamingBuffer.append(buffer.copy())

                size = None
                logicalID = 0
                buffer.clear()

            elif len(buffer) > 100:
                size = None
                logicalID = 0
                buffer.clear()


            for i in range(len(self.streaming)):
                if self.streaming[i] and self.streamingDuration[i][0] >= 0:
                    if currentTime - self.streamingDuration[i][1] > self.streamingDuration[i][0]:
                        self.streaming[i] = False

    def _parseresponseheader(self, header):
        index = 0
        importantBits = []
        headerFormat = ''
        if self.wireless:
            neededFields = 0x55
        else:
            neededFields = 0x44
        if header & 0x1:
            if 0x01 & neededFields:
                importantBits.append(index)
            index += 1
            headerFormat += 'B'
        if header & 0x2:
            index += 4
            headerFormat += 'I'
        if header & 0x4:
            if 0x4 & neededFields:
                importantBits.append(index)
            index += 1
            headerFormat += 'B'
        if header & 0x8:
            index += 1
            headerFormat += 'B'
        if header & 0x10:
            if 0x10 & neededFields:
                importantBits.append(index)
            index += 1
            headerFormat += 'B'
        if header & 0x20:
            index += 4
            headerFormat += 'I'
        if header & 0x40:
            if 0x40 & neededFields:
                importantBits.append(index)
            index += 1
            headerFormat += 'B'

        return headerFormat, importantBits

    def _getstreamingformat(self):
        format = '>'
        if self.wireless:
            format = ['>'] * 15
            logicalIDs = []
            # We dont want to poll all 15 slots if there is no sensor connected
            for i in range(15):
                serial = self.getSerialNumberAtLogicalID(i)[-1]
                if serial != 0:
                    logicalIDs.append(i)
            for i in logicalIDs:
                slots = self.getStreamingSlots(logicalID=i)
                if slots != -1 and slots[0] == 0:
                    format[i] += self.header
                    for cmd in slots[-8:]:
                        format[i] += _streamingCommands[cmd]
        else:
            slots = self.getStreamingSlots()
            format += self.header

            for cmd in slots[-8:]:
                format += _streamingCommands[cmd]
        return format

    def _getstreamingtiming(self):
        duration = (0, 0)
        if self.wireless:
            duration = [(0, 0)] * 15
            logicalIDs = []
            for i in range(15):
                serial = self.getSerialNumberAtLogicalID(i)[-1]
                if serial != 0:
                    logicalIDs.append(i)
            for i in logicalIDs:
                timing = self.getStreamingTiming(logicalID=i)
                if timing != -1:
                    if timing[-2] == STREAM_CONTINUOUSLY:
                            duration[i] = (-1, -1)
                    else:
                        duration[i] = ((timing[-1] + timing[-2]) / 1000000, 0)
        else:
            timing = self.getStreamingTiming()
            if timing[-2] == STREAM_CONTINUOUSLY:
                duration = (-1, -1)
            else:
                duration = ((timing[-1] + timing[-2]) / 1000000, 0)
        return duration
    def _readcommandouput(self,ammountToRead):
        retData = None
        if self.wireless:
            if any(self.streaming):
                timeoutTimer = time.time()
                while len(self.whileStreamingBuffer) < 1:
                    time.sleep(0)
                    if time.time()-timeoutTimer > 0.3:
                        raise TimeoutError("Streaming thread not returning command response in time")
                with self.streamingBufferLock:
                    retData = self.whileStreamingBuffer.pop(0)
            else:
                retData = self.comClass.read(ammountToRead)
        else:
            if self.streaming:
                with self.streamingBufferLock:
                    retData = self.whileStreamingBuffer.pop(0)
            else:
                retData = self.comClass.read(ammountToRead)
        return retData

    def generateStaticClass(self, filename=None):
        """This will generate a python file containing a sensor specific class that will not dynamically create functions.
        Use cases for this would be where speed is important, debugging any issues, seeing how we talk to write commands"""
        import inspect

        if filename is None:
            filename = "ThreeSpace{sensor}API.py".format(sensor=self.sensorType)
        file = open(filename, "w")
        code = '''"""\nCopyright 2022, Yost Labs Inc\nReleased under Yost Labs 3-Space Open Source License\nhttps://yostlabs.com/support/open-source-license/\nAuthor: Eric McCaw\n"""\n'''
        code += "import struct, threading, time\n"
        code += "# Streamable functions\n"
        code += inspect.getsource(Streamable)
        code += "_streamingCommands = {streamableCmds}\n".format(streamableCmds=_streamingCommands.__str__())
        code += "STREAM_CONTINUOUSLY = 0xffffffff\n"
        code += "\n\nclass ThreeSpaceSensor:\n"
        code += "\tdef __init__(self, comClass, streamingBufferLen=1000):\n"
        code += "\t\tself.comClass = comClass\n"
        code += "\t\tself.comClass.open()\n"
        code += "\t\tself.sensorType = self._getsensortype()\n"
        code += "\t\tself.streamingBufferLock = threading.Lock()\n"
        code += "\t\tself.streamingThread = None\n"
        code += "\t\tself.maxStreamingBufferLength = streamingBufferLen\n"
        code += "\t\tself.whileStreamingBuffer = []\n"

        if self.wireless:
            code += "\t\tself.wireless = True\n"
            code += "\t\tself.streaming = [False] * 15\n"
            code += "\t\tself.streamingBuffer = [[], [], [], [], [], [], [], [], [], [], [], [], [], [], []]\n"
        else:
            code += "\t\tself.wireless = False\n"
            code += "\t\tself.streaming = False\n"
            code += "\t\tself.streamingBuffer = []\n"
        code += "\t\tself.header,self.importantfields = self._parseresponseheader(self._getheader())\n"
        code += "\t\tself.streamingDuration = self._getstreamingtiming()\n"
        code += "\t\tself.streamingFormat = self._getstreamingformat()\n"

        functions = [self._getsensortype, self.setStreamingSlots, self.startStreaming,
                     self.stopStreaming, self.getNewestStreamingPacket, self.getOldestStreamingPacket, self.cleanup,
                     self.setResponseHeaderBitfield, self._getheader, self._parseresponseheader, self.clearStreamingBuffer,self._readcommandouput,
                     self._getstreamingformat,self._getstreamingtiming]
        if self.wireless:
            functions.append(self._readstreamingdatawireless)
        else:
            functions.append(self._readstreamingdata)

        for func in functions:
            code += inspect.getsource(func)
        code += '\t'
        for cmd in commandList:
            if cmd.code is not None:
                for char in cmd.code:
                    code += char
                    if char == '\n':
                        code += '\t'
        code = code.replace("\t","    ")
        file.write(code)
        file.close()

    def cleanup(self):
        if self.streamingThread is not None:
            if self.wireless:
                for i in range(len(self.streaming)):
                    self.streaming[i] = False
            else:
                self.streaming = False
            self.streamingThread.join()
            self.streamingThread = None
        self.comClass.close()

    def getNewestStreamingPacket(self, logicalID=0):
        """When a sensor is streaming the parsed data will be stored in a buffer. This method will safely get and return
        the most recent data packet from the sensor."""
        if self.streaming:
            with self.streamingBufferLock:
                if self.wireless:
                    if len(self.streamingBuffer[logicalID]) > 0:
                        return self.streamingBuffer[logicalID].pop()
                else:
                    if len(self.streamingBuffer) > 0:
                        return self.streamingBuffer.pop()

    def getOldestStreamingPacket(self, logicalID=0):
        """When a sensor is streaming the parsed data will be stored in a buffer. This method will safely get and return
            the oldest data packet from the sensor."""
        with self.streamingBufferLock:
            if self.wireless:
                if len(self.streamingBuffer[logicalID]) > 0:
                    return self.streamingBuffer[logicalID].pop(0)
            else:
                if len(self.streamingBuffer) > 0:
                    return self.streamingBuffer.pop(0)

    def clearStreamingBuffer(self, logicalID=0):
        """When a sensor is streaming the parsed data will be stored in a buffer. This method will clear all data from the buffer."""
        with self.streamingBufferLock:
            if self.wireless:
                self.streamingBuffer[logicalID] = []
            else:
                self.streamingBuffer = []

    def setResponseHeaderBitfield(self, headerConfig: int):
        """This function combines SetWiredResponseHeaderBitfield and SetWirelessResponseHeaderBitfield to simplify the usage
        of the header functionality
        Configures the response header for data returned.
        The only parameter is a four-byte bitfield that
        determines which data is prepended to all data
        responses. The following bits are used:
        0x1: (1 byte) Success/Failure, with non-zero values
        representing failure.
        0x2: (4 bytes) Timestamp, in microseconds.
        0x4: (1 byte) Command echo outputs the called
        command. Returns 0xFF for streamed data.
        0x8: (1 byte) Additive checksum over returned data,
        but not including response header.
        0x10: (1 byte) Logical ID, returns 0xFE for wired
        sensors. Meant to be used with 3-Space Dongle
        response header (For more info, see command
        0xDB).
        0x20: (4 bytes) Serial number
        0x40: (1 byte) Data length, returns the length of the
        requested data, not including response header.
        This setting can be committed to non-volatile flash
        memory by calling the Commit Settings command.
        For more information on Response Headers, please
        refer to the users manual in section 4.4.
        """
        retries = 3
        retData = None
        # When Streaming we use these header fields to identify packets
        if self.wireless:
            neededFields = 0x55
        else:
            neededFields = 0x44
        if headerConfig & neededFields != neededFields:
            headerConfig = headerConfig | neededFields
        while retries > 0:
            try:
                cmd = bytearray()
                cmd.append(249)
                if self.wireless:
                    cmd.append(219)
                else:
                    cmd.append(221)
                cmd += struct.pack('>I', headerConfig)
                cmd.append((sum(cmd) - 249) % 256)
                self.comClass.write(cmd, len(cmd))

                self.header, self.importantfields = self._parseresponseheader(headerConfig)

                if len(self.header) > 0:
                    if self.wireless:
                        if any(self.streaming):
                            with self.streamingBufferLock:
                                retData = self.whileStreamingBuffer.pop(0)
                        else:
                            retData = self.comClass.read(struct.calcsize('>' + self.header))
                    else:
                        if self.streaming:
                            with self.streamingBufferLock:
                                retData = self.whileStreamingBuffer.pop(0)
                        else:
                            retData = self.comClass.read(struct.calcsize('>' + self.header))
                    retData = struct.unpack('>' + self.header, retData)

                return retData
            except:
                retries -= 1
        return -1

    def setStreamingSlots(self, slot1=Streamable.NO_COMMAND, slot2=Streamable.NO_COMMAND, slot3=Streamable.NO_COMMAND, slot4=Streamable.NO_COMMAND,
                          slot5=Streamable.NO_COMMAND, slot6=Streamable.NO_COMMAND, slot7=Streamable.NO_COMMAND, slot8=Streamable.NO_COMMAND, logicalID=0):
        """Configures data output slots for streaming mode. Command accepts a list of eight bytes, where each byte
        corresponds to a different data command. Every streaming iteration, each command will be executed in order and
        the resulting data will be output in the specified slot. Valid commands are commands in the ranges 0x0 - 0x10,
        0x20 - 0x30, 0x40 - 0x50, 0xC9 - 0xCA (for battery-powered sensors) and 0xFA. A slot value of 0xFF 'clears' the
        slot and prevents any data from being written in that position. This command can fail if there is an invalid
        command passed in as any of the parameters or if the total allotted size is exceeded. Upon failure, all slots
        will be reset to 0xFF. This setting can be saved to nonvolatile flash memory using the Commit Settings command. """
        slots = [slot1, slot2, slot3, slot4, slot5, slot6, slot7, slot8]
        cmds = []
        retData = None
        if self.wireless:
            startByte = 0xfa
        else:
            startByte = 0xf9
        for slot in slots:
            cmds.append(slot)
        cmd = bytearray()
        cmd.append(startByte)
        if self.wireless:
            cmd.append(logicalID)
        cmd.append(80)
        cmd += struct.pack('>8B', *cmds)
        cmd.append((sum(cmd) - startByte) % 256)
        self.comClass.write(cmd, len(cmd))
        streamingFormat = '>' + self.header
        for i in slots:
            streamingFormat += _streamingCommands[i]
        if self.wireless:
            self.streamingFormat[logicalID] = streamingFormat

        else:
            self.streamingFormat = streamingFormat
        if len(self.header) > 0:
            retData = self._readcommandouput(struct.calcsize('>' + self.header))
            retData = struct.unpack('>' + self.header, retData)
        return retData

    def setStreamingTiming(self, interval: int, duration: int, delay: int, logicalID=0):
        """Configures timing information for a streaming session. All parameters are specified in microseconds. The first parameter is the interval, which specifies how often data will be output. A value of 0 means that data will be output at the end of every filter loop. Aside from 0, values lower than 1000 will be clamped to 1000. The second parameter is the duration, which specifies the length of the streaming session. If this value is set to 0xFFFFFFFF, streaming will continue indefinitely until it is stopped via command 0x56. The third parameter is the delay, which specifies a n amount of time the sensor will wait before outputting the first packet of streaming data. This setting can be saved to non-volatile flash memory using the Commit Settings command."""
        retries = 3
        retData = None
        while retries > 0:
            try:
                cmd = bytearray()
                cmd.append(250)
                cmd.append(logicalID)
                cmd.append(82)
                cmd += struct.pack('>III', interval, duration, delay)
                cmd.append((sum(cmd) - 250) % 256)
                self.comClass.write(cmd, len(cmd))
                if duration == STREAM_CONTINUOUSLY:
                    timing = (-1, -1)
                else:
                    timing = ((duration + delay) / 1000000, 0)
                if self.wireless:
                    self.streamingDuration[logicalID] = timing
                else:
                    self.streamingDuration = timing
                if len(self.header) > 0:
                    retData = self._readcommandouput(struct.calcsize('>' + self.header))
                    retData = struct.unpack('>' + self.header, retData)
                return retData
            except:
                retries -= 1
        return -1


    def startStreaming(self, logicalID=0):
        """Start a streaming session using the current slot and timing configuration."""
        streaming = self.streaming
        startByte = 0xf9
        if self.wireless:
            streaming = self.streaming[logicalID]
            startByte = 0xfa
        if not streaming:
            if self.wireless:
                self.streamingDuration[logicalID] = (self.streamingDuration[logicalID][0],time.time())
            else:
                self.streamingDuration = (self.streamingDuration[0],time.time())
            cmd = bytearray()
            cmd.append(startByte)
            if self.wireless:
                cmd.append(logicalID)
            cmd.append(85)
            cmd.append((sum(cmd) - startByte) % 256)
            self.comClass.write(cmd, len(cmd))
            if len(self.header) > 0 and not self.wireless:
                retData = self.comClass.read(struct.calcsize('>'+self.header))
                retData = struct.unpack('>' + self.header, retData)
            if self.wireless:
                self.streaming[logicalID] = True
                if self.streamingThread is not None:
                    return
                self.streamingThread = threading.Thread(target=self._readstreamingdatawireless)
                self.streamingThread.start()
            else:
                self.streaming = True
                self.streamingThread = threading.Thread(target=self._readstreamingdata,
                                                        args=(struct.calcsize(self.streamingFormat),))
                self.streamingThread.start()
            if len(self.header) > 0:
                return

    def stopStreaming(self, logicalID=0):
        """Stop the current streaming session."""
        streaming = self.streaming
        startByte = 0xf7
        if self.wireless:
            streaming = self.streaming[logicalID]
            startByte = 0xf8
        if streaming:
            cmd = bytearray()
            cmd.append(startByte)
            if self.wireless:
                cmd.append(logicalID)
            cmd.append(86)
            cmd.append((sum(cmd) - startByte) % 256)
            self.comClass.write(cmd, len(cmd))
            if self.wireless:
                self.streaming[logicalID] = False
                if not any(self.streaming):
                    self.streamingThread.join()
                    self.streamingThread = None
            else:
                self.streaming = False
                self.streamingThread.join()
                self.streamingThread = None


    def getTaredOrientation(self, logicalID=0):
        """Returns the filtered, tared orientation estimate in quaternion form"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTaredOrientationAsEulerAngles(self, logicalID=0):
        """Returns the filtered, tared orientation estimate in euler angle form"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTaredOrientationAsRotationMatrix(self, logicalID=0):
        """Returns the filtered, tared orientation estimate in rotation matrix form """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTaredOrientationAsAxisAngles(self, logicalID=0):
        """Returns the filtered, tared orientation estimate in axis-angle form"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTaredOrientationAsTwoVector(self, logicalID=0):
        """Returns the filtered, tared orientation estimate in two vector form, where the first vector refers to forward and the second refers to down."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getDifferenceQuaternion(self, logicalID=0):
        """Returns the difference between the measured orientation from last frame and this frame."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUntaredOrientation(self, logicalID=0):
        """Returns the filtered, untared orientation estimate in quaternion form."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUntaredOrientationAsEulerAngles(self, logicalID=0):
        """Returns the filtered, untared orientation estimate in euler angle form"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUntaredOrientationAsRotationMatrix(self, logicalID=0):
        """Returns the filtered, untared orientation estimate in rotation matrix form"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUntaredOrientationAsAxisAngles(self, logicalID=0):
        """Returns the filtered, untared orientation estimate in axis-angle form"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUntaredOrientationAsTwoVector(self, logicalID=0):
        """Returns the filtered, untared orientation estimate in two vector form, where the first vector refers to north and the second refers to gravity"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTaredTwoVectorInSensorFrame(self, logicalID=0):
        """Returns the filtered, tared orientation estimate in two vector form, where the first vector refers to forward and the second refers to down. These vectors are given in the sensor reference frame and not the global reference frame. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUntaredTwoVectorInSensorFrame(self, logicalID=0):
        """Returns the filtered, untared orientation estimate in two vector form, where the first vector refers to north and the second refers to gravity. These vectors are given in the sensor reference frame and not the global reference frame"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAllNormalizedComponentSensorData(self, logicalID=0):
        """Returns the normalized gyro rate vector, accelerometer vector, and compass vector. Note that the gyro vector is in units of radians/sec, while the accelerometer and compass are unit-length vectors indicating the direction of gravity and north, respectively. These two vectors do not have any magnitude data associated with them. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getNormalizedGyroRate(self, logicalID=0):
        """Returns the normalized gyro rate vector, which is in units of radians/sec."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getNormalizedAccelerometerVector(self, logicalID=0):
        """Returns the normalized accelerometer vector. Note that this is a unit-vector indicating the direction of gravity. This vector does not have any magnitude data associated with it. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getNormalizedCompassVector(self, logicalID=0):
        """Returns the normalized compass vector. Note that this is a unit-vector indicating the direction of gravity. This vector does not have any magnitude data associated with it."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAllCorrectedComponentSensorData(self, logicalID=0):
        """Returns the corrected gyro rate vector, accelerometer vector, and compass vector. Note that the gyro vector is in units of radians/sec, the accelerometer vector is in units of G, and the compass vector is in units of gauss"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCorrectedGyroRate(self, logicalID=0):
        """Returns the corrected gyro rate vector, which is in units of radians/sec. Note that this result is the same data returned by the normalized gyro rate command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCorrectedAccelerometerVector(self, logicalID=0):
        """Returns the acceleration vector in units of G. Note that this acceleration will include the static component of acceleration due to gravity."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCorrectedCompassVector(self, logicalID=0):
        """Returns the compass vector in units of gauss."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCorrectedLinearAccelerationInGlobalSpace(self, logicalID=0):
        """Returns the linear acceleration of the device, which is the overall acceleration which has been orientation compensated and had the component of acceleration due to gravity removed. Uses the untared orientation."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def correctRawGyroData(self, x: float, y: float, z: float, logicalID=0):
        """Converts the supplied raw data gyroscope vector to its corrected data representation."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def correctRawAccelData(self, x: float, y: float, z: float, logicalID=0):
        """Converts the supplied raw data accelerometer vector to its corrected data representation. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def correctRawCompassData(self, x: float, y: float, z: float, logicalID=0):
        """Converts the supplied raw data compass vector to its corrected data representation"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTemperatureC(self, logicalID=0):
        """Returns the temperature of the sensor in Celsius."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTemperatureF(self, logicalID=0):
        """Returns the temperature of the sensor in Fahrenheit"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getConfidenceFactor(self, logicalID=0):
        """Returns a value indicating how much the sensor is being moved at the moment. This value will return 1 if the sensor is completely stationary, and will return 0 if it is in motion. This command can also return values in between indicating how much motion the sensor is experiencing"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAllRawComponentSensorData(self, logicalID=0):
        """Returns the raw gyro rate vector, accelerometer vector and compass vector as read directly from the component sensors without any additional postprocessing. The range of values is dependent on the currently selected range for each respective sensor. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getRawGyroRate(self, logicalID=0):
        """Returns the raw gyro rate vector as read directly from the gyroscope without any additional postprocessing. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getRawAccelerometerVector(self, logicalID=0):
        """Returns the raw acceleration vector as read directly from the accelerometer without any additional postprocessing."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getRawCompassVector(self, logicalID=0):
        """Returns the raw compass vector as read directly from the compass without any additional postprocessing."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStreamingSlots(self, logicalID=0):
        """Returns the current streaming slots configuration."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStreamingTiming(self, logicalID=0):
        """Returns the current streaming timing information."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def updateCurrentTimestamp(self, timestamp: int, logicalID=0):
        """Set the current internal timestamp to the specified value."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setEulerAngleDecompositionOrder(self, order: int, logicalID=0):
        """Sets the current euler angle decomposition order, which determines how the angles returned from command 0x1 are decomposed from the full quaternion orientation. Possible values are 0x0 for XYZ, 0x1 for YZX, 0x2 for ZXY, 0x3 for ZYX, 0x4 for XZY or 0x5 for YXZ (default)."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def offsetWithCurrentOrientation(self, logicalID=0):
        """Sets the offset orientation to be the same as the current filtered orientation."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def resetBaseOffset(self, logicalID=0):
        """Sets the base offset to an identity quaternion."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def offsetWithQuaternion(self, x: float, y: float, z: float, w: float,
                             logicalID=0):
        """Sets the offset orientation to be the same as the supplied orientation, which should be passed as a quaternion."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setBaseOffsetWithCurrentOrientation(self, logicalID=0):
        """Sets the base offset orientation to be the same as the current filtered orientation."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def tareWithCurrentOrientation(self, logicalID=0):
        """Sets the tare orientation to be the same as the current filtered orientation."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def tareWithQuaternion(self, x: float, y: float, z: float, w: float,
                           logicalID=0):
        """Sets the tare orientation to be the same as the supplied orientation, which should be passed as a quaternion."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def tareWithRotationMatrix(self, matrix: list, logicalID=0):
        """Sets the tare orientation to be the same as the supplied orientation, which should be passed as a rotation matrix. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setStaticAccelerometerTrustValue(self, trustValue: float, logicalID=0):
        """Determines how trusted the accelerometer contribution is to the overall orientation estimation. Trust is 0 to 1, with 1 being fully trusted and 0 being not trusted at all."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setConfidenceAccelerometerTrustValues(self, minTrustValue: float,
                                              maxTrustValue: float,
                                              logicalID=0):
        """Determines how trusted the accelerometer contribution is to the overall orientation estimation. Instead of using a single value, uses a minimum and maximum value. Trust values will be selected from this range depending on the confidence factor. This can have the effect of smoothing out the accelerometer when the sensor is in motion."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setStaticCompassTrustValue(self, trustValue: float, logicalID=0):
        """Determines how trusted the accelerometer contribution is to the overall orientation estimation. tribution is to the overall orientation estimation. Trust is 0 to 1, with 1 being fully trusted and 0 being not trusted at all."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setConfidenceCompassTrustValues(self, minTrustValue: float,
                                        maxTrustValue: float, logicalID=0):
        """Determines how trusted the compass contribution is to the overall orientation estimation. Instead of using a single value, uses a minimum and maximum value. Trust values will be selected from this range depending on the confidence factor. This can have the effect of smoothing out the compass when the sensor is in motion. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setReferenceVectorMode(self, mode: int, logicalID=0):
        """Set the current reference vector mode. Parameter can be 0 for single static mode, which uses a certain reference vector for the compass and another certain vector for the accelerometer at all times, 1 for single auto mode, which uses (0, -1, 0) as the reference vector for the accelerometer at all times and uses the average angle between the accelerometer and compass to calculate the compass reference vector once upon initiation of this mode, or 2 for single auto continuous mode, which works similarly to single auto mode, but calculates this continuously."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setOversampleRate(self, gyroSamples: int, accelSamples: int,
                          compassSamples: int, logicalID=0):
        """Sets the number of times to sample each component sensor for each iteration of the filter. This can smooth out readings at the cost of responsiveness. If this value is set to 0 or 1, no oversampling occurs-otherwise, the number of samples per iteration depends on the specified parameter, up to a maximum of 65535. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setGyroscopeEnabled(self, enabled: bool, logicalID=0):
        """Enable or disable gyroscope readings as inputs to the orientation estimation. Note that updated gyroscope readings are still accessible via commands. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setAccelerometerEnabled(self, enabled: bool, logicalID=0):
        """Enable or disable accelerometer readings as inputs to the orientation estimation. Note that updated accelerometer readings are still accessible via commands. This setting can be saved to non-volatile flash memory using the Commit Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setCompassEnabled(self, enabled: bool, logicalID=0):
        """Enable or disable compass readings as inputs to the orientation estimation. Note that updated compass readings are still accessible via commands. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setMIModeEnabled(self, enabled: bool, logicalID=0):
        """Enables MI mode, which is meant to protect against some magnetic disturbances. See the Quick Start guide for more information. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setMIModeParameters(self, params: list, logicalID=0):
        """Sets up parameters for MI mode. A description of these parameters will be added at a later date. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def beginMIModeFieldCalibration(self, logicalID=0):
        """Begins the calibration process for MI mode. The sensor should be left in a magnetically unperturbed area for 3-4 seconds after this is called for calibration to succeed. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setAxisDirections(self, direction: int, logicalID=0):
        """Sets alternate directions for each of the natural axes
         of the sensor. The only parameter is a bitfield
         representing the possible combinations of axis
         swapping. The lower 3 bits specify where each of the
         natural axes appears:
         000: X: Right, Y: Up, Z: Forward (left-handed
         system, standard operation)
         001: X: Right, Y: Forward, Z: Up (right-handed
         system)
         002: X: Up, Y: Right, Z: Forward (right-handed
         system)
         003: X: Forward, Y: Right, Z: Up (left-handed
         system)
         004: X: Up, Y: Forward, Z: Right (left-handed
         system)
         005: X: Forward, Y: Up, Z: Right (right-handed
         system)
         (For example, using X: Right, Y: Forward, Z: Up
         means that any values that appear on the positive
         vertical(Up) axis of the sensor will be the third(Z)
         component of any vectors and will have a positive
         sign, and any that appear on the negative vertical
         axis will be the Z component and will have a negative
         sign.)
         The 3 bits above those are used to indicate which
         axes, if any, should be reversed. If it is cleared, the
         axis will be pointing in the positive direction.
         Otherwise, the axis will be pointed in the negative
         direction. (Note: These are applied to the axes after
         the previous conversion takes place).
         Bit 4: Positive/Negative Z (Third resulting component)
         Bit 5: Positive/Negative Y (Second resulting
         component)
         Bit 6: Positive/Negative X (First resulting component)
         Note that for each negation that is applied, the
         handedness of the system flips. So, if X and Z are
         negative and you are using a left-handed system, the
         system will still be left handed, but if only X is
         negated, the system will become right-handed."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setRunningAveragePercent(self, gyroPercent: float, accelPercent: float,
                                 compassPercent: float,
                                 orientationPercent: float, logicalID=0):
        """Sets what percentage of running average to use on a
         component sensor, or on the sensor's orientation.
         This is computed as follows:
         total_value = total_value* percent
         total_value = total_value + current_value * (1 -
         percent)
         current_value = total_value
         If the percentage is 0, the running average will be
         shut off completely. Maximum value is 1. This
         setting can be saved to non-volatile flash memory
         using the Commit Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setCompassReferenceVector(self, x: float, y: float, z: float,
                                  logicalID=0):
        """Sets the static compass reference vector for Single Reference Mode. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setAccelerometerReferenceVector(self, x: float, y: float, z: float,
                                        logicalID=0):
        """Sets the static accelerometer reference vector for Single Reference Mode. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def resetFilter(self, logicalID=0):
        """Resets the state of the currently selected filter."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setAccelerometerRange(self, range: int, logicalID=0):
        """Only parameter is the new accelerometer range, which can be 0 for 2g (Default range), which can be 1 for 4g, or 2 for 8g. Higher ranges can detect and report larger accelerations, but are not as accurate for smaller accelerations. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setFilterMode(self, mode: int, logicalID=0):
        """Used to disable the orientation filter or set the orientation filter mode. Changing this parameter can be useful for tuning filter-performance versus orientation-update rates. Passing in a parameter of 0 places the sensor into IMU mode, a 1 places the sensor into Kalman Filtered Mode (Default mode), a 2 places the sensor into Q-COMP Filter Mode, a 3 places the sensor into Q-GRAD Filter Mode. More information can be found in the users manual in section 3.1.5. This setting can be saved to non-volatile flash memory using the Commit Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setRunningAverageMode(self, mode: int, logicalID=0):
        """Used to further smooth out the orientation at the cost of higher latency. Passing in a parameter of 0 places the sensor into a static running average mode, a 1 places the sensor into a confidencebased running average mode, which changes the running average factor based upon the confidence factor, which is a measure of how 'in motion' the sensor is. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setGyroscopeRange(self, range: int, logicalID=0):
        """Only parameter is the new gyroscope range, which can be 0 for 250 DPS, 1 for 500 DPS, or 2 for 2000 DPS (Default range). Higher ranges can detect and report larger angular rates, but are not as accurate for smaller angular rates. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setCompassRange(self, range: int, logicalID=0):
        """Only parameter is the new compass range, which can be 0 for 0.88G, 1 for 1.3G (Default range), 2 for 1.9G, 3 for 2.5G, 4 for 4.0G, 5 for 4.7G, 6 for 5.6G, or 7 for 8.1G. Higher ranges can detect and report larger magnetic field strengths but are not as accurate for smaller magnetic field strengths. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTareOrientationAsQuaternion(self, logicalID=0):
        """Returns the current tare orientation as a quaternion. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTareOrientationAsRotationMatrix(self, logicalID=0):
        """Returns the current tare orientation as a rotation matrix."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAccelerometerTrustValues(self, logicalID=0):
        """Returns the current accelerometer min and max trust values. If static trust values were set, both of these will be the same. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCompassTrustValues(self, logicalID=0):
        """Returns the current compass min and max trust values. If static trust values were set, both of these will be the same."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCurrentUpdateRate(self, logicalID=0):
        """Reads the amount of time taken by the last filter update step. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCompassReferenceVector(self, logicalID=0):
        """Reads the current compass reference vector. Note that this is not valid if the sensor is in Multi Reference Vector mode. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAccelerometerReferenceVector(self, logicalID=0):
        """Reads the current compass reference vector. Note that this is not valid if the sensor is in Multi Reference Vector mode. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getReferenceVectorMode(self, logicalID=0):
        """Reads the current reference vector mode. Return value can be 0 for single static, 1 for single auto, or 2 for single auto continuous. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getMIModeEnabled(self, logicalID=0):
        """Returns a value indicating whether MI mode is currently on or not: 0 for off, 1 for on."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getMIModeParameters(self, logicalID=0):
        """Returns the MI mode parameter list. A description of these will be added at a later date. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getGyroscopeEnabledState(self, logicalID=0):
        """Returns a value indicating whether the gyroscope contribution is currently part of the orientation estimate: 0 for off, 1 for on. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAccelerometerEnabledState(self, logicalID=0):
        """Returns a value indicating whether the accelerometer contribution is currently part of the orientation estimate: 0 for off, 1 for on. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCompassEnabledState(self, logicalID=0):
        """Returns a value indicating whether the compass contribution is currently part of the orientation estimate: 0 for off, 1 for on. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAxisDirection(self, logicalID=0):
        """Returns a value indicating the current axis direction setup. For more information on the meaning of this value, please refer to the Set Axis Direction command (116). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getOverSampleRate(self, logicalID=0):
        """Returns values indicating how many times each component sensor is sampled before being stored as raw data. A value of 1 indicates that no oversampling is taking place, while a value that is higher indicates the number of samples per component sensor per filter update step. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getRunningAveragePercent(self, logicalID=0):
        """Returns the running average percent value for each component sensor and for the orientation. The value indicates what portion of the previous reading is kept and incorporated into the new reading."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAccelerometerRange(self, logicalID=0):
        """Return the current accelerometer measurement range, which can be a 0 for 2g, 1 for 4g or a 2 for 8g. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getFilterMode(self, logicalID=0):
        """Returns the current filter mode, which can be 0 for IMU mode, 1 for Kalman, 2 for Q-COMP, or 3 for QGRAD. For more information, please refer to the Set Filter Mode command (123). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getRunningAverageMode(self, logicalID=0):
        """Reads the selected mode for the running average, which can be 0 for normal or 1 for confidence."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getGyroscopeRange(self, logicalID=0):
        """Reads the current gyroscope measurement range, which can be 0 for 250 DPS, 1 for 500 DPS or 2 for 2000 DPS. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCompassRange(self, logicalID=0):
        """Reads the current compass measurement range, which can be 0 for 0.88G, 1 for 1.3G, 2 for 1.9G, 3 for 2.5G, 4 for 4.0G, 5 for 4.7G, 6 for 5.6G or 7 for 8.1G. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getEulerAngleDecompositionOrder(self, logicalID=0):
        """Reads the current euler angle decomposition order."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getOffsetOrientationAsQuaternion(self, logicalID=0):
        """Returns the current offset orientation as a quaternion."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setCompassCalibrationCoefficients(self, matrix: list, biasX: float,
                                          biasY: float, biasZ: float,
                                          logicalID=0):
        """Sets the current compass calibration parameters to the specified values. These consist of a bias which is added to the raw data vector and a matrix by which the value is multiplied. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setAccelerometerCalibrationCoefficients(self, matrix: list,
                                                biasX: float, biasY: float,
                                                biasZ: float, logicalID=0):
        """Sets the current accelerometer calibration parameters to the specified values. These consist of a bias which is added to the raw data vector and a matrix by which the value is multiplied. This setting can be saved to non-volatile flash memory using the Commit Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCompassCalibrationCoefficients(self, logicalID=0):
        """Return the current compass calibration parameters."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAccelerometerCalibrationCoefficients(self, logicalID=0):
        """Return the current accelerometer calibration parameters. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getGyroscopeCalibrationCoefficients(self, logicalID=0):
        """Return the current gyroscope calibration parameters."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def beginGyroscopeAutoCalibration(self, logicalID=0):
        """Performs auto-gyroscope calibration. Sensor should remain still while samples are taken. The gyroscope bias will be automatically placed into the bias part of the gyroscope calibration coefficient list."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setGyroscopeCalibrationCoefficients(self, matrix: list, biasX: float,
                                            biasY: float, biasZ: float,
                                            logicalID=0):
        """Sets the current gyroscope calibration parameters to the specified values. These consist of a bias which is added to the raw data vector and a matrix by which the value is multiplied. This setting can be saved to non-volatile flash memory using the Commit Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setCalibrationMode(self, mode: int, logicalID=0):
        """Sets the current calibration mode, which can be 0 for Bias or 1 for Scale-Bias. For more information, refer to the users manual in section 3.1.3 Additional Calibration. This setting can be saved to non-volatile flash memory using the Commit Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getCalibrationMode(self, logicalID=0):
        """Reads the current calibration mode, which can be 0 for Bias or 1 for Scale-Bias. For more information, refer to the users manual in section 3.1.3 Additional Calibration."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setLEDMode(self, mode: bool, logicalID=0):
        """Allows finer-grained control over the sensor LED. Accepts a single parameter that can be 0 for standard, which displays all standard LED status indicators or 1 for static, which displays only the LED color as specified by command 238. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getLEDMode(self, logicalID=0):
        """Returns the current sensor LED mode, which can be 0 for standard or 1 for static. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWiredResponseHeaderBitfield(self, logicalID=0):
        """Return the current wired response header bitfield. For more information, please refer to the users manual in section 4.4. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getFirmwareVersionString(self, logicalID=0):
        """Returns a string indicating the current firmware version. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def restoreFactorySettings(self, logicalID=0):
        """Return all non-volatile flash settings to their original, default settings. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def commitSettings(self, logicalID=0):
        """Commits all current sensor settings to non-volatile flash memory, which will persist after the sensor is powered off. For more information on which parameters can be stored in this manner, refer to the users manual in section 3.4 Sensor Settings. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def softwareReset(self, logicalID=0):
        """Resets the sensor."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setSleepMode(self, mode: bool, logicalID=0):
        """Sets the current sleep mode of the sensor. Supported sleep modes are 0 for NONE and 1 for IDLE. IDLE mode merely skips all filtering steps. NONE is the default state. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getSleepMode(self, logicalID=0):
        """Reads the current sleep mode of the sensor, which can be 0 for NONE or 1 for IDLE."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getHardwareVersionString(self, logicalID=0):
        """Returns a string indicating the current hardware version. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setUARTBaudRate(self, baudRate: int, logicalID=0):
        """Sets the baud rate of the physical UART. This setting does not need to be committed, but will not take effect until the sensor is reset. Valid baud rates are 1200, 2400, 4800, 9600, 19200, 28800, 38400, 57600, 115200 (default), 230400, 460800 and 921600. Note that this is only applicable for sensor types that have UART interfaces. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUARTBaudRate(self, logicalID=0):
        """Returns the baud rate of the physical UART. Note that this is only applicable for sensor types that have UART interfaces."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setUSBMode(self, mode: bool, logicalID=0):
        """Sets the communication mode for USB. Accepts one value that can be 0 for CDC (default) or 1 for FTDI. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUSBMode(self, logicalID=0):
        """Returns the current USB communication mode. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getSerialNumber(self, logicalID=0):
        """Returns the serial number, which will match the value etched onto the physical sensor."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setHaptics(self, duration: int, onTime: int, offTime: int, logicalID=0):
        """Sets the duty cycle and duration for haptics module. When the duration is set to 65535 the module will run continuously, when set to 0 it will turn off. All values are in centiseconds"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setLEDColor(self, red: float, green: float, blue: float, logicalID=0):
        """Sets the color of the LED on the sensor to the specified RGB color. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getLEDColor(self, logicalID=0):
        """Returns the color of the LED on the sensor. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setJoystickEnabled(self, enable: bool, logicalID=0):
        """Enable or disable streaming of joystick HID data for this sensor. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setMouseEnabled(self, enable: bool, logicalID=0):
        """Enable or disable streaming of mouse HID data for this sensor."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getJoystickEnabled(self, logicalID=0):
        """Read whether the sensor is currently streaming joystick HID data. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getMouseEnabled(self, logicalID=0):
        """Read whether the sensor is currently streaming mouse HID data. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setControlMode(self, controlClass: int, controlIndex: int,
                       handlerIndex: int, logicalID=0):
        """Sets the operation mode for one of the controls. The
        first parameter is the control class,which can be 0
        for Joystick Axis, 1 for Joystick Button, 2 for Mouse
        Axis or 3 for Mouse Button. There are two axes and
        eight buttons on the joystick and mouse. The
        second parameter, the control index, selects which
        one of these axes or buttons you would like to
        modify. The third parameter, the handler index,
        specifies which handler you want to take care of this
        control. These can be the following:
        Turn off this control: 255
        Axes:
        Global Axis: 0
        Screen Point: 1
        Buttons:
        Hardware Button: 0
        Orientation Button: 1
        Shake Button: 2"""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setControlData(self, controlClass: int, controlIndex: int,
                       handlerIndex: int, dataPoint: float, logicalID=0):
        """Sets parameters for the specified control's operation mode. The control classes and indices are the same as described in command 244. Each mode can have up to 10 data points associated with it. How many should be set and what they should be set to is entirely based on which mode is being used. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getControlMode(self, controlClass: int, controlIndex: int, logicalID=0):
        """Reads the handler index of this control's mode. The control classes and indices are the same as described in command 244."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getControlData(self, controlClass: int, controlIndex: int,
                       dataPointIndex: int, logicalID=0):
        """Reads the value of a certain parameter of the specified control's operation mode. The control classes and indices are the same as described in command 244."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getButtonState(self, logicalID=0):
        """Reads the current state of the sensor's physical buttons. This value returns a byte, where each bit represents the state of the sensor's physical buttons. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setMouseMode(self, mode: bool, logicalID=0):
        """Puts the mode in absolute or relative mode. This change will not take effect immediately and the sensor must be reset before the mouse will enter this mode. The only parameter can be 0 for absolute (default) or 1 for relative """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getMouseMode(self, logicalID=0):
        """Return the current mouse absolute/relative mode. Note that if the sensor has not been reset since it has been put in this mode, the mouse will not reflect this change yet, even though the command will."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setJoystickAndMouse(self, joystick: bool, mouse: bool, logicalID=0):
        """Sets whether the joystick and mouse are present or removed. The first parameter is for the joystick, and can be 0 for removed or 1 for present. The second parameter is for the mouse. If removed, they will not show up as devices on the target system at all. For these changes to take effect, the sensor driver may need to be reinstalled."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getJoystickAndMouse(self, logicalID=0):
        """Returns whether the joystick and mouse are present or removed. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def pauseStreaming(self):
        """Prevents the dongle from outputting wirelessly streamed data. This can be useful in the case that certain data responses are desired but an influx of streaming data prevents these from being read in a timely manner."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def resumeStreaming(self):
        """Resumes the dongle's outputting of wirelessly streamed data. This command has no effect if the sensor was not paused. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def broadcastSynchronizationPulse(self):
        """Sends out a timestamp synchronization broadcast message to all wireless sensors that are listening on the same channel and PanID as the dongle. The message will essentially set each receiving sensor's timestamp to the same timestamp as stored in the dongle. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getReceptionBitfield(self):
        """Returns a bitfield where bits corresponding to logical IDs will be set to 1 if the corresponding sensor has sent a wireless packet to the dongle since the last time this command was called. Calling this command will clear all bits to 0. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getSerialNumberAtLogicalID(self, logicalID: int):
        """Return the mapped serial number for the given logical ID. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setSerialNumberAtLogicalID(self, logicalID: int, serialNumber: int):
        """Set the mapped serial number given by the logical ID. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessChannelNoiseLevels(self):
        """Return the noise levels for each of the 16 wireless channels. A higher value corresponds to a noisier channel, which can significantly impact wireless reception and throughput. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setWirelessRetries(self, retries: int):
        """Set the number of times a dongle will attempt to retransmit a data request after timing out. Default value is 3. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessRetries(self):
        """Read the number of times a dongle will attempt to re-transmit a data request after timing out. Default value is 3."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getSignalStrength(self):
        """Returns a value indicating the reception strength of the most recently received packet. Higher values indicate a stronger link. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessResponseHeaderBitfield(self):
        """Return the current wireless response header bitfield."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessPanID_Dongle(self):
        """Return the current panID for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setWirelessPanID_Dongle(self, panID: int):
        """Set the current panID for this wireless sensor or dongle. Note that the panID for a wireless sensor can only be set via the USB connection. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to nonvolatile flash memory by calling the Commit Wireless Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessChannel_Dongle(self):
        """Read the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setWirelessChannel_Dongle(self, channel: int):
        """Set the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def commitWirelessSettings_Dongle(self):
        """Commits all current wireless settings to non-volatile flash memory, which will persist after the sensor is powered off. For more information on which parameters can be stored in this manner, refer to the users manual in section 3.4 Sensor Settings."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessAddress_Dongle(self):
        """Read the wireless hardware address for this sensor or dongle."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessPanID_Sensor(self, logicalID=0):
        """Return the current panID for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setWirelessPanID_Sensor(self, panID: int, logicalID=0):
        """Set the current panID for this wireless sensor or dongle. Note that the panID for a wireless sensor can only be set via the USB connection. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to nonvolatile flash memory by calling the Commit Wireless Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessChannel_Sensor(self, logicalID=0):
        """Read the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setWirelessChannel_Sensor(self, channel: int, logicalID=0):
        """Set the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def commitWirelessSettings_Sensor(self, logicalID=0):
        """Commits all current wireless settings to non-volatile flash memory, which will persist after the sensor is powered off. For more information on which parameters can be stored in this manner, refer to the users manual in section 3.4 Sensor Settings."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessAddress_Sensor(self, logicalID=0):
        """Read the wireless hardware address for this sensor or dongle."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setWirelessHIDUpdateRate(self, updateRate: int, logicalID=0):
        """Specify the interval at which HID information is requested by the dongle. The default and minimum value is 15ms in synchronous HID mode. In asynchronous HID mode, the minimum is 5ms. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessHIDUpdateRate(self, logicalID=0):
        """Return the interval at which HID information is requested by the dongle. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setWirelessHIDAsynchronousMode(self, mode: int, logicalID=0):
        """Sets the current wireless HID communication mode. Supplying a 0 makes wireless HID communication synchronous, while a 1 makes wireless HID asynchronous. For more information, refer to the users manual in section 3.3.4 Wireless Joystick/Mouse. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getWirelessHIDAsynchronousMode(self, logicalID=0):
        """Returns the current wireless HID communication mode, which can be a 0 for synchronous wireless HID or a 1 for asynchronous wireless HID."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setJoystickLogicalID(self, joystickID: int, logicalID=0):
        """Causes the sensor at the specified logical ID to return joystick HID data. Passing a -1 will disable wireless joystick data. For more information, refer to the users manual in section 3.3.4 Wireless Joystick/Mouse. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setMouseLogicalID(self, mouseID: int, logicalID=0):
        """Causes the sensor at the specified logical ID to return mouse HID data. Passing a -1 will disable wireless mouse data. For more information, refer to the users manual in section 3.3.4 Wireless Joystick/Mouse."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getJoystickLogicalID(self, logicalID=0):
        """Returns the current logical ID of the joystick-enabled sensor or -1 if none exists. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getMouseLogicalID(self, logicalID=0):
        """Returns the current logical ID of the mouse-enabled sensor or -1 if none exists. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getBatteryVoltage(self, logicalID=0):
        """Read the current battery level in volts. Note that this value will read as slightly higher than it actually is if it is read via a USB connection. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getBatteryPercentageRemaining(self, logicalID=0):
        """Read the current battery lifetime as a percentage of the total. Note that this value will read as slightly higher than it actually is if it is read via a USB connection."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getBatteryStatus(self, logicalID=0):
        """Returns a value indicating the current status of the battery, which can be a 3 to indicate that the battery is currently not charging, a 2 to indicate that the battery is charging and thus plugged in, or a 1 to indicate that the sensor is fully charged. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setPinMode(self, mode: int, pin: int, logicalID=0):
        """Sets the pin mode of the sensor. First parameter is mode, which will be 0 for off, 1 for pulse mode, 2 for level, 3 for SPI pulse and 4 for button. Second parameter is pin, which will be 0 for TXD(for button, also RXD) or 1 for MISO(for button, also MOSI). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getPinMode(self, logicalID=0):
        """Read the interrupt mode of the sensor. First parameter is mode, which will be 0 for off, 1 for pulse mode, 2 for level, 3 for SPI pulse and 4 for button. Second parameter is pin, which will be 0 for TXD(for button, also RXD) or 1 for MISO(for button, also MOSI)."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getInterruptStatus(self, logicalID=0):
        """Read the current interrupt status. This value will be 1 if the filter has updated since the last time the value was read or 0 otherwise."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setInterruptType(self, mode: int, pin: int, polarity: int, logicalID=0):
        """Sets up interrupt generation.

        If mode is 0, no generation will occur.
        If mode is 1, the interrupt generator will set the specified pin low for 5 microseconds when new data is available.
        If mode is 2, the interrupt generator will set the pin low until the interrupt status is read with command 18.

        The pin byte specifies which pin ois being used for interrupt generation.
        A value of 0 is for SDA, and 1 is for MISO.
        Note that the pin cannot be changed to SDA over I2C, and cannot be changed to MISO over SPI.

        If polarity is 0, then interrupts are generated by the interrupt pin being pulled low.
        If 1, the the pin will be pulled high. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getInterruptType(self, logicalID=0):
        """Read the current interrupt mode, pin, and polarity.
        If mode is 0, no generation will occurring.
        If mode is 1, the interrupt generator will set the specified pin low for 5 microseconds when new data is available.
        If mode is 2, the interrupt generator will set the pin low until the interrupt status is read with command 18.

        The pin byte specifies which pin ois being used for interrupt generation.
        A value of 0 is for SDA, and 1 is for MISO.

        If polarity is 0, then interrupts are generated by the interrupt pin being pulled low.
        If 1, the the pin will be pulled high. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setFilterParameters(self, kp: float, maxSmoothFactor: float,
                            minSmoothFactor: float, logicalID=0):
        """Sets the filter parameters: kp, max smooth factor, and min smooth factor. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getFilterParameters(self, logicalID=0):
        """Read out adjustable filter parameters: kp (float), max smooth factor (float), and min smooth factor (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setProtocolTimeout(self, timeout: int, logicalID=0):
        """Sets sets the timeout value for the command processing protocol in microseconds to the given float. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getProtocolTimeout(self, logicalID=0):
        """Returns the timeout value for the command processing protocol in microseconds (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setPedestrianTrackingEnabled(self, enabled: float, logicalID=0):
        """Enables/disables pedestrian tracking. Pass in 1.0 for on or 0.0 for off. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setSelectedStepIndex(self, index: float, logicalID=0):
        """Sets selected step index to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setRMin(self, rMin: float, logicalID=0):
        """Sets RMin to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setRMax(self, rMax: float, logicalID=0):
        """Sets RMax to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setDMin(self, dMin: float, logicalID=0):
        """Sets DMin to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setDMax(self, dMax: float, logicalID=0):
        """Sets DMax to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setAMin(self, aMin: float, logicalID=0):
        """Sets AMin to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setAMax(self, aMax: float, logicalID=0):
        """Sets AMax to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setStepDurationMin(self, stepDurMin: float, logicalID=0):
        """Sets minimum step duration to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setStepDurationMax(self, stepDurMax: float, logicalID=0):
        """Sets maximum step duration to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setStepStrideSlope(self, stepSlope: float, logicalID=0):
        """Sets step stride slope to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setStepStrideOffset(self, stepOffset: float, logicalID=0):
        """Sets step stride offset to the specified value (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setUnits(self, units: float, logicalID=0):
        """Sets units for distance. Pass in 0.0 for meters or 1.0 for feet. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def resetSteps(self, dummy: float, logicalID=0):
        """Resets step count and clears step data. Must pass in a dummy float. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getPedestrianTrackingEnabled(self, logicalID=0):
        """Returns whether or not pedestrian tracking is enabled. Will return 1.0 for on or 0.0 for off. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getSelectedStepIndex(self, logicalID=0):
        """Returns the currently selected step index (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getRMin(self, logicalID=0):
        """Returns the current RMin (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getRMax(self, logicalID=0):
        """Returns the current RMax (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getDMin(self, logicalID=0):
        """Returns the current DMin (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getDMax(self, logicalID=0):
        """Returns the current DMax (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAMin(self, logicalID=0):
        """Returns the current AMin (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getAMax(self, logicalID=0):
        """Returns the current AMax (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStepDurationMin(self, logicalID=0):
        """Returns the current minimum step duration (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStepDurationMax(self, logicalID=0):
        """Returns the current maximum step duration (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStepStrideSlope(self, logicalID=0):
        """Returns the current step stride slope (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStepStrideOffset(self, logicalID=0):
        """Returns the current step stride offset (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getUnits(self, logicalID=0):
        """Returns the current units for distance. Pass in 0.0 for meters or 1.0 for feet. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getHeadingInDegrees(self, logicalID=0):
        """Returns the current heading (float) in degrees. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStepBufferLength(self, logicalID=0):
        """Returns the number of steps recorded (float). """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getTotalDistanceTraveled(self, logicalID=0):
        """Returns the total distance traveled (float) in the units specified by setUnits. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getConfidenceValue(self, logicalID=0):
        """Returns the current confidence value. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getLatestStep(self, logicalID=0):
        """Returns the most recent step data. Its format is as follows:
        Index (float),
        Heading (float),
        X Step Distance (float),
        Y Step Distance (float),
        Step Distance (float),
        Step Time (float),
        Step Amplitude (float),
        Step Duty Cycle (float),
        Step Ratio (float),
        Altitude (float),
        Confidence (float),
        Altitude Offset (float).
        This function will return -1 if there is no step data. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getStepFromCurrentIndex(self, logicalID=0):
        """Returns the step data with the index specified in setSelectedStepIndex.
        Its format is as follows:
        Index (float),
        Heading (float),
        X Step Distance (float),
        Y Step Distance (float),
        Step Distance (float),
        Step Time (float),
        Step Amplitude (float),
        Step Duty Cycle (float),
        Step Ratio (float),
        Altitude (float),
        Confidence (float),
        Altitude Offset (float).
        This function will return -1 if there is no step data. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def formatAndInitializeSDCard(self, logicalID=0):
        """Erases the contents of the SD card."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def beginDataLoggingSession(self, logicalID=0):
        """Initiates a data logging section with the specified attributes as indicated in the provided data logging configuration file."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def endDataLoggingSession(self, logicalID=0):
        """Terminates the ongoing data logging session """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def setClockValues(self, month: int, day: int, year: int, hour: int,
                       minute: int, second: int, logicalID=0):
        """Sets the current time on the onboard real-time clock."""
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))

    def getClockValues(self, logicalID=0):
        """Returns the current time as read by the onboard real-time clock. """
        raise NotImplementedError(
            'This method is not available for {sensor} sensors'.format(
                sensor=self.sensorType))


commandList = [
    # Orientation Commands
    _Command("getTaredOrientation", 0, "4f", "", "*","Returns the filtered, tared orientation estimate in quaternion form"),
    _Command("getTaredOrientationAsEulerAngles", 1, "3f", "", "*","Returns the filtered, tared orientation estimate in euler angle form"),
    _Command("getTaredOrientationAsRotationMatrix", 2, "9f", "", "*","Returns the filtered, tared orientation estimate in rotation matrix form "),
    _Command("getTaredOrientationAsAxisAngles", 3, "3f f", "", "*","Returns the filtered, tared orientation estimate in axis-angle form"),
    _Command("getTaredOrientationAsTwoVector", 4, "3f 3f", "", "*","Returns the filtered, tared orientation estimate in two vector form, where the first vector refers to forward and the second refers to down."),
    _Command("getDifferenceQuaternion", 5, "4f", "", "*","Returns the difference between the measured orientation from last frame and this frame."),
    _Command("getUntaredOrientation", 6, "4f", "", "*","Returns the filtered, untared orientation estimate in quaternion form."),
    _Command("getUntaredOrientationAsEulerAngles", 7, "3f", "", "*","Returns the filtered, untared orientation estimate in euler angle form"),
    _Command("getUntaredOrientationAsRotationMatrix", 8, "9f", "", "*","Returns the filtered, untared orientation estimate in rotation matrix form"),
    _Command("getUntaredOrientationAsAxisAngles", 9, "3f f", "", "*","Returns the filtered, untared orientation estimate in axis-angle form"),
    _Command("getUntaredOrientationAsTwoVector", 10, "3f 3f", "", "*","Returns the filtered, untared orientation estimate in two vector form, where the first vector refers to north and the second refers to gravity"),
    _Command("getTaredTwoVectorInSensorFrame", 11, "3f 3f", "", "*","Returns the filtered, tared orientation estimate in two vector form, where the first vector refers to forward and the second refers to down. These vectors are given in the sensor reference frame and not the global reference frame. "),
    _Command("getUntaredTwoVectorInSensorFrame", 12, "3f 3f", "", "*","Returns the filtered, untared orientation estimate in two vector form, where the first vector refers to north and the second refers to gravity. These vectors are given in the sensor reference frame and not the global reference frame"),

    # Normalized Data Commands
    _Command("getAllNormalizedComponentSensorData", 32, "3f 3f 3f", "", "*","Returns the normalized gyro rate vector, accelerometer vector, and compass vector. Note that the gyro vector is in units of radians/sec, while the accelerometer and compass are unit-length vectors indicating the direction of gravity and north, respectively. These two vectors do not have any magnitude data associated with them. "),
    _Command("getNormalizedGyroRate", 33, "3f", "", "*","Returns the normalized gyro rate vector, which is in units of radians/sec."),
    _Command("getNormalizedAccelerometerVector", 34, "3f", "", "*","Returns the normalized accelerometer vector. Note that this is a unit-vector indicating the direction of gravity. This vector does not have any magnitude data associated with it. "),
    _Command("getNormalizedCompassVector", 35, "3f", "", "*","Returns the normalized compass vector. Note that this is a unit-vector indicating the direction of gravity. This vector does not have any magnitude data associated with it."),

    # Corrected Data Commands
    _Command("getAllCorrectedComponentSensorData", 37, "3f 3f 3f", "", "*","Returns the corrected gyro rate vector, accelerometer vector, and compass vector. Note that the gyro vector is in units of radians/sec, the accelerometer vector is in units of G, and the compass vector is in units of gauss"),
    _Command("getCorrectedGyroRate", 38, "3f", "", "*","Returns the corrected gyro rate vector, which is in units of radians/sec. Note that this result is the same data returned by the normalized gyro rate command."),
    _Command("getCorrectedAccelerometerVector", 39, "3f", "", "*","Returns the acceleration vector in units of G. Note that this acceleration will include the static component of acceleration due to gravity."),
    _Command("getCorrectedCompassVector", 40, "3f", "", "*","Returns the compass vector in units of gauss."),
    _Command("getCorrectedLinearAccelerationInGlobalSpace", 41, "3f", "", "*","Returns the linear acceleration of the device, which is the overall acceleration which has been orientation compensated and had the component of acceleration due to gravity removed. Uses the untared orientation."),
    _Command("correctRawGyroData", 48, "3f", "3f ,x:float,y:float,z:float", "*","Converts the supplied raw data gyroscope vector to its corrected data representation."),
    _Command("correctRawAccelData", 49, "3f", "3f ,x:float,y:float,z:float", "*","Converts the supplied raw data accelerometer vector to its corrected data representation. "),
    _Command("correctRawCompassData", 50, "3f", "3f ,x:float,y:float,z:float", "*","Converts the supplied raw data compass vector to its corrected data representation"),

    # Other Data Commands
    _Command("getTemperatureC", 43, "f", "", "*","Returns the temperature of the sensor in Celsius."),
    _Command("getTemperatureF", 44, "f", "", "*","Returns the temperature of the sensor in Fahrenheit"),
    _Command("getConfidenceFactor", 45, "f", "", "*-LX,Nano","Returns a value indicating how much the sensor is being moved at the moment. This value will return 1 if the sensor is completely stationary, and will return 0 if it is in motion. This command can also return values in between indicating how much motion the sensor is experiencing"),

    # Raw Data Commands
    _Command("getAllRawComponentSensorData", 64, "3f 3f 3f", "", "*","Returns the raw gyro rate vector, accelerometer vector and compass vector as read directly from the component sensors without any additional postprocessing. The range of values is dependent on the currently selected range for each respective sensor. "),
    _Command("getRawGyroRate", 65, "3f", "", "*","Returns the raw gyro rate vector as read directly from the gyroscope without any additional postprocessing. "),
    _Command("getRawAccelerometerVector", 66, "3f", "", "*","Returns the raw acceleration vector as read directly from the accelerometer without any additional postprocessing."),
    _Command("getRawCompassVector", 67, "3f", "", "*","Returns the raw compass vector as read directly from the compass without any additional postprocessing."),

    # Streaming Commands
    _Command("getStreamingSlots", 81, "8B", "", "*","Returns the current streaming slots configuration."),
    _Command("setStreamingTiming", 82, "", "III ,interval:int,duration:int,delay:int", "*","Configures timing information for a streaming session. All parameters are specified in microseconds. The first parameter is the interval, which specifies how often data will be output. A value of 0 means that data will be output at the end of every filter loop. Aside from 0, values lower than 1000 will be clamped to 1000. The second parameter is the duration, which specifies the length of the streaming session. If this value is set to 0xFFFFFFFF, streaming will continue indefinitely until it is stopped via command 0x56. The third parameter is the delay, which specifies a n amount of time the sensor will wait before outputting the first packet of streaming data. This setting can be saved to non-volatile flash memory using the Commit Settings command."),
    _Command("getStreamingTiming", 83, "III", "", "*","Returns the current streaming timing information."),
    _Command("updateCurrentTimestamp", 95, "", "I ,timestamp:int", "*","Set the current internal timestamp to the specified value."),

    # Configuration Write Commands
    _Command("setEulerAngleDecompositionOrder", 16, "", "B ,order:int", "*","Sets the current euler angle decomposition order, which determines how the angles returned from command 0x1 are decomposed from the full quaternion orientation. Possible values are 0x0 for XYZ, 0x1 for YZX, 0x2 for ZXY, 0x3 for ZYX, 0x4 for XZY or 0x5 for YXZ (default)."),
    _Command("offsetWithCurrentOrientation", 19, "", "", "*","Sets the offset orientation to be the same as the current filtered orientation."),
    _Command("resetBaseOffset", 20, "", "", "*","Sets the base offset to an identity quaternion."),
    _Command("offsetWithQuaternion", 21, "", "4f ,x:float,y:float,z:float,w:float", "*","Sets the offset orientation to be the same as the supplied orientation, which should be passed as a quaternion."),
    _Command("setBaseOffsetWithCurrentOrientation", 22, "", "", "*","Sets the base offset orientation to be the same as the current filtered orientation."),
    _Command("tareWithCurrentOrientation", 96, "", "", "*","Sets the tare orientation to be the same as the current filtered orientation."),
    _Command("tareWithQuaternion", 97, "", "4f ,x:float,y:float,z:float,w:float", "*","Sets the tare orientation to be the same as the supplied orientation, which should be passed as a quaternion."),
    _Command("tareWithRotationMatrix", 98, "", "9f ,matrix:list", "*","Sets the tare orientation to be the same as the supplied orientation, which should be passed as a rotation matrix. "),
    _Command("setStaticAccelerometerTrustValue", 99, "", "f ,trustValue:float", "*-Nano","Determines how trusted the accelerometer contribution is to the overall orientation estimation. Trust is 0 to 1, with 1 being fully trusted and 0 being not trusted at all."),
    _Command("setConfidenceAccelerometerTrustValues", 100, "", "ff ,minTrustValue:float,maxTrustValue:float", "*-Nano","Determines how trusted the accelerometer contribution is to the overall orientation estimation. Instead of using a single value, uses a minimum and maximum value. Trust values will be selected from this range depending on the confidence factor. This can have the effect of smoothing out the accelerometer when the sensor is in motion."),
    _Command("setStaticCompassTrustValue", 101, "", "f ,trustValue:float", "*-Nano","Determines how trusted the accelerometer contribution is to the overall orientation estimation. tribution is to the overall orientation estimation. Trust is 0 to 1, with 1 being fully trusted and 0 being not trusted at all."),
    _Command("setConfidenceCompassTrustValues", 102, "", "ff ,minTrustValue:float,maxTrustValue:float", "*-Nano","Determines how trusted the compass contribution is to the overall orientation estimation. Instead of using a single value, uses a minimum and maximum value. Trust values will be selected from this range depending on the confidence factor. This can have the effect of smoothing out the compass when the sensor is in motion. "),
    _Command("setReferenceVectorMode", 105, "", "B ,mode:int", "*","Set the current reference vector mode. Parameter can be 0 for single static mode, which uses a certain reference vector for the compass and another certain vector for the accelerometer at all times, 1 for single auto mode, which uses (0, -1, 0) as the reference vector for the accelerometer at all times and uses the average angle between the accelerometer and compass to calculate the compass reference vector once upon initiation of this mode, or 2 for single auto continuous mode, which works similarly to single auto mode, but calculates this continuously."),
    _Command("setOversampleRate", 106, "", "HHH ,gyroSamples:int,accelSamples:int,compassSamples:int", "*","Sets the number of times to sample each component sensor for each iteration of the filter. This can smooth out readings at the cost of responsiveness. If this value is set to 0 or 1, no oversampling occurs-otherwise, the number of samples per iteration depends on the specified parameter, up to a maximum of 65535. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("setGyroscopeEnabled", 107, "", "B ,enabled:bool", "*","Enable or disable gyroscope readings as inputs to the orientation estimation. Note that updated gyroscope readings are still accessible via commands. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("setAccelerometerEnabled", 108, "", "B ,enabled:bool", "*","Enable or disable accelerometer readings as inputs to the orientation estimation. Note that updated accelerometer readings are still accessible via commands. This setting can be saved to non-volatile flash memory using the Commit Settings command."),
    _Command("setCompassEnabled", 109, "", "B ,enabled:bool", "*","Enable or disable compass readings as inputs to the orientation estimation. Note that updated compass readings are still accessible via commands. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("setMIModeEnabled", 112, "", "B ,enabled:bool", "*-LX,Nano","Enables MI mode, which is meant to protect against some magnetic disturbances. See the Quick Start guide for more information. "),
    _Command("setMIModeParameters", 113, "", "7f ,params:list", "*-LX,Nano","Sets up parameters for MI mode. A description of these parameters will be added at a later date. "),
    _Command("beginMIModeFieldCalibration", 114, "", "", "*-LX,Nano","Begins the calibration process for MI mode. The sensor should be left in a magnetically unperturbed area for 3-4 seconds after this is called for calibration to succeed. "),
    _Command("setAxisDirections", 116, "", "B ,direction:int", "*","""Sets alternate directions for each of the natural axes
     of the sensor. The only parameter is a bitfield
     representing the possible combinations of axis
     swapping. The lower 3 bits specify where each of the
     natural axes appears:
     000: X: Right, Y: Up, Z: Forward (left-handed
     system, standard operation)
     001: X: Right, Y: Forward, Z: Up (right-handed
     system)
     002: X: Up, Y: Right, Z: Forward (right-handed
     system)
     003: X: Forward, Y: Right, Z: Up (left-handed
     system)
     004: X: Up, Y: Forward, Z: Right (left-handed
     system)
     005: X: Forward, Y: Up, Z: Right (right-handed
     system)
     (For example, using X: Right, Y: Forward, Z: Up
     means that any values that appear on the positive
     vertical(Up) axis of the sensor will be the third(Z)
     component of any vectors and will have a positive
     sign, and any that appear on the negative vertical
     axis will be the Z component and will have a negative
     sign.)
     The 3 bits above those are used to indicate which
     axes, if any, should be reversed. If it is cleared, the
     axis will be pointing in the positive direction.
     Otherwise, the axis will be pointed in the negative
     direction. (Note: These are applied to the axes after
     the previous conversion takes place).
     Bit 4: Positive/Negative Z (Third resulting component)
     Bit 5: Positive/Negative Y (Second resulting
     component)
     Bit 6: Positive/Negative X (First resulting component)
     Note that for each negation that is applied, the
     handedness of the system flips. So, if X and Z are
     negative and you are using a left-handed system, the
     system will still be left handed, but if only X is
     negated, the system will become right-handed."""),
    _Command("setRunningAveragePercent", 117, "",
            "ffff ,gyroPercent:float,accelPercent:float,compassPercent:float,orientationPercent:float", "*","""Sets what percentage of running average to use on a
     component sensor, or on the sensor's orientation.
     This is computed as follows:
     total_value = total_value* percent
     total_value = total_value + current_value * (1 -
     percent)
     current_value = total_value
     If the percentage is 0, the running average will be
     shut off completely. Maximum value is 1. This
     setting can be saved to non-volatile flash memory
     using the Commit Settings command."""),
    _Command("setCompassReferenceVector", 118, "", "3f ,x:float,y:float,z:float", "*","Sets the static compass reference vector for Single Reference Mode. "),
    _Command("setAccelerometerReferenceVector", 119, "", "3f ,x:float,y:float,z:float", "*","Sets the static accelerometer reference vector for Single Reference Mode. "),
    _Command("resetFilter", 120, "", "", "*-LX,Nano","Resets the state of the currently selected filter."),
    _Command("setAccelerometerRange", 121, "", "B ,range:int", "*","Only parameter is the new accelerometer range, which can be 0 for 2g (Default range), which can be 1 for 4g, or 2 for 8g. Higher ranges can detect and report larger accelerations, but are not as accurate for smaller accelerations. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("setFilterMode", 123, "", "B ,mode:int", "*-LX,Nano","Used to disable the orientation filter or set the orientation filter mode. Changing this parameter can be useful for tuning filter-performance versus orientation-update rates. Passing in a parameter of 0 places the sensor into IMU mode, a 1 places the sensor into Kalman Filtered Mode (Default mode), a 2 places the sensor into Q-COMP Filter Mode, a 3 places the sensor into Q-GRAD Filter Mode. More information can be found in the users manual in section 3.1.5. This setting can be saved to non-volatile flash memory using the Commit Settings command."),
    _Command("setRunningAverageMode", 124, "", "B ,mode:int", "*-LX,Nano","Used to further smooth out the orientation at the cost of higher latency. Passing in a parameter of 0 places the sensor into a static running average mode, a 1 places the sensor into a confidencebased running average mode, which changes the running average factor based upon the confidence factor, which is a measure of how 'in motion' the sensor is. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("setGyroscopeRange", 125, "", "B ,range:int", "*","Only parameter is the new gyroscope range, which can be 0 for 250 DPS, 1 for 500 DPS, or 2 for 2000 DPS (Default range). Higher ranges can detect and report larger angular rates, but are not as accurate for smaller angular rates. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("setCompassRange", 126, "", "B ,range:int", "*","Only parameter is the new compass range, which can be 0 for 0.88G, 1 for 1.3G (Default range), 2 for 1.9G, 3 for 2.5G, 4 for 4.0G, 5 for 4.7G, 6 for 5.6G, or 7 for 8.1G. Higher ranges can detect and report larger magnetic field strengths but are not as accurate for smaller magnetic field strengths. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),

    # Configuration Read Commands
    _Command("getTareOrientationAsQuaternion", 128, "4f", "", "*","Returns the current tare orientation as a quaternion. "),
    _Command("getTareOrientationAsRotationMatrix", 129, "9f", "", "*","Returns the current tare orientation as a rotation matrix."),
    _Command("getAccelerometerTrustValues", 130, "ff", "", "*-LX,Nano","Returns the current accelerometer min and max trust values. If static trust values were set, both of these will be the same. "),
    _Command("getCompassTrustValues", 131, "ff", "", "*-LX,Nano","Returns the current compass min and max trust values. If static trust values were set, both of these will be the same."),
    _Command("getCurrentUpdateRate", 132, "I", "", "*","Reads the amount of time taken by the last filter update step. "),
    _Command("getCompassReferenceVector", 133, "3f", "", "*","Reads the current compass reference vector. Note that this is not valid if the sensor is in Multi Reference Vector mode. "),
    _Command("getAccelerometerReferenceVector", 134, "3f", "", "*","Reads the current compass reference vector. Note that this is not valid if the sensor is in Multi Reference Vector mode. "),
    _Command("getReferenceVectorMode", 135, "B", "", "*","Reads the current reference vector mode. Return value can be 0 for single static, 1 for single auto, or 2 for single auto continuous. "),
    _Command("getMIModeEnabled", 136, "B", "", "*-LX,Nano","Returns a value indicating whether MI mode is currently on or not: 0 for off, 1 for on."),
    _Command("getMIModeParameters", 137, "7f", "", "*-LX,Nano","Returns the MI mode parameter list. A description of these will be added at a later date. "),
    _Command("getGyroscopeEnabledState", 140, "B", "", "*","Returns a value indicating whether the gyroscope contribution is currently part of the orientation estimate: 0 for off, 1 for on. "),
    _Command("getAccelerometerEnabledState", 141, "B", "", "*","Returns a value indicating whether the accelerometer contribution is currently part of the orientation estimate: 0 for off, 1 for on. "),
    _Command("getCompassEnabledState", 142, "B", "", "*","Returns a value indicating whether the compass contribution is currently part of the orientation estimate: 0 for off, 1 for on. "),
    _Command("getAxisDirection", 143, "B", "", "*","Returns a value indicating the current axis direction setup. For more information on the meaning of this value, please refer to the Set Axis Direction command (116). "),
    _Command("getOverSampleRate", 144, "HHH", "", "*","Returns values indicating how many times each component sensor is sampled before being stored as raw data. A value of 1 indicates that no oversampling is taking place, while a value that is higher indicates the number of samples per component sensor per filter update step. "),
    _Command("getRunningAveragePercent", 145, "ffff", "", "*","Returns the running average percent value for each component sensor and for the orientation. The value indicates what portion of the previous reading is kept and incorporated into the new reading."),
    _Command("getAccelerometerRange", 148, "B", "", "*","Return the current accelerometer measurement range, which can be a 0 for 2g, 1 for 4g or a 2 for 8g. "),
    _Command("getFilterMode", 152, "B", "", "*-LX,Nano","Returns the current filter mode, which can be 0 for IMU mode, 1 for Kalman, 2 for Q-COMP, or 3 for QGRAD. For more information, please refer to the Set Filter Mode command (123). "),
    _Command("getRunningAverageMode", 153, "B", "", "*-LX,Nano","Reads the selected mode for the running average, which can be 0 for normal or 1 for confidence."),
    _Command("getGyroscopeRange", 154, "B", "", "*","Reads the current gyroscope measurement range, which can be 0 for 250 DPS, 1 for 500 DPS or 2 for 2000 DPS. "),
    _Command("getCompassRange", 155, "B", "", "*","Reads the current compass measurement range, which can be 0 for 0.88G, 1 for 1.3G, 2 for 1.9G, 3 for 2.5G, 4 for 4.0G, 5 for 4.7G, 6 for 5.6G or 7 for 8.1G. "),
    _Command("getEulerAngleDecompositionOrder", 156, "B", "", "*","Reads the current euler angle decomposition order."),
    _Command("getOffsetOrientationAsQuaternion", 159, "4f", "", "*","Returns the current offset orientation as a quaternion."),

    # Calibration Commands
    _Command("setCompassCalibrationCoefficients", 160, "", "9f3f ,matrix:list,biasX:float,biasY:float,biasZ:float",
            "*","Sets the current compass calibration parameters to the specified values. These consist of a bias which is added to the raw data vector and a matrix by which the value is multiplied. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("setAccelerometerCalibrationCoefficients", 161, "",
            "9f3f ,matrix:list,biasX:float,biasY:float,biasZ:float", "*","Sets the current accelerometer calibration parameters to the specified values. These consist of a bias which is added to the raw data vector and a matrix by which the value is multiplied. This setting can be saved to non-volatile flash memory using the Commit Settings command."),
    _Command("getCompassCalibrationCoefficients", 162, "9f 3f", "", "*","Return the current compass calibration parameters."),
    _Command("getAccelerometerCalibrationCoefficients", 163, "9f 3f", "", "*","Return the current accelerometer calibration parameters. "),
    _Command("getGyroscopeCalibrationCoefficients", 164, "9f 3f", "", "*","Return the current gyroscope calibration parameters."),
    _Command("beginGyroscopeAutoCalibration", 165, "", "", "*","Performs auto-gyroscope calibration. Sensor should remain still while samples are taken. The gyroscope bias will be automatically placed into the bias part of the gyroscope calibration coefficient list."),
    _Command("setGyroscopeCalibrationCoefficients", 166, "", "9f3f ,matrix:list,biasX:float,biasY:float,biasZ:float",
            "*","Sets the current gyroscope calibration parameters to the specified values. These consist of a bias which is added to the raw data vector and a matrix by which the value is multiplied. This setting can be saved to non-volatile flash memory using the Commit Settings command."),
    _Command("setCalibrationMode", 169, "", "B ,mode:int", "*-LX,Nano","Sets the current calibration mode, which can be 0 for Bias or 1 for Scale-Bias. For more information, refer to the users manual in section 3.1.3 Additional Calibration. This setting can be saved to non-volatile flash memory using the Commit Settings command. "),
    _Command("getCalibrationMode", 170, "B", "", "*-LX,Nano","Reads the current calibration mode, which can be 0 for Bias or 1 for Scale-Bias. For more information, refer to the users manual in section 3.1.3 Additional Calibration."),

    # System Commands
    _Command("setLEDMode", 196, "", "B ,mode:bool", "*-LX,Nano","Allows finer-grained control over the sensor LED. Accepts a single parameter that can be 0 for standard, which displays all standard LED status indicators or 1 for static, which displays only the LED color as specified by command 238. "),
    _Command("getLEDMode", 200, "B", "", "*-LX,Nano","Returns the current sensor LED mode, which can be 0 for standard or 1 for static. "),
    _Command("getWiredResponseHeaderBitfield", 222, "I", "", "*","Return the current wired response header bitfield. For more information, please refer to the users manual in section 4.4. "),
    _Command("getFirmwareVersionString", 223, "12s", "", "*","Returns a string indicating the current firmware version. "),
    _Command("restoreFactorySettings", 224, "", "", "*","Return all non-volatile flash settings to their original, default settings. "),
    _Command("commitSettings", 225, "", "", "*","Commits all current sensor settings to non-volatile flash memory, which will persist after the sensor is powered off. For more information on which parameters can be stored in this manner, refer to the users manual in section 3.4 Sensor Settings. "),
    _Command("softwareReset", 226, "", "", "*","Resets the sensor."),
    _Command("setSleepMode", 227, "", "B ,mode:bool", "*","Sets the current sleep mode of the sensor. Supported sleep modes are 0 for NONE and 1 for IDLE. IDLE mode merely skips all filtering steps. NONE is the default state. "),
    _Command("getSleepMode", 228, "B", "", "*","Reads the current sleep mode of the sensor, which can be 0 for NONE or 1 for IDLE."),
    _Command("getHardwareVersionString", 230, "32s", "", "*","Returns a string indicating the current hardware version. "),
    _Command("setUARTBaudRate", 231, "", "I ,baudRate:int", "*","Sets the baud rate of the physical UART. This setting does not need to be committed, but will not take effect until the sensor is reset. Valid baud rates are 1200, 2400, 4800, 9600, 19200, 28800, 38400, 57600, 115200 (default), 230400, 460800 and 921600. Note that this is only applicable for sensor types that have UART interfaces. "),
    _Command("getUARTBaudRate", 232, "I", "", "*","Returns the baud rate of the physical UART. Note that this is only applicable for sensor types that have UART interfaces."),
    _Command("setUSBMode", 233, "", "B ,mode:bool", "*-LX,Nano","Sets the communication mode for USB. Accepts one value that can be 0 for CDC (default) or 1 for FTDI. "),
    _Command("getUSBMode", 234, "B", "", "*-LX,Nano","Returns the current USB communication mode. "),
    _Command("getSerialNumber", 237, "I", "", "*","Returns the serial number, which will match the value etched onto the physical sensor."),
    _Command("setHaptics", 204, "", "HBB ,duration:int,onTime:int,offTime:int", "*-LX,Nano","Sets the duty cycle and duration for haptics module. When the duration is set to 65535 the module will run continuously, when set to 0 it will turn off. All values are in centiseconds"),
    _Command("setLEDColor", 238, "", "fff ,red:float,green:float,blue:float", "*-LX,Nano","Sets the color of the LED on the sensor to the specified RGB color. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."),
    _Command("getLEDColor", 239, "fff", "", "*-LX,Nano","Returns the color of the LED on the sensor. "),

    # Wired HID Commands
    _Command("setJoystickEnabled", 240, "", "B ,enable:bool", "*-LX,Nano","Enable or disable streaming of joystick HID data for this sensor. "),
    _Command("setMouseEnabled", 241, "", "B ,enable:bool", "*-LX,Nano","Enable or disable streaming of mouse HID data for this sensor."),
    _Command("getJoystickEnabled", 242, "B", "", "*-LX,Nano","Read whether the sensor is currently streaming joystick HID data. "),
    _Command("getMouseEnabled", 243, "B", "", "*-LX,Nano","Read whether the sensor is currently streaming mouse HID data. "),

    # General HID Commands
    _Command("setControlMode", 244, "", "BBB ,controlClass:int,controlIndex:int,handlerIndex:int", "*-LX,Nano","""Sets the operation mode for one of the controls. The
    first parameter is the control class,which can be 0
    for Joystick Axis, 1 for Joystick Button, 2 for Mouse
    Axis or 3 for Mouse Button. There are two axes and
    eight buttons on the joystick and mouse. The
    second parameter, the control index, selects which
    one of these axes or buttons you would like to
    modify. The third parameter, the handler index,
    specifies which handler you want to take care of this
    control. These can be the following:
    Turn off this control: 255
    Axes:
    Global Axis: 0
    Screen Point: 1
    Buttons:
    Hardware Button: 0
    Orientation Button: 1
    Shake Button: 2"""),
    _Command("setControlData", 245, "", "BBBf ,controlClass:int,controlIndex:int,handlerIndex:int,dataPoint:float",
            "*-LX,Nano","Sets parameters for the specified control's operation mode. The control classes and indices are the same as described in command 244. Each mode can have up to 10 data points associated with it. How many should be set and what they should be set to is entirely based on which mode is being used. "),
    _Command("getControlMode", 246, "B", "BB ,controlClass:int,controlIndex:int", "*-LX,Nano","Reads the handler index of this control's mode. The control classes and indices are the same as described in command 244."),
    _Command("getControlData", 247, "f", "BBB ,controlClass:int,controlIndex:int,dataPointIndex:int", "*-LX,Nano","Reads the value of a certain parameter of the specified control's operation mode. The control classes and indices are the same as described in command 244."),
    _Command("getButtonState", 250, "B", "", "*-LX,Nano","Reads the current state of the sensor's physical buttons. This value returns a byte, where each bit represents the state of the sensor's physical buttons. "),
    _Command("setMouseMode", 251, "", "B ,mode:bool", "*-LX,Nano","Puts the mode in absolute or relative mode. This change will not take effect immediately and the sensor must be reset before the mouse will enter this mode. The only parameter can be 0 for absolute (default) or 1 for relative "),
    _Command("getMouseMode", 252, "B", "", "*-LX,Nano","Return the current mouse absolute/relative mode. Note that if the sensor has not been reset since it has been put in this mode, the mouse will not reflect this change yet, even though the command will."),
    _Command("setJoystickAndMouse", 253, "", "BB ,joystick:bool,mouse:bool", "*-LX,Nano","Sets whether the joystick and mouse are present or removed. The first parameter is for the joystick, and can be 0 for removed or 1 for present. The second parameter is for the mouse. If removed, they will not show up as devices on the target system at all. For these changes to take effect, the sensor driver may need to be reinstalled."),
    _Command("getJoystickAndMouse", 254, "BB", "", "*-LX,Nano","Returns whether the joystick and mouse are present or removed. "),

    # Dongle Commands
    _Command("pauseStreaming", 85, "", "", "DNG","Prevents the dongle from outputting wirelessly streamed data. This can be useful in the case that certain data responses are desired but an influx of streaming data prevents these from being read in a timely manner."),
    _Command("resumeStreaming", 86, "", "", "DNG","Resumes the dongle's outputting of wirelessly streamed data. This command has no effect if the sensor was not paused. "),
    _Command("broadcastSynchronizationPulse", 182, "", "", "DNG","Sends out a timestamp synchronization broadcast message to all wireless sensors that are listening on the same channel and PanID as the dongle. The message will essentially set each receiving sensor's timestamp to the same timestamp as stored in the dongle. "),
    _Command("getReceptionBitfield", 183, "H", "", "DNG","Returns a bitfield where bits corresponding to logical IDs will be set to 1 if the corresponding sensor has sent a wireless packet to the dongle since the last time this command was called. Calling this command will clear all bits to 0. "),
    _Command("getSerialNumberAtLogicalID", 208, "I", "B ,logicalID:int", "DNG","Return the mapped serial number for the given logical ID. "),
    _Command("setSerialNumberAtLogicalID", 209, "", "B ,logicalID:int,serialNumber:int", "DNG","Set the mapped serial number given by the logical ID. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."),
    _Command("getWirelessChannelNoiseLevels", 210, "16B", "", "DNG","Return the noise levels for each of the 16 wireless channels. A higher value corresponds to a noisier channel, which can significantly impact wireless reception and throughput. "),
    _Command("setWirelessRetries", 211, "", "B ,retries:int", "DNG","Set the number of times a dongle will attempt to retransmit a data request after timing out. Default value is 3. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command. "),
    _Command("getWirelessRetries", 212, "B", "", "DNG","Read the number of times a dongle will attempt to re-transmit a data request after timing out. Default value is 3."),
    _Command("getSignalStrength", 214, "B", "", "DNG","Returns a value indicating the reception strength of the most recently received packet. Higher values indicate a stronger link. "),
    _Command("getWirelessResponseHeaderBitfield", 220, "I", "", "DNG","Return the current wireless response header bitfield."),

    _Command("getWirelessPanID_Dongle", 192, "H", "", "DNG","Return the current panID for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology."),
    _Command("setWirelessPanID_Dongle", 193, "", "H ,panID:int", "DNG","Set the current panID for this wireless sensor or dongle. Note that the panID for a wireless sensor can only be set via the USB connection. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to nonvolatile flash memory by calling the Commit Wireless Settings command. "),
    _Command("getWirelessChannel_Dongle", 194, "B", "", "DNG","Read the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. "),
    _Command("setWirelessChannel_Dongle", 195, "", "B ,channel:int", "DNG","Set the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."),
    _Command("commitWirelessSettings_Dongle", 197, "", "", "DNG","Commits all current wireless settings to non-volatile flash memory, which will persist after the sensor is powered off. For more information on which parameters can be stored in this manner, refer to the users manual in section 3.4 Sensor Settings."),
    _Command("getWirelessAddress_Dongle", 198, "H", "", "DNG","Read the wireless hardware address for this sensor or dongle."),

    # Wireless Commands
    _Command("getWirelessPanID_Sensor", 192, "H", "", "WL","Return the current panID for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology."),
    _Command("setWirelessPanID_Sensor", 193, "", "H ,panID:int", "WL","Set the current panID for this wireless sensor or dongle. Note that the panID for a wireless sensor can only be set via the USB connection. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to nonvolatile flash memory by calling the Commit Wireless Settings command. "),
    _Command("getWirelessChannel_Sensor", 194, "B", "", "WL","Read the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. "),
    _Command("setWirelessChannel_Sensor", 195, "", "B ,channel:int", "WL","Set the current channel for this wireless sensor or dongle. For more information, refer to the users manual in section 2.9 Wireless Terminology. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."),
    _Command("commitWirelessSettings_Sensor", 197, "", "", "WL","Commits all current wireless settings to non-volatile flash memory, which will persist after the sensor is powered off. For more information on which parameters can be stored in this manner, refer to the users manual in section 3.4 Sensor Settings."),
    _Command("getWirelessAddress_Sensor", 198, "H", "", "WL","Read the wireless hardware address for this sensor or dongle."),

    # Wireless HID Commands
    _Command("setWirelessHIDUpdateRate", 215, "", "B ,updateRate:int", "WL","Specify the interval at which HID information is requested by the dongle. The default and minimum value is 15ms in synchronous HID mode. In asynchronous HID mode, the minimum is 5ms. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command."),
    _Command("getWirelessHIDUpdateRate", 216, "B", "", "WL","Return the interval at which HID information is requested by the dongle. "),
    _Command("setWirelessHIDAsynchronousMode", 217, "", "B ,mode:int", "WL","Sets the current wireless HID communication mode. Supplying a 0 makes wireless HID communication synchronous, while a 1 makes wireless HID asynchronous. For more information, refer to the users manual in section 3.3.4 Wireless Joystick/Mouse. This setting can be committed to non-volatile flash memory by calling the Commit Wireless Settings command. "),
    _Command("getWirelessHIDAsynchronousMode", 218, "B", "", "WL","Returns the current wireless HID communication mode, which can be a 0 for synchronous wireless HID or a 1 for asynchronous wireless HID."),
    _Command("setJoystickLogicalID", 240, "", "b ,joystickID:int", "WL","Causes the sensor at the specified logical ID to return joystick HID data. Passing a -1 will disable wireless joystick data. For more information, refer to the users manual in section 3.3.4 Wireless Joystick/Mouse. "),
    _Command("setMouseLogicalID", 241, "", "b ,mouseID:int", "WL","Causes the sensor at the specified logical ID to return mouse HID data. Passing a -1 will disable wireless mouse data. For more information, refer to the users manual in section 3.3.4 Wireless Joystick/Mouse."),
    _Command("getJoystickLogicalID", 242, "b", "", "WL","Returns the current logical ID of the joystick-enabled sensor or -1 if none exists. "),
    _Command("getMouseLogicalID", 243, "b", "", "WL","Returns the current logical ID of the mouse-enabled sensor or -1 if none exists. "),

    # Battery Commands
    _Command("getBatteryVoltage", 201, "f", "", "*-LX,Nano","Read the current battery level in volts. Note that this value will read as slightly higher than it actually is if it is read via a USB connection. "),
    _Command("getBatteryPercentageRemaining", 202, "B", "", "*-LX,Nano","Read the current battery lifetime as a percentage of the total. Note that this value will read as slightly higher than it actually is if it is read via a USB connection."),
    _Command("getBatteryStatus", 203, "B", "", "*-LX,Nano","Returns a value indicating the current status of the battery, which can be a 3 to indicate that the battery is currently not charging, a 2 to indicate that the battery is charging and thus plugged in, or a 1 to indicate that the sensor is fully charged. "),

    # Embedded Commands
    _Command("setPinMode", 29, "", "BB ,mode:int,pin:int", "EM","Sets the pin mode of the sensor. First parameter is mode, which will be 0 for off, 1 for pulse mode, 2 for level, 3 for SPI pulse and 4 for button. Second parameter is pin, which will be 0 for TXD(for button, also RXD) or 1 for MISO(for button, also MOSI). "),
    _Command("getPinMode", 30, "BB", "", "EM","Read the interrupt mode of the sensor. First parameter is mode, which will be 0 for off, 1 for pulse mode, 2 for level, 3 for SPI pulse and 4 for button. Second parameter is pin, which will be 0 for TXD(for button, also RXD) or 1 for MISO(for button, also MOSI)."),
    _Command("getInterruptStatus", 31, "B", "", "EM","Read the current interrupt status. This value will be 1 if the filter has updated since the last time the value was read or 0 otherwise."),

    # LX, Nano Commands
    _Command("setInterruptType", 29, "", "BBB ,mode:int,pin:int,polarity:int", "LX,Nano", """Sets up interrupt generation.
    
    If mode is 0, no generation will occur. 
    If mode is 1, the interrupt generator will set the specified pin low for 5 microseconds when new data is available. 
    If mode is 2, the interrupt generator will set the pin low until the interrupt status is read with command 18.
    
    The pin byte specifies which pin ois being used for interrupt generation.
    A value of 0 is for SDA, and 1 is for MISO.
    Note that the pin cannot be changed to SDA over I2C, and cannot be changed to MISO over SPI.
    
    If polarity is 0, then interrupts are generated by the interrupt pin being pulled low.
    If 1, the the pin will be pulled high. """),
    _Command("getInterruptType", 30, "BBB", "", "LX,Nano", """Read the current interrupt mode, pin, and polarity.
    If mode is 0, no generation will occurring.
    If mode is 1, the interrupt generator will set the specified pin low for 5 microseconds when new data is available. 
    If mode is 2, the interrupt generator will set the pin low until the interrupt status is read with command 18.
     
    The pin byte specifies which pin ois being used for interrupt generation.
    A value of 0 is for SDA, and 1 is for MISO.
     
    If polarity is 0, then interrupts are generated by the interrupt pin being pulled low.
    If 1, the the pin will be pulled high. """),
    _Command("getInterruptStatus", 31, "B", "", "LX,Nano", "Read the current interrupt state. If there is new data since the last orientation read (commands 0-4 and 6-10), the value will be a 1, otherwise it will be 0. Calling the command while interrupts are in level mode will cause the interrupt pin to turn high. "),
    _Command("setFilterParameters", 110, "", "fff ,kp:float,maxSmoothFactor:float,minSmoothFactor:float", "LX,Nano", "Sets the filter parameters: kp, max smooth factor, and min smooth factor. "),
    _Command("getFilterParameters", 111, "fff", "", "LX,Nano", "Read out adjustable filter parameters: kp (float), max smooth factor (float), and min smooth factor (float). "),
    _Command("setProtocolTimeout", 244, "", "Q ,timeout:int", "Nano", "Sets sets the timeout value for the command processing protocol in microseconds to the given float. "),
    _Command("setProtocolTimeout", 244, "", "i ,timeout:int", "LX", "Sets sets the timeout value for the command processing protocol in microseconds to the given float. "),
    _Command("getProtocolTimeout", 245, "Q", "", "Nano", "Returns the timeout value for the command processing protocol in microseconds (float). "),
    _Command("getProtocolTimeout", 245, "i", "", "LX", "Returns the timeout value for the command processing protocol in microseconds (float). "),

    # Chain-Streaming Commands
    # _Command("getLogicalID", 208, "B", "", "LX,Nano", "Returns logical ID of this sensor within a chain of sensors. "),
    # _Command("setLogicalID", 209, "", "BI ,logicalID:int,serialNumber:int", "LX,Nano", "Sets logical ID of this sensor given a logical ID (byte) and a serial number (unsigned int). Should be used to designate the sensor's position in a chain. "),
    # _Command("setChainStreamingSettings", 210, "", "BBB ,streamingCommand:int,numPackets:int,numSensors:int", "LX,Nano", "Sets the command to be streamed to the sensor (byte), the number of packets to be output by the sensor (byte), and the total number of sensors in the chain (byte). If the number of packets is set to 0, then the sensor will stream until stoppend by command 0x56. "),
    # _Command("setChainStreamingDelay", 211, "", "I ,delay:int", "LX,Nano", "Sets the delay between output packets from each sensor to the given unsigned integer. "),
    # _Command("startChainStreaming", 212, "", "B ,mode:int", "LX,Nano", "Starts streaming data from all sensors in the chain. Data is produced at intervals specified by command 0xD3. This command requires a Mode byte that acts either as a start command or a synchronization command: 1 loads all streaming parameters and begins streaming, and 0 continues to operate with most recent settings and synchronizes the timers of all streaming devices. "),
    # _Command("getChainStreamingParameters", 213, "BBBI", "", "LX,Nano", "Returns the set streaming command (byte), the number of output packets (byte), the total number of sensors in the chain (byte), and the delay between each output packet (unsigned int). "),

    # Pedestrian-Tracking Commands
    _Command("setPedestrianTrackingEnabled", 52, "", "f ,enabled:float", "*-Nano", "Enables/disables pedestrian tracking. Pass in 1.0 for on or 0.0 for off. ", 0),
    _Command("setSelectedStepIndex", 52, "", "f ,index:float", "*-Nano", "Sets selected step index to the specified value (float). ", 1),
    _Command("setRMin", 52, "", "f ,rMin:float", "*-Nano", "Sets RMin to the specified value (float). ", 2),
    _Command("setRMax", 52, "", "f ,rMax:float", "*-Nano", "Sets RMax to the specified value (float). ", 3),
    _Command("setDMin", 52, "", "f ,dMin:float", "*-Nano", "Sets DMin to the specified value (float). ", 4),
    _Command("setDMax", 52, "", "f ,dMax:float", "*-Nano", "Sets DMax to the specified value (float). ", 5),
    _Command("setAMin", 52, "", "f ,aMin:float", "*-Nano", "Sets AMin to the specified value (float). ", 6),
    _Command("setAMax", 52, "", "f ,aMax:float", "*-Nano", "Sets AMax to the specified value (float). ", 7),
    _Command("setStepDurationMin", 52, "", "f ,stepDurMin:float", "*-Nano", "Sets minimum step duration to the specified value (float). ", 8),
    _Command("setStepDurationMax", 52, "", "f ,stepDurMax:float", "*-Nano", "Sets maximum step duration to the specified value (float). ", 9),
    _Command("setStepStrideSlope", 52, "", "f ,stepSlope:float", "*-Nano", "Sets step stride slope to the specified value (float). ", 10),
    _Command("setStepStrideOffset", 52, "", "f ,stepOffset:float", "*-Nano", "Sets step stride offset to the specified value (float). ", 11),
    _Command("setUnits", 52, "", "f ,units:float", "*-Nano", "Sets units for distance. Pass in 0.0 for meters or 1.0 for feet. ", 12),
    _Command("resetSteps", 52, "", "f ,dummy:float", "*-Nano", "Resets step count and clears step data. Must pass in a dummy float. ", 15),

    _Command("getPedestrianTrackingEnabled", 53, "f", "", "*-Nano", "Returns whether or not pedestrian tracking is enabled. Will return 1.0 for on or 0.0 for off. ", 0),
    _Command("getSelectedStepIndex", 53, "f", "", "*-Nano", "Returns the currently selected step index (float). ", 1),
    _Command("getRMin", 53, "f", "", "*-Nano", "Returns the current RMin (float). ", 2),
    _Command("getRMax", 53, "f", "", "*-Nano", "Returns the current RMax (float). ", 3),
    _Command("getDMin", 53, "f", "", "*-Nano", "Returns the current DMin (float). ", 4),
    _Command("getDMax", 53, "f", "", "*-Nano", "Returns the current DMax (float). ", 5),
    _Command("getAMin", 53, "f", "", "*-Nano", "Returns the current AMin (float). ", 6),
    _Command("getAMax", 53, "f", "", "*-Nano", "Returns the current AMax (float). ", 7),
    _Command("getStepDurationMin", 53, "f", "", "*-Nano", "Returns the current minimum step duration (float). ", 8),
    _Command("getStepDurationMax", 53, "f", "", "*-Nano", "Returns the current maximum step duration (float). ", 9),
    _Command("getStepStrideSlope", 53, "f", "", "*-Nano", "Returns the current step stride slope (float). ", 10),
    _Command("getStepStrideOffset", 53, "f", "", "*-Nano", "Returns the current step stride offset (float). ", 11),
    _Command("getUnits", 53, "f", "", "*-Nano", "Returns the current units for distance. Pass in 0.0 for meters or 1.0 for feet. ", 12),
    _Command("getHeadingInDegrees", 53, "f", "", "*-Nano", "Returns the current heading (float) in degrees. ", 18),
    _Command("getStepBufferLength", 53, "f", "", "*-Nano", "Returns the number of steps recorded (float). ", 19),
    _Command("getTotalDistanceTraveled", 53, "f", "", "*-Nano", "Returns the total distance traveled (float) in the units specified by setUnits. ", 20),
    _Command("getConfidenceValue", 53, "f", "", "*-Nano", "Returns the current confidence value. ", 21),
    _Command("getLatestStep", 53, "12f", "", "*-Nano", """Returns the most recent step data. Its format is as follows:
    Index (float),
    Heading (float),
    X Step Distance (float),
    Y Step Distance (float),
    Step Distance (float),
    Step Time (float),
    Step Amplitude (float),
    Step Duty Cycle (float),
    Step Ratio (float),
    Altitude (float),
    Confidence (float),
    Altitude Offset (float).
    This function will return -1 if there is no step data. """, 22),
    _Command("getStepFromCurrentIndex", 53, "12f", "", "*-Nano", """Returns the step data with the index specified in setSelectedStepIndex.
    Its format is as follows:
    Index (float),
    Heading (float),
    X Step Distance (float),
    Y Step Distance (float),
    Step Distance (float),
    Step Time (float),
    Step Amplitude (float),
    Step Duty Cycle (float),
    Step Ratio (float),
    Altitude (float),
    Confidence (float),
    Altitude Offset (float).
    This function will return -1 if there is no step data. """, 23),

    # Data-Logging Commands
    _Command("formatAndInitializeSDCard", 59, "", "", "DL" ,"Erases the contents of the SD card."),
    _Command("beginDataLoggingSession", 60, "", "", "DL" ,"Initiates a data logging section with the specified attributes as indicated in the provided data logging configuration file."),
    _Command("endDataLoggingSession", 61, "", "", "DL" ,"Terminates the ongoing data logging session "),
    _Command("setClockValues", 62, "", "BBBBBB ,month:int,day:int,year:int,hour:int,minute:int,second:int", "DL" ,"Sets the current time on the onboard real-time clock."),
    _Command("getClockValues", 63, "BBBBBB", "", "DL" ,"Returns the current time as read by the onboard real-time clock. ")
]
