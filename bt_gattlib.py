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

    def start_scanning(self, callback = None):
        self._devices = []

        # 2020-12
        # this would be an easy patch to gattlib, similar to the characteristic enumeration code
        print('')
        print('Warning: gattlib has no way to enumerate devices that are already connected via bluetooth.')
        print('')

        self._adapter.open()
        sem = Semaphore(0)
        cont = True
        def on_scan(device, userdata):
            addr = str(device.id)
            name = str(device)
            self._devices.append((addr,name))
            print('device {} {}'.format(addr,name))
            sem.release()
        def pump():
            sem.acquire()
            while cont:
                print('sem {}', self._devices[-1])
                callback(self._devices)
                sem.acquire()
        thread = Thread(target=pump)
        thread.start()
                        
        self._adapter.scan_enable(on_scan, 0)
        cont = False
        sem.release()
        thread.join()
    
    def stop_scanning(self):
        print('stopping scanning')
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
        print('DISCONNECT')
        self._device.disconnect()
        atexit.unregister(self.__del__)
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
        for characteristic in self._device._device.characteristics.values():
            if str(characteristic.uuid) == uuid:
                if self._characteristic is not None:
                    raise AssertionError('todo: characteristics with matching uuids')
                self._characteristic = characteristic
        if self._characteristic is None:
            raise ValueError('no such characteristic on device')
        self._characteristic.register_notification(self._notification_registrant)
    def _notification_registrant(self, data, user_data):
        # current interface is for ONE subscriber at once; this is just to ease changes if they happen
        for subscribee in self._subscribees:
            subscribee(data)
    def subscribe(self, callback):
        self._subscribees.add(callback)
        self._characteristic.notification_start()  
    def unsubscribe():
        self._subscribees.clear()
        self._characteristic.notification_stop()
    def write(self, data : bytes):
        self._characteristic.write(data)

_interface = Interface()

