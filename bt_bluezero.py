import bluezero.adapter
import bluezero.central
import bluezero.device
import bluezero.GATT

import bluezero.async_tools
import bluezero.dbus_tools
import bluezero.constants

import threading
import time

def interfaces():
    return [Interface(mac) for mac in bluezero.adapter.list_adapters()]

class PumpThread:
    def __init__(self):
        self._pumploop = bluezero.async_tools.EventLoop()
        self._lock = threading.Lock()
        self._counter = 0
    def add_needed(self):
        with self._lock:
            if self._counter == 0:
                threading.Thread(target=self.run,name='bluezero gobject pump').start()
            self._counter += 1
    def remove_needed(self):
        with self._lock:
            self._counter -= 1
            if self._counter < 0:
                raise AssertionError('threading release without initialisation')
            if self._counter == 0:
                self.stop()
    def run(self):
        print('bluezero pump starting')
        self._pumploop.run()
        print('bluezero pump stopped')
    def stop(self):
        print('bluezero pump stopping')
        self._pumploop.quit()
_pump = PumpThread()

class Interface:
    def __init__(self, mac):
        self._adapter = bluezero.adapter.Adapter(mac)
        self._devices = {}

    def start_scanning(self, callback = None):
        self._adapter.powered = True
        self._adapter.start_discovery()
        if callback:
            def on_device_found(*params):
                callback(self.near_addresses())
                return False
            self._adapter.on_device_found = on_device_found
        _pump.add_needed() # not sure if this is needed with no callback, but atm it is uncalled in stop_scanning
        if callback:
            _pump._pumploop.add_timer(1, on_device_found) # recurs at this many ms until returns False

    def stop_scanning(self):
        _pump.remove_needed()
        self._adapter.stop_discovery()

    def near_addresses(self):
        devices = []
        mngd_objs = bluezero.dbus_tools.get_managed_objects()
        for path, obj in mngd_objs.items():
            device = obj.get(bluezero.constants.DEVICE_INTERFACE, None)
            if device and device['Adapter'] == self._adapter.path:
                devices.append(device['Address'])
        return [(str(address), str(bluezero.device.Device(self._adapter.address, address).alias)) for address in devices]

    def device(self, address):
        return LEDevice(self, address)

class LEDevice:
    def __init__(self, interface, address):
        self._central = bluezero.central.Central(address, interface._adapter.address)
        if not self._central.connected:
            self._central.connect()
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
        print('bluezero characteristic subscription')
        self._gatt.add_characteristic_cb(handoff)
        self._gatt.start_notify()
        _pump.add_needed()
    def unsubscribe(self):
        print('bluezero characteristic unsubscription')
        self._gatt.stop_notify()
        _pump.remove_needed()
    def write(self, data : bytes):
        self._gatt.value = list(data)

#class Gatt:
#    def __init__(self, interface, address, service, characteristic):
#        self._gatt = bluezero.GATT.Characteristic(interface._adapter.address, address, service, characteristic)
#class LEConnection:
#    def __init__(self, interface, address):
#        self._central = bluezero.central(interface._adapter.address, address)
#        self._central.connect()
#    def 
#            
#        self.adapter.on_connect = self.on_connect
#        self.adapter.on_disconnect = self.on_disconnect
#        self.adapter.run()
#        #self.print_devices()
#        #self.adapter.nearby_discovery(10)
#    def is_muse(self, address):
#        return address[:9] == '00:55:DA:'
#    def stop(self):
#        self.adapter.stop_discovery()
#
#    def on_device_found(self, device):
#        print(f'found:{device.address} paired:{device.paired} connected:{device.connected} muse:{self.is_muse(device.address)}')
#        if self.is_muse(device.address):
#            device.central = bluezero.central.Central(device.address, self.adapter.address)
#            # muse doesn't seem to need pairing? maybe it does?
#            if not device.connected:
#                device.connect()
#            else:
#                self.on_connect(device)
#
#    def on_anything(self, *params, interface, signal_name):
#        print(f'interface={interface}, signal_name={signal_name}, params=', params)
#    def on_connect(self, device):
#        if not self.is_muse(device.address):
#            return
#        data = device.manufacturer_data
#        data = (*data.values(),)[0]
#        print('connected', device, data)
#        #import dbus
#        #while True:
#        #    try:
#        #        device.connect(SPP_UUID)
#        #        break
#        #    except dbus.exceptions.DBusException as e:
#        #        print(e)
#        #        time.sleep(1)
#        #        continue
#        #
#        #print('connected to serial profile')
#        #for service in device.gatt_services:
#        #    gatt = bluezero.GATT.Service(self.adapter.address, device.address, service)
#        #    if not gatt.primary:
#        #        continue           
#        #print(gatt.UUID)
#        import logging
#        class printhandler(logging.Handler):
#            def emit(self, record):
#                print(record)
#        bluezero.GATT.logger.addHandler(printhandler())
#        accel = device.central.add_characteristic(PRIMARY_SERVICE, ACCELEROMETER_CHARACTERISTIC)
#        accel.resolve_gatt()
#        accel.add_characteristic_cb(print)
#        accel.start_notify()
#        ctrl = device.central.add_characteristic(PRIMARY_SERVICE, CONTROL_CHARACTERISTIC)
#        ctrl.resolve_gatt()
#        def muse_serial_in(iface, changed_props, invalidated_props):
#            if 'Value' in changed_props:
#                print(repr(bytes(changed_props['Value'])))
#            else:
#                print(iface, changed_props, invalidated_props)
#        ctrl.add_characteristic_cb(muse_serial_in)
#        ctrl.start_notify()
#        #ctrl.value = encode_command('v1')
#        #ctrl.value = encode_command('h')
#        #ctrl.value = encode_command('p20')
#        #ctrl.value = encode_command('s')
#        ctrl.value = encode_command('d')
#        
#    def on_disconnect(self, device):
#        print('disconnected', device)
#
#_=c()
#time.sleep(60)
#_.stop()
