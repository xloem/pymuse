import asyncio
import atexit
import bleak
#import logging
#logging.basicConfig(level=logging.DEBUG)

async def interfaces():
    return [_interface]

class Interface:
    def __init__(self):
        self._scanner = bleak.BleakScanner()
        self._near_addresses = []
        self._connected = []

    async def start_scanning(self, callback = None):
        if callback:
            def on_device_found(new_device, new_advertisement_data):
                callback(self.near_addresses())
            self._scanner.register_detection_callback(on_device_found)
        self._stop_scanning = asyncio.Event()
        await self._scanner.start()

    async def wait(self):
        await self._stop_scanning.wait()

    async def stop_scanning(self):
        await self._scanner.stop()
        self._stop_scanning.set()

    async def near_addresses(self):
        devices = await self._scanner.get_discovered_devices()
        #self._devices = {device.address: device for device in devices}
        return [(device.address, device.name) for device in devices]

    async def device(self, address):
        try:
            client = bleak.BleakClient(address)
            await client.connect()
            device = LEDevice(self, address, client)
            self._connected.append(device)
            return device
        except Exception as e:
            print('== failed to connect to {} =='.format(address), e)
            return None

    async def _destroy(self):
        await asyncio.wait([device._client.disconnect() for device in self._connected], return_when=asyncio.ALL_COMPLETED)
        self._connected = []

_interface = Interface()
@atexit.register
def _destroy():
    asyncio.get_event_loop().run_until_complete(_interface._destroy())

class LEDevice:
    def __init__(self, interface, address, connected_client):
        self._interface = interface
        self._address = address
        self._client = connected_client
#    def __del__(self):
#        asyncio.get_event_loop().run_until_complete(self._client.disconnect())
    def info(self):
        return {
            'address': self._address
        }
    async def characteristic(self, service, uuid):
        return Characteristic(self, service, uuid)

class Characteristic:
    def __init__(self, device, service, uuid):
        self._device = device
        self._service = service
        self._uuid = uuid
        service = self._device._client.services.get_service(self._service)
        characteristic = service.get_characteristic(self._uuid)
        self._characteristic = characteristic
    async def subscribe(self, callback):
        def handoff(characteristic : int, data : bytearray):
            callback(data)
        await self._device._client.start_notify(self._characteristic, handoff)
    async def unsubscribe(self):
        await self._device._client.stop_notify(self._characteristic)
    async def write(self, data):
        data = bytearray(data)
        await self._device._client.write_gatt_char(self._characteristic, data)
