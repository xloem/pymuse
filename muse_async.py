#!/usr/bin/env python3

# information may be at: (and i haven't reviewed most of this)
#  https://web.archive.org/web/20190515215627/http://android.choosemuse.com/index.html
#  https://sites.google.com/a/interaxon.ca/muse-developer-site/home
    # these were the control commands in 2015: https://sites.google.com/a/interaxon.ca/muse-developer-site/muse-communication-protocol/serial-commands
#  https://web.archive.org/web/20180102133124/http://developer.choosemuse.com/hardware-firmware

# preset information from web (may be more from museio binaries):
# Preset ID   EEG Channels    EEG Data    Accelerometer Data  Notch Filter    Compression Battery/Temp Data   Error Data  DRL/REF Data
# consumer 2014
# 10  TP9, AF7, AF8, TP10 10 bits @ 220Hz None    60Hz    ON  None    None    None
# 12  TP9, AF7, AF8, TP10 10 bits @ 220Hz 50Hz    60Hz    ON  0.1Hz   None    None
# 14  TP9, AF7, AF8, TP10 10 bits @ 220Hz 50Hz    60Hz    ON  0.1Hz   Real-time   10bit @ 10Hz
# research 2014
# AB  TP9, AF7, AF8, TP10, Left AUX, Right AUX    16 bits @ 500Hz 50Hz    OFF OFF 0.1Hz   None    None
# AD  TP9, AF7, AF8, TP10 16 bits @ 500Hz 50Hz    OFF OFF 0.1Hz   None    None
# consumer 2016
# 21  TP9, AF7, AF8, TP10 12 bits @ 256Hz 52Hz    None    OFF 0.1Hz   None    12 bits @ 32Hz
# 22  TP9, AF7, AF8, TP10 12 bits @ 256Hz None    None    OFF 0.1Hz   None    12 bits @ 32Hz
# 23  TP9, AF7, AF8, TP10 12 bits @ 256Hz None    None    OFF 0.1Hz   None    12 bits @ 32Hz

# the official meditation app contains a number of presets in its 2020 binary:
# note the preset numbers are in hexadecimal, and are returned in json decimal in the status command
# enum {
#   PRESET_10; # muse 1, 2014, 2016
#   PRESET_12;
#   PRESET_14;
#   PRESET_20; # muse 2, muse S
#   PRESET_21;
#   PRESET_22;
#   PRESET_23;
#   PRESET_31; # unknown
#   PRESET_32;
#   PRESET_50; # these all worked on my muse S
#   PRESET_51;
#   PRESET_52;
#   PRESET_53;   # this one places it into a different runstate, maybe bootloaderish
#   PRESET_60;
#   PRESET_61;
#   PRESET_63;
#   PRESET_AB; # muse 1, research
#   PRESET_AD;
# }


# muse 2, btle gatt
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

# muse 1, not implemented, rfcomm sdp
SPP_UUID = '00001101-0000-1000-8000-00805F9B34FB'

def _encode_command(cmd : str):
    return [len(cmd) + 1, *(ord(char) for char in cmd), ord('\n')]

import btasync_bleak as bt
import asyncio
from fractions import Fraction

#class MuseDevice:
#    def __init__(self, btdevice):
#        self.device = btdevice
#    async def gatt(self, name):
#        characteristic = await self.device.characteristic(PRIMARY_SERVICE, GATT_CHARACTERISTDIC_UUIDS[name])
#        characteristic.name = name
#        return characteristic
        

class Bits12:
    def __init__(self, device, name):
        self._device = device
        self._name = name
        self._characteristic = GATT_CHARACTERISTIC_UUIDS[self._name]
    async def init(self):
        self._gatt = await self._device.characteristic(PRIMARY_SERVICE, self._characteristic)
        await self._gatt.subscribe(self._recv)
    def _recv(self, data : bytes):
        seq = int.from_bytes(data[0:2], 'big', signed=False)
        samples = []
        for i in range(2, len(data), 3):
            # two 12-bit values made out of three 8-bit values
            samples.append(data[i] << 4 | data[i + 1] >> 4)
            samples.append((data[i + 1] & 0xf) << 8 | data[i + 2])
        samples = [Fraction((sample - 0x800) * 125, 256) for sample in samples]
        print(self._name, {
            'seq': seq,
            'samples': [float(sample) for sample in samples],
        })
class Bits24:
    def __init__(self, device, name):
        self._device = device
        self._name = name
        self._characteristic = GATT_CHARACTERISTIC_UUIDS[name]
    async def init(self):
        self._gatt = await self._device.characteristic(PRIMARY_SERVICE, self._characteristic)
        await self._gatt.subscribe(self._recv)
    def _recv(self, data : bytes):
        seq = int.from_bytes(data[0:2], 'big', signed=False)
        samples = []
        for i in range(2, len(data), 3):
            samples.append(int.from_bytes(data[i:i+3], 'big', signed=False))
        #samples = [Fraction((sample * numerator, denominator) for sample in samples]
        print(self._name, {
            'seq': seq,
            'samples': [sample for sample in samples],
        })
class Imu:
    def __init__(self, device, name, characteristic, scale):
        self._device = device
        self._scale = scale
        self._name = name
        self._characteristic = characteristic
    async def init(self):
        self._gatt = await self._device.characteristic(PRIMARY_SERVICE, characteristic)
        await self._gatt.subscribe(self._recv)
        self._accum = []
    def _vector(self, data : bytes):
        return [
            int.from_bytes(data[0:2], 'big', signed=True) * self._scale,
            int.from_bytes(data[2:4], 'big', signed=True) * self._scale,
            int.from_bytes(data[4:6], 'big', signed=True) * self._scale
        ]
    def _recv(self, data : bytes):
        seq = int.from_bytes(data[0:2], 'big', signed=False)
        samples = [self._vector(data[2:8]), self._vector(data[8:14]), self._vector(data[14:20])]
        #self._accum.extend(samples)
        #if (len(self._accum) > 24):
        #    avg = []
        #    for a in range(len(self._accum[0])):
        #        total = 0
        #        for sample in self._accum:
        #            total += sample[a]
        #        avg.append(total / len(self._accum))
        #    self._accum = []
        print('imu', self._name, {
            'seq': seq,
            'samples': [[float(coord) for coord in sample] for sample in samples]
            #'avg': [float(coord) for coord in avg]
        })
class Accelerometer(Imu):
    # DONE FOR NOW
    def __init__(self, device):
        # result is in G's, proportion of gravity at sea level
        super().__init__(device, 'accelerometer', GATT_CHARACTERISTIC_UUIDS['ACCELEROMETER'], Fraction(1, 16384))

# what model is the IMU to verify these units?  what does an existing app output?
class Gyroscope(Imu):
    def __init__(self, device):
        # result may be in degrees/s
            # i'm not sure where this decimal comes from.
            # it's in the muse-js source code.  it doesn't multiply out to an integral
            # number of degrees, or units per 16-bit value, or anything.
        super().__init__(device, 'gyroscope', GATT_CHARACTERISTIC_UUIDS['GYRO'], Fraction(0.0074768))
        
class ChannelProbe:
    def __init__(self, device, name):
        self._name = name
    async def init(self):
        self._gatt = await self._device.characteristic(PRIMARY_SERVICE, GATT_CHARACTERISTIC_UUIDS[name])
        await self._gatt.subscribe(self._recv)

    async def probe(self, ctrl, presets):
        result = []
        for preset in presets:
            await ctrl.send('v1') # versions
            await ctrl.send(preset) # preset
            await ctrl.send('s') # status
            self._received = None
            await ctrl.send('d') # data
            bt_bluezero._pumploop.add_timer(10000, bt_bluezero.stop_pump)
            bt_bluezero.pump()
            await ctrl.send('h') # halt
            if self._received:
                result.append(preset)
            else:
                print('no', preset, self._name)
        #self._gatt.unsubscribe()
        return result
    def _recv(self, data : bytes):
        self._received = data

class Debug:
    def __init__(self, device, name):
        self._device = device
        self._name = name
    async def init(self):
        self._gatt = await self._device.characteristic(PRIMARY_SERVICE, GATT_CHARACTERISTIC_UUIDS[name])
        await self._gatt.subscribe(self._recv)
    def _recv(self, data : bytes):
        print('debug', self._name, int.from_bytes(data[0:2], 'big'), [x for x in data[2:]])


class Telemetry:
    # DONE FOR NOW
    def __init__(self, device):
        self._device = device
    async def init(self):
        self._gatt = await self._device.characteristic(PRIMARY_SERVICE, GATT_CHARACTERISTIC_UUIDS['BATTERY'])
        await self._gatt.subscribe(self._recv)
    def _recv(self, data : bytes):
        seq = int.from_bytes(data[0:2], 'big', signed=False)
        # battery is expected to contain a mv field, an adc mv field, a data enabled flag, a percentage remaining
        batt = Fraction(int.from_bytes(data[2:4], 'big', signed=False), 512)
        fuelgaugemv = Fraction(int.from_bytes(data[4:6], 'big', signed=False) * 10, 22)
        adcmv_maybe = int.from_bytes(data[6:8], 'big', signed=False)
        temp = int.from_bytes(data[8:10], 'big', signed=False)
        print('telemetry', {
            'seq': seq,
            'batt': float(batt),
            'fuelgauagemv': float(fuelgaugemv),
            'adcmv_maybe': adcmv_maybe,
            'temp': temp,
            'unknown': [i for i in data[10:]]
        })

class Ctrl:
    def __init__(self, device):
        self._data = b''
        self._recvd = []
        self._device = device
    async def init(self):
        self._gatt = await self._device.characteristic(PRIMARY_SERVICE, GATT_CHARACTERISTIC_UUIDS['SERIAL'])
        await self._gatt.subscribe(self._recv)
    async def status(self):
        result = await self.send('s')
        if 'rs' in result:
            result['running_state'] = result['rs']
            del result['rs']
        if 'ts' in result:
            result['test_mode'] = result['ts']
            del result['ts']
        result['preset'] = '%02X' % result['ps']
        del result['ps']
        result['sn']
        result['hn']
        result['id']
        result['bp']
        result['mac_address'] = result['ma']
        del result['ma']
        # hn, id, bp, ma, sn
        return result
    async def version(self, ver : int):
        # rc, ap, sp, tp, hw, bn, fw, bl, pv
        # bn is an integer
        result = await self.send('v' + str(ver))
        return result
    def _recv(self, data : bytes):
        data = data[1:data[0]+1]
        self._data += data
        if self._data[-1] == b'}'[0]:
            self._recvd.append(json.loads(self._data))
            self._resultevent.set()
            self._data = b''
    async def send(self, data : str):
        print('SERIAL ->', data)
        self._resultevent = asyncio.Event()
        await self._gatt.write(bytes([len(data) + 1, *(ord(character) for character in data), ord('\n')]))
        await self._resultevent.wait()
        result = self._recvd.pop(0)
        if result['rc'] == 0:
            return result
        else:
            # i'm not sure these error code names are right
            raise ValueError('invalid command', data, result, ['FAILURE','TIMEOUT','OVERLOADED','UNIMPLEMENTED'][result['rc']-1])
    #def recv(self):
    #    return self.data.pop(0)

import json
async def main():
    print('scanning for muses ...')
    iface = (await bt.interfaces())[0]

    devices = None
    await iface.start_scanning()
    while True:
        await asyncio.sleep(0.5)
        devlist = await iface.near_addresses()
        devices = [mac for mac, name in devlist if mac.startswith(MUSE_MAC_PREFIX)]
        print('found {} devices starting with {}: {}'.format(len(devices), MUSE_MAC_PREFIX, devices))
        devices = [await iface.device(mac) for mac in devices]
        devices = [device for device in devices if device]
        print('able to connect to {} of them: {}'.format(len(devices), devices))
        #devices = [device for device in (iface.device(mac) for mac, name in devlist if mac.startswith(MUSE_MAC_PREFIX)) if device]
        if len(devices):
            print('found')
            print('found {}'.format([device.info() for device in devices]))
            break
        else:
            print('... no connectable muses yet, {} other devices ... {}'.format(len(devlist), devlist))
    await iface.stop_scanning()

    device = devices[0]
    print('connected to {}'.format(device.info()))

    ctrl = Ctrl(device)
    await ctrl.init()
    
    # *1   boot to headset state
    # h    stop streaming / halt
    # d    start streaming (handlers initialised prior to send)
    # s    status / version check
    # vX   version,x=1
    # pXX  preset
    # k    keepalive, 2.5s timeout?
    
    #accel = bt_bluezero.Characteristic(device, PRIMARY_SERVICE, ACCELEROMETER_CHARACTERISTIC)
    #accel.subscribe(lambda data: print('accel', data))
    print('sending control stop command; if things freeze command sequence may need improvement')
    print(await ctrl.send('v1')) # version, maybe protocol version?
    print(await ctrl.send('h')) # stop streaming
    print(await ctrl.send('p63')) # preset
    #print(ctrl.send('s')) # status
    print(await ctrl.status())
    #print(ctrl.send('k')) # keepalive
    #print(ctrl.send('g408c'))
    #print(ctrl.send('?'))
    
    
    telemetry = Telemetry(device)
    await telemetry.init()
    
    #print('load')
    #debug= Debug(device, 'PPG_RED')
    eeg = Bits12(device, 'SIGNAL_FP2')
    await eeg.init()
    #debug = Debug(device, 'THERMISTOR')
    #gyroscope = Gyroscope(device)
    #accelerometer = Accelerometer(device)
    #eeg = {
    #    name: Bits12(device, name, GATT_CHARACTERISTIC_UUIDS[name])
    #    for name, characteristic in GATT_CHARACTERISTIC_UUIDS.items()
    #    if name.startswith('SIGNAL_') or name == 'DRL_REF'
    #}
    print(await ctrl.send('d')) # start streaming
    await asyncio.sleep(1)
    #bt_bluezero.pump()
if __name__ == '__main__':        
    asyncio.get_event_loop().run_until_complete(main())
