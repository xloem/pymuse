import bluezero.adapter
import bluezero.central
import bluezero.device
import bluezero.GATT

import bluezero.async_tools
import bluezero.dbus_tools
import bluezero.constants

import dbus

import threading
import time

def interfaces():
    return [Interface(mac) for mac in bluezero.adapter.list_adapters()]

class PumpThread:
    def __init__(self):
        self._pumploop = bluezero.async_tools.EventLoop()
        self._lock = threading.Lock()
        self._counter = 0
        self._thread = None
    def add_needed(self):
        with self._lock:
            if self._counter == 0:
                self._thread = threading.Thread(target=self._run,name='bluezero gobject pump')
                self._thread.start()
            self._counter += 1
    def remove_needed(self):
        thread = threading.currentThread()
        with self._lock:
            self._counter -= 1
            count = self._counter
            if self._counter < 0:
                raise AssertionError('threading release without initialisation')
            if self._counter == 0:
                thread = self._thread
                self._pumploop.quit()
        if thread is not threading.currentThread():
            thread.join()
    def wait(self):
        with self._lock:
            if self._thread is None:
                return
            thread = self._thread
        thread.join()
    def afterms_callonce(self, milliseconds, callback):
        def handoff():
            callback()
            return False
        self.afterms_untilfalse(self, milliseconds, handoff)
    def afterms_untilfalse(self, milliseconds, callback):
        _pump._pumploop.add_timer(milliseconds, callback)
    def _run(self):
        self._pumploop.run()
        self._thread = None
_pump = PumpThread()

class Interface:
    def __init__(self, mac):
        self._adapter = bluezero.adapter.Adapter(mac)
        self._devices = {}

    def start_scanning(self, callback = None):
        self._adapter.powered = True
        try:
            self._adapter.start_discovery()
        except Exception as e:
            print('exception thrown starting discovery')
            print(e)
            raise e
        def do_callback(callback):
            if callback:
                def on_device_found(*params):
                    if callback:
                        callback(self.near_addresses())
                    return callback is not None
                self._adapter.on_device_found = on_device_found
            _pump.add_needed() # not sure if this is needed with no callback, but atm it is uncalled in stop_scanning
            if callback:
                _pump.afterms_untilfalse(500, on_device_found)
            _pump.wait()
            if callback:
                self._adapter.on_device_found = None
                callback = None
        return do_callback(callback)

    def stop_scanning(self):
        self._adapter.stop_discovery()
        _pump.remove_needed()

    def near_addresses(self):
        devices = []
        mngd_objs = bluezero.dbus_tools.get_managed_objects()
        for path, obj in mngd_objs.items():
            device = obj.get(bluezero.constants.DEVICE_INTERFACE, None)
            if device and device['Adapter'] == self._adapter.path:
                devices.append(device['Address'])
        return [(str(address), str(bluezero.device.Device(self._adapter.address, address).alias)) for address in devices]

    def device(self, address):
        try:
            return LEDevice(self, address)
        except dbus.exceptions.DBusException:
            print('== failed to connect to {} =='.format(address))
            return None

class LEDevice:
    def __init__(self, interface, address):
        self._central = bluezero.central.Central(address, interface._adapter.address)
        if not self._central.connected:
            self._central.connect()

    def info(self):
        return {
            'address': str(self._central.rmt_device.address)
        }

    def characteristic(self, service, uuid):
        return Characteristic(self, service, uuid)

class Characteristic:
    def __init__(self, device, service, uuid):
        self._gatt = device._central.add_characteristic(service, uuid)
        self._gatt.resolve_gatt()
    def subscribe(self, callback):
        def handoff(iface, changed, invalidated):
            if 'Value' in changed:
                callback(bytes(changed['Value']))
            else:
                print(f'iface:{iface}, changed:{changed}, invalidated:{invalidated}')
        self._gatt.add_characteristic_cb(handoff)
        self._gatt.start_notify()
        _pump.add_needed()
    def unsubscribe(self):
        self._gatt.stop_notify()
        _pump.remove_needed()
    def write(self, data : bytes):
        self._gatt.value = list(data)
