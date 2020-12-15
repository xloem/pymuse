import gattlib.adapter
import gattlib.device

from concurrent.futures import Future

def interfaces():
    return [_interface]

class Interface:
    def __init__(self, mac=None):
        self._adapter = gattlib.adapter.Adapter()
        self._devices = {}
        self._addrs = []

    def start_scanning(self, callback = None):
        self._addrs = []

        self._adapter.open()
        def on_scan(device, userdata):
            addr = str(device)
            self._addrs.append(addr)
            callback(self._addrs)
        self._adapter.scan_enable(on_scan, 0):
    
    def stop_scanning(self):
        self._adapter.scan_disable()

    def near_addresses(self):
        return self._addrs

    def device(self, address):
        return LEDevice(self, address)

class LEDevice:
    def __init__(self, interface, address):
        self._device = gattlib.device.Device(interface, address)
        self._device.discover()
    def characteristic(self, service, uuid):
        return Characteristic(self, service, uuid)

class Characteristic:
    def __init__(self, device, service, uuid):
        self._device = device
        self._service = service
        self._uuid = uuid
        self._characteristic = None
        self._subscribees = set()
        for characteristic in self._device.characteristics:
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

