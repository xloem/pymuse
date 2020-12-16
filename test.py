#!/usr/bin/env python3

from gattlib import *
from gattlib.adapter import *
from gattlib.device import *
from gattlib.uuid import *
import sys
from gi.repository import GLib
import signal
from threading import Thread

# int gattlib_string_to_uuid(const char *str, size_t size, uuid_t *uuid);
gattlib_string_to_uuid = gattlib.gattlib_string_to_uuid
gattlib_string_to_uuid.argtypes = [c_char_p, c_size_t , POINTER(GattlibUuid)]

SUCCESS = 0
INVALID_PARAMETER = 1
NOT_FOUND = 2
OUT_OF_MEMORY = 3
NOT_SUPPORTED = 4
DEVICE_ERROR = 5
ERROR_DBUS = 6
ERROR_BLUEZ = 7
ERROR_INTERNAL = 8

def usage():
    print(sys.argv[0], '<device_address> <notification_characteristic_uuid> [<write_characteristic_uuid> <write_characteristic_hex_data> ...]')

def main():
    notify_uuid = UUID(sys.argv[2])
    if len(sys.argv) > 3:
        write_uuid = UUID(sys.argv[3])
    argv = [bytes(arg, 'utf-8') for arg in sys.argv]
    if len(argv) < 3:
        return usage()
        

    #notify_uuid = GattlibUuid()
    #write_uuid = GattlibUuid()

    #if gattlib_string_to_uuid(argv[2], len(argv[2]) + 1, byref(notify_uuid)) < 0:
    #    return usage()

    #if len(argv) > 3:
    #    if gattlib_string_to_uuid(argv[3], len(argv[3]) + 1, byref(write_uuid)) < 0:
    #        return usage()

    loop = GLib.MainLoop()
    thread = Thread(target=loop.run)
    thread.start()

    adapter = Adapter()
    device = Device(adapter, argv[1])
    
    device.connect()
    connection = device.connection

    device.discover()

    for characteristic in device.characteristics.values():
        if len(argv) > 3 and characteristic.uuid == write_uuid:
            write_characteristic = characteristic
        if characteristic.uuid == notify_uuid:
            notify_characteristic = characteristic

    try:
    
        def callback(*args, **kwargs):
            print('callback', args, kwargs)
        notify_characteristic.register_notification(callback, b'useR')
    
        notify_characteristic.notification_start()
    
        for arg in argv[4:]:
            data = bytes.fromhex(arg.decode('utf-8'))
            write_characteristic.write(data)
    
        def on_user_abort(signum, frame):
            print('caught CTRL-C, stopping')
            loop.quit()
        signal.signal(signal.SIGINT, on_user_abort)
    
        thread.join()
        #loop.run()
    
        #gattlib_notification_stop(connection, byref(notify_uuid))
        notify_characteristic.notification_stop()
    except Exception as e:
        print(e)

    device.disconnect()

if __name__ == '__main__':
    main()
