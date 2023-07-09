from io import BytesIO
from pywintypes import error
from struct import (
                    calcsize,
                    unpack,
                   )
from typing import (
                    List,
                    Optional,
                    Union,
                   )
from win32file import (
                       FILE_ATTRIBUTE_NORMAL,
                       FILE_SHARE_READ,
                       FILE_SHARE_WRITE,
                       OPEN_EXISTING,
                       CreateFile,
                       DeviceIoControl,
                       ReadFile,
                       SetFilePointer,
                       WriteFile,
                      )
from winioctlcon import (
                         FILE_READ_DATA,
                         FILE_WRITE_DATA,
                         FSCTL_DISMOUNT_VOLUME,
                         FSCTL_LOCK_VOLUME,
                         FSCTL_UNLOCK_VOLUME,
                         IOCTL_DISK_GET_LENGTH_INFO,
                        )

from wmi import WMI


class fopen(object):
    'класс для работы с блочными устройствами и io.BytesIO() как с файлом'

    def __init__(
                 self,
                 filename: Union[str, BytesIO],
                 mode: str = "r+b",
                 letters: List[str] = [],
                ) -> None:
        'инициализация класса'

        self.filename = filename
        self.bs = 512
        self.buffer = b''
        self.pos = 0
        self.mode = mode
        self.filesize = False
        self.handle = False
        self.letters = letters

        if self.mode == "rb":
            self.write_enabled = False
        elif self.mode in ("r+b", "rb+", "wb"):
            self.write_enabled = True
        else:
            return False
        
        if isinstance(
                      self.filename,
                      BytesIO,
                     ):
            self.type = "BYTESIO"
            self.handle = self.filename

        elif "\\\\.\\PHYSICALDRIVE" in self.filename:
            self.type = "BLOCKDEV"
            self.lock()
            self.handle = CreateFile(
                                     self.filename,
                                     FILE_READ_DATA |
                                     FILE_WRITE_DATA,
                                     FILE_SHARE_READ |
                                     FILE_SHARE_WRITE,
                                     None,
                                     OPEN_EXISTING,
                                     FILE_ATTRIBUTE_NORMAL,
                                     None,
                                    )

        else:
            self.type = "FILE"
            self.handle = open(
                               self.filename,
                               self.mode,
                              )

    def getletters(self) -> None:
        'если не передан список логических дисков'
        'для блочного устройства, ищем самостоятельно'
        
        self.letters.clear()
        letters = []
        c = WMI()

        for drive in c.Win32_DiskDrive():
            if drive.DeviceID == self.filename:
                for partition in c.query(
                                         'ASSOCIATORS OF {Win32_DiskDrive.DeviceID="' +
                                         drive.DeviceID +
                                         '"} WHERE AssocClass = Win32_DiskDriveToDiskPartition'
                                        ):
                    for logical_disk in c.query(
                                                'ASSOCIATORS OF {Win32_DiskPartition.DeviceID="' +
                                                partition.DeviceID +
                                                '"} WHERE AssocClass = Win32_LogicalDiskToPartition'
                                               ):
                        letters.append(
                                       '\\\\.\\' +
                                       logical_disk.DeviceID
                                      )
        del c

        for letter in letters:
            try:
                letterHeader = CreateFile(
                                          letter,
                                          FILE_READ_DATA |
                                          FILE_WRITE_DATA,
                                          FILE_SHARE_READ |
                                          FILE_SHARE_WRITE,
                                          None,
                                          OPEN_EXISTING,
                                          FILE_ATTRIBUTE_NORMAL,
                                          None,
                                         )
                self.letters.append(letterHeader)
            except Exception:
                'если получили ошибку пропускаем'
    
    def lock(self) -> None:
        'блокировка логических дисков перед записью'

        if not self.letters:
            self.getletters()
        
        try:
            for letter in self.letters:
                DeviceIoControl(
                                letter,
                                FSCTL_LOCK_VOLUME,
                                None,
                                None,
                               )
                DeviceIoControl(
                                letter,
                                FSCTL_DISMOUNT_VOLUME,
                                None,
                                None,
                               )
        except error as _:
            'если получили ошибку пропускаем'
    
    def unlock(self) -> None:
        'разблокировка логических дисков после записи'

        try:
            for letter in self.letters:
                DeviceIoControl(
                                letter,
                                FSCTL_UNLOCK_VOLUME,
                                None,
                                None,
                               )
                letter.Close()
            self.letters.clear()
        except error as _:
            'если получили ошибку пропускаем'
    
    def seek(
             self,
             position: int,
             stop: int = 0,
            ) -> int:
        'переход по смещению'

        if self.type == "BLOCKDEV":
            if position == 0 and stop == 2:
                self.pos = unpack(
                                  'Q',
                                  DeviceIoControl(
                                                  self.handle,
                                                  IOCTL_DISK_GET_LENGTH_INFO,
                                                  None,
                                                  calcsize('LL'),
                                                  None,
                                                 )
                                 )[0] - self.bs
                self.filesize = self.pos
                SetFilePointer(
                               self.handle,
                               self.pos,
                               0,
                              )
                self.buffer = b''
                return self.pos
            pos = position % self.bs
            if pos != 0:
                SetFilePointer(
                               self.handle,
                               position - pos,
                               0,
                              )
                _, buffer = ReadFile(
                                     self.handle,
                                     self.bs,
                                     None,
                                    )
                self.buffer = buffer[:pos]
                SetFilePointer(
                               self.handle,
                               position - pos,
                               0,
                              )
            else:
                SetFilePointer(
                               self.handle,
                               position,
                               0,
                              )
                self.buffer = b''
            self.pos = position
        else:
            if position == 0 and stop == 2:
                self.handle.seek(
                                 position,
                                 stop,
                                )
                self.filesize = self.tell()
            else:
                self.handle.seek(position)
            self.pos = self.handle.tell()
        return self.pos
    
    def read(
             self,
             lenghts: int = -1
            ) -> bytes:
        'чтение данных из объекта'

        if self.type == "BLOCKDEV":
            if lenghts != -1:
                lens = lenghts % self.bs
                bs = self.bs
                while (len(self.buffer) + lens) > bs:
                    bs += self.bs
                _, buffer = ReadFile(
                                     self.handle,
                                     lenghts - lens + bs,
                                     None,
                                    )
                byteOut = buffer[
                                 len(self.buffer):
                                 len(self.buffer) + lenghts
                                ]
                self.pos += lenghts
                self.buffer = buffer[
                                     -self.bs:
                                     -self.bs + (self.pos % self.bs)
                                    ]
            else:
                if not self.filesize:
                    self.filesize = unpack(
                                           'Q',
                                           DeviceIoControl(
                                                           self.handle,
                                                           IOCTL_DISK_GET_LENGTH_INFO,
                                                           None,
                                                           calcsize('LL'),
                                                           None,
                                                          )
                                          )[0]
                _, buffer = ReadFile(
                                     self.handle,
                                     self.filesize - self.pos - len(self.buffer),
                                     None,
                                    )
                self.pos = self.filesize
                byteOut = buffer[len(self.buffer):]
                self.buffer = b''
        else:
            byteOut = self.handle.read(lenghts)
            self.pos = self.handle.tell()
        return byteOut
    
    def write(
              self,
              byteObj: Union[bytes, bytearray],
             ) -> int:
        'запись данных в объект'

        if type(byteObj) is bytearray:
            byteObj = bytes(byteObj)
        if self.type == "BLOCKDEV":
            lens = len(self.buffer + byteObj) % self.bs
            if lens != 0:
                bs = self.bs
                while len(self.buffer + byteObj) > bs:
                    bs += self.bs
                _, buff = ReadFile(
                                   self.handle,
                                   bs,
                                   None,
                                  )
                buffer = self.buffer + byteObj + buff[
                                                      len(self.buffer + byteObj):
                                                     ]
                SetFilePointer(
                               self.handle,
                               self.pos - len(self.buffer),
                               0,
                              )
                self.buffer = buff[
                                   -self.bs:
                                   len(self.buffer + byteObj)
                                  ]
            else:
                buffer = self.buffer + byteObj
                self.buffer = b''
            WriteFile(
                      self.handle,
                      buffer,
                     )
            self.pos += len(byteObj)
        else:
            self.handle.write(byteObj)
            self.pos = self.handle.tell()
        return len(byteObj)

    def flush(self) -> None:
        if self.type != "BLOCKDEV":
            self.handle.flush()
    
    def tell(self) -> int:
        return self.pos

    def readable(self) -> bool:
        return True

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True
    
    def close(self) -> None:
        self.flush()
        if self.type != "BYTESIO":
            self.handle.close()
        else:
            self.handle.seek(0)
        if self.type == "BLOCKDEV":
            self.unlock()
    
    def fileno(self) -> Optional[int]:
        if self.type == "FILE":
            return self.handle.fileno()
    
    def __enter__(self) -> object:
        return self

    def __exit__(self, *_) -> None:
        self.close()
