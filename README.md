# fopen
class for work with files, BytesIO and block devices (removable devices) such as file

писал год назад. класс для работы с файлами, блочными устройствами и файлоподбными объектами как с обычными файлами под Windows.
для чего это нужно? решаем проблемы с записью, такие как отмонтировать разделы, записать на блочное устройство несколько байт как в обычный файл и т.п.
класс повторяет все основные методы работы с файлом.

Написан для Python 3.*, зависит от io, pywintypes, struct, win32file, winioctlcon, wmi


>>> from fonen impoer fopen
>>> 
>>> test = fopen("\\\\.\\PHYSICALDRIVE5", "wb")
>>> 
>>> # прочитать 10 байт
>>> 
>>> data = test.read(10)
>>> 
>>> # перейти на нужный оффсет
>>> 
>>> test.seek(10000)
>>> 
>>> # записать данные
>>> 
>>> test.write(b"test_data")
>>> 
>>> # получить правильный размер блочного устройства
>>> 
>>> test.seek(0,2)
>>> 
>>> test.tell()
>>> 
>>> # закрыть соединение
>>> 
>>> test.close()
>>> 
>>> # дополнительно
>>> 
>>> with fopen("\\\\.\\PHYSICALDRIVE5", "wb") as file:
>>> 
>>>       file.seek(1024)
>>>       
>>>       file.write("тест записи в блочное устройство по смещению 1024 данных, не кратных 512 байт".encode("utf8"))
>>>       

можно исплоьзовать в сторонних библиотеках для работы с файловыми системами или каких то подобных проектах.
