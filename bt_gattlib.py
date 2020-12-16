import gattlib.adapter
import gattlib.device

from threading import Semaphore, Thread

import atexit

def interfaces():
    return [_interface]

class Interface:
    def __init__(self, mac=None):
        self._adapter = gattlib.adapter.Adapter()
        self._devices = {}
        self._addrs = []
        self._adapter.open()

    def start_scanning(self, callback = None):
        self._devices = []
        self._scanning = True

        # 2020-12
        # this would be an easy patch to gattlib, similar to the characteristic enumeration code
        print('')
        print('Warning: gattlib has no way to enumerate devices that are already connected via bluetooth.')
        print('')
        
        sem = Semaphore(0)
        def on_scan(device, userdata):
            addr = str(device.id)
            name = str(device)
            self._devices.append((addr,name))
            print('device {} {}'.format(addr,name))
            sem.release()
        def pump():
            while True:
                if sem.acquire(timeout=0.5):
                    print('sem {}'.format(self._devices[-1][0]))
                if not self._scanning:
                    break
                callback(self._devices)
        thread = Thread(target=pump)
        thread.start()
                        
        try:
            # it looks like CTRL-C/SIGINT doesn't interrupt the process during gattlib calls
            # probably not hard to work around that and make it work, maybe by installing a signal handler
            # is probably also a bug in gattlib that would be easy to fix
            self._adapter.scan_enable(on_scan, 0)
        except gattlib.exception.DBusError as e:
            e.args.append('Is Bluetooth turned on?')
            raise e

        sem.release()
        thread.join()
    
    def stop_scanning(self):
        print('stopping scanning')
        self._scanning = False
        self._adapter.scan_disable()

    def near_addresses(self):
        return self._addrs

    def device(self, address):
        return LEDevice(self, address)

class LEDevice:
    def __init__(self, interface, address):
        print('device')
        self._device = gattlib.device.Device(interface._adapter, address)
        print('CONNECT')
        self._device.connect()
        atexit.register(self.__del__)
        print('discovering')
        self._device.discover()
        print('discovered')
    def __del__(self):
        if self._device:
            device = self._device
            self._device = None
            print('DISCONNECT')
            device.disconnect()
    def info(self):
        return {
            'address': str(self._device.id)
        }
    def characteristic(self, service, uuid):
        return Characteristic(self, service, uuid)

class Characteristic:
    def __init__(self, device, service, uuid):
        self._device = device
        self._service = service
        self._uuid = uuid
        self._characteristic = None
        self._subscribees = set()
        for key, value in self._device._device.characteristics.items():
            print(str(key), str(value))
        for characteristic in self._device._device.characteristics.values():
            if str(characteristic.uuid) == uuid:
                if self._characteristic is not None:
                    raise AssertionError('todo: characteristics with matching uuids')
                self._characteristic = characteristic
        if self._characteristic is None:
            raise ValueError('no such characteristic on device')
        print('uuid', self._characteristic.uuid)
        self._characteristic.register_notification(self._notification_registrant)
    def _notification_registrant(self, data, user_data):
        # current interface is for ONE subscriber at once; this is just to ease changes if they happen
        print('notify!')
        for subscribee in self._subscribees:
            subscribee(data)
    def subscribe(self, callback):
        print('subscribe!')
        self._subscribees.add(callback)
        self._characteristic.notification_start()  
    def unsubscribe():
        self._subscribees.clear()
        self._characteristic.notification_stop()
    def write(self, data : bytes):
        print('write!', data)
        for byte in data:
            self._characteristic.write(bytes(byte,))

_interface = Interface()

