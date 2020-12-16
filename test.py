#!/usr/bin/env python3

from gattlib import *
from gattlib.adapter import *
from gattlib.device import *
from gattlib.uuid import *
import sys
from gi.repository import GLib
import signal
from threading import Thread

MUSE_MAC_PREFIX = '00:55:DA:'
PRIMARY_SERVICE = '0000fe8d-0000-1000-8000-00805f9b34fb'
CHARACTERISTIC_UUID_TEMPLATE = '273e00{}-4c4d-454d-96be-f03bac821358'

GATT_CHARACTERISTIC_IDS = {
    # i'm not sure these names have the right numbers
    # the presets are associated with the numbers, not the names, on my Muse S
    'SERIAL': 1,
    # packets start with a 16-bit sequence number
    # eeg signals are all 12-bit numbers concatenated together
    'SIGNAL_AUX_LEFT': 2,  #                                              p63
    'SIGNAL_TP9': 3,       # p20, p21, p22, p23, p50, p51, p52, p60, p61, p63
    'SIGNAL_FP1': 4,       # p20, p21, p22, p23, p50, p51, p52, p60, p61, p63
    'SIGNAL_FP2': 5,       # p20, p21, p22, p23, p50, p51, p52, p60, p61, p63
    'SIGNAL_TP10': 6,      # p20, p21, p22, p23, p50, p51, p52, p60, p61, p63
    'SIGNAL_AUX_RIGHT': 7, # p20            p23  p50            p60       p63
    'DRL_REF': 8,          # p20  p21  p22  p23  p50  p51  p52  p60  p61  p63
    # imu data is sent as 16-bit numbers, 3 3-axis vectors at a time
    'GYRO': 9,             # p20  p21            p50  p51       p60  p61  p63
    'ACCELEROMETER': 0xa,  # p20  p21            p50  p51       p60  p61  p63
    # battery packet format is uncertain
    'BATTERY': 0xb,        # p20  p21  p22  p23  p50  p51  p52  p60  p61  p63
    'MAGNETOMETER': 0xc,   #                        not on muse S
    'PRESSURE': 0xd,       #                        not on muse S
    'ULTRA_VIOLET': 0xe,   #                        not on muse S
    # PPG appears to be 24bit intensity data.
    'PPG_AMBIENT': 0xf,    #                     p50  p51  p52  p60  p61  p63
    'PPG_IR': 0x10,        #                     p50  p51  p52  p60  p61  p63
    'PPG_RED': 0x11,       #                     p50  p51  p52  p60  p61  p63
    # thermistor has 12-bit format, like the eeg signals
    # it looks like lower numbers indicate warmer temperature
    'THERMISTOR': 0x12,    # p20       p22       p50            p60       p63
}
GATT_CHARACTERISTIC_UUIDS = {    
    name: CHARACTERISTIC_UUID_TEMPLATE.format('%02x' % id)
    for name, id in GATT_CHARACTERISTIC_IDS.items()
}


def main():
    argv=[sys.argv[0], MUSE_MAC_PREFIX + 'BB:1C:52', GATT_CHARACTERISTIC_UUIDS['SERIAL'], GATT_CHARACTERISTIC_UUIDS['SERIAL'], '0376310a']
    notify_uuid = UUID(argv[2])
    if len(argv) > 3:
        write_uuid = UUID(argv[3])

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
            data = bytes.fromhex(arg)
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
