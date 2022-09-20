import io, pywintypes, struct, win32file, winioctlcon, wmi

class fopen(object):
    # класс для работы с блочными устройствами и io.BytesIO() как с файлом
    def __init__(self, filename, mode="rb"):
        self.filename = filename
        self.bs = 512
        self.buffer = b''
        self.pos = 0
        self.mode = mode
        self.filesize = False
        self.handle = False
        self.letters = []
        if self.mode == "rb":
            self.write_enabled = False
        elif self.mode in ["r+b", "rb+", "wb"]:
            self.write_enabled = True
        else:
            return False
        if "\\\\.\\PHYSICALDRIVE" in self.filename:
            self.type = "BLOCKDEV"
            self.lock()
            self.handle = win32file.CreateFile(self.filename, winioctlcon.FILE_READ_DATA | winioctlcon.FILE_WRITE_DATA, win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                                                                                                    None, win32file.OPEN_EXISTING, win32file.FILE_ATTRIBUTE_NORMAL, None)
        elif type(self.filename) is io.BytesIO:
            self.type = "BYTESIO"
            self.handle = self.filename
        else:
            self.type = "FILE"
            self.handle = open(self.filename, self.mode)

    def getletters(self):
        self.letters.clear()
        letters = []
        c = wmi.WMI()
        for drive in c.Win32_DiskDrive():
            if drive.DeviceID == self.filename:
                for partition in c.query('ASSOCIATORS OF {Win32_DiskDrive.DeviceID="' + drive.DeviceID + '"} WHERE AssocClass = Win32_DiskDriveToDiskPartition'):
                    for logical_disk in c.query('ASSOCIATORS OF {Win32_DiskPartition.DeviceID="' + partition.DeviceID + '"} WHERE AssocClass = Win32_LogicalDiskToPartition'):
                        letters.append('\\\\.\\'+logical_disk.DeviceID)
        del c
        for letter in letters:
            try:
                letterHeader = win32file.CreateFile(letter, winioctlcon.FILE_READ_DATA | winioctlcon.FILE_WRITE_DATA, win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                                                                                                        None, win32file.OPEN_EXISTING, win32file.FILE_ATTRIBUTE_NORMAL, None)
                self.letters.append(letterHeader)
            except Exception:
                pass
    
    def lock(self):
        if not self.letters:
            self.getletters()
        try:
            for letter in self.letters:
                win32file.DeviceIoControl(letter, winioctlcon.FSCTL_LOCK_VOLUME, None, None)
                win32file.DeviceIoControl(letter, winioctlcon.FSCTL_DISMOUNT_VOLUME, None, None)
        except pywintypes.error as e:
            pass
    
    def unlock(self):
        try:
            for letter in self.letters:
                win32file.DeviceIoControl(letter, winioctlcon.FSCTL_UNLOCK_VOLUME, None, None)
                letter.Close()
            self.letters.clear()
        except pywintypes.error as e:
            pass
    
    def seek(self, position, stop=0):
        if self.type == "BLOCKDEV":
            if position == 0 and stop == 2:
                self.pos = struct.unpack('Q', win32file.DeviceIoControl(self.handle, winioctlcon.IOCTL_DISK_GET_LENGTH_INFO, None, struct.calcsize('LL'), None))[0]-self.bs
                self.filesize = self.pos
                win32file.SetFilePointer(self.handle, self.pos, 0)
                self.buffer = b''
            else:
                pos = position % self.bs
                if pos != 0:
                    win32file.SetFilePointer(self.handle, position-pos, 0)
                    noneed, buffer = win32file.ReadFile(self.handle, self.bs, None)
                    self.buffer = buffer[:pos]
                    win32file.SetFilePointer(self.handle, position-pos, 0)
                else:
                    win32file.SetFilePointer(self.handle, position, 0)
                    self.buffer = b''
                self.pos = position
        else:
            if position == 0 and stop == 2:
                self.handle.seek(position, stop)
                self.filesize = self.tell()
            else:
                self.handle.seek(position)
            self.pos = self.handle.tell()
        return self.pos
    
    def read(self, lenghts=None):
        if self.type == "BLOCKDEV":
            if lenghts:
                lens = lenghts % self.bs
                bs = self.bs
                while len(self.buffer)+lens > bs:
                    bs += self.bs
                noneed, buffer = win32file.ReadFile(self.handle, lenghts-lens+bs, None)
                byteOut = buffer[len(self.buffer):len(self.buffer)+lenghts]
                self.pos += lenghts
                self.buffer = buffer[-self.bs:-self.bs+(self.pos % self.bs)]
            else:
                if not self.filesize:
                    self.filesize = struct.unpack('Q', win32file.DeviceIoControl(self.handle, winioctlcon.IOCTL_DISK_GET_LENGTH_INFO, None, struct.calcsize('LL'), None))[0]
                noneed, buffer = win32file.ReadFile(self.handle, self.filesize-self.pos-len(self.buffer), None)
                self.pos = self.filesize
                byteOut = buffer[len(self.buffer):]
                self.buffer = b''
        else:
            byteOut = self.handle.read(lenghts)
            self.pos = self.handle.tell()
        return byteOut
    
    def write(self, byteObj):
        if type(byteObj) is bytearray:
            byteObj = bytes(byteObj)
        if self.type == "BLOCKDEV":
            lens = len(self.buffer + byteObj) % self.bs
            if lens != 0:
                bs = self.bs
                while len(self.buffer + byteObj) > bs:
                    bs += self.bs
                noneed, buff = win32file.ReadFile(self.handle, bs, None)
                buffer = self.buffer + byteObj + buff[len(self.buffer + byteObj):]
                win32file.SetFilePointer(self.handle, self.pos-len(self.buffer), 0)
                self.buffer = buff[-self.bs:len(self.buffer + byteObj)]
            else:
                buffer = self.buffer + byteObj
                self.buffer = b''
            win32file.WriteFile(self.handle, buffer)
            self.pos += len(byteObj)
        else:
            self.handle.write(byteObj)
            self.pos = self.handle.tell()
        return len(byteObj)

    def flush(self):
        if self.type != "BLOCKDEV":
            self.handle.flush()
    
    def tell(self):
        return self.pos

    def readable(self):
        return True

    def writable(self):
        return True

    def seekable(self):
        return True
    
    def close(self):
        self.flush()
        self.handle.close()
        if self.type == "BLOCKDEV":
            self.unlock()
    
    def fileno(self):
        if self.type == "FILE":
            return self.handle.fileno()
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
