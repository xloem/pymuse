import async_to_sync as sync
#import asyncio
import atexit
import bleak
import threading
#import logging
#logging.basicConfig(level=logging.DEBUG)

def interfaces():
    return [_interface]

class Interface:
    def __init__(self):
        self._scanner = sync.methods(bleak.BleakScanner())
        self._near_addresses = []
        self._connected = []

    def start_scanning(self, callback = None):
        if callback:
            def on_device_found(new_device, new_advertisement_data):
                if not self._stop_scanning.is_set():
                    callback(self.near_addresses())
            def handoff(new_device, new_advertisement_data):
                threading.Thread(target=on_device_found, args=(new_device, new_advertisement_data)).start()
            self._scanner.register_detection_callback(handoff)
        self._stop_scanning = threading.Event()
        self._scanner.start()
        self._wait()

    def _wait(self):
        self._stop_scanning.wait()

    def stop_scanning(self):
        self._stop_scanning.set()
        self._scanner.stop()

    def near_addresses(self):
        devices = self._scanner.get_discovered_devices()
        #self._devices = {device.address: device for device in devices}
        return [(device.address, device.name) for device in devices]

    def device(self, address):
        try:
            client = sync.methods(bleak.BleakClient(address))
            client.connect()
            device = LEDevice(self, address, client)
            self._connected.append(device)
            return device
        except Exception as e:
            print('== failed to connect to {} =='.format(address), e)
            return None

    def _destroy(self):
        for device in self._connected:
            device._destroy()

_interface = Interface()
@atexit.register
def _destroy():
    _interface._destroy()

class LEDevice:
    def __init__(self, interface, address, connected_client):
        self._interface = interface
        self._address = address
        self._client = connected_client
    def _destroy(self):
        if self._client:
            self._client.disconnect()
        self._client = None
    def __del__(self):
        self._destroy()
    def info(self):
        return {
            'address': self._address
        }
    def characteristic(self, service, uuid):
        return Characteristic(self, service, uuid)

class Characteristic:
    def __init__(self, device, service, uuid):
        self._device = device
        self._service = service
        self._uuid = uuid
        service = self._device._client.services.get_service(self._service)
        characteristic = service.get_characteristic(self._uuid)
        self._characteristic = characteristic
    def subscribe(self, callback):
        def handoff(characteristic : int, data : bytearray):
            callback(data)
        self._device._client.start_notify(self._characteristic, handoff)
    def unsubscribe(self):
        self._device._client.stop_notify(self._characteristic)
    def write(self, data):
        data = bytearray(data)
        self._device._client.write_gatt_char(self._characteristic, data)
