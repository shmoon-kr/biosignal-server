import io
import gzip
import struct
import csv
import datetime
import numpy as np

dt_datetime = np.dtype(datetime.datetime)
dt_str = np.dtype(str)
default_array_size = 65536

class vdevice:
    typename = None
    devname = None
    port = None

class vtrack:
    rec_type = None
    rec_fmt = None
    name = None
    unit = None
    minval = None
    maxval = None
    color = None
    srate = None
    adc_gain = None
    adc_offset = None
    mon_type = None 
    did = None
    dt = None
    val = None
    packet_size = None
    file_pointer = None
    packet_pointer = None
    string = None
    n = None


def sort_timestamp(val):
    return val[2]


def convert_binary_to_string(binary_list):
    r = list()
    for i in binary_list:
        r.append(i.decode('utf-8'))
    return r


class VitalFileHandler(object):

    def __init__(self, file):
        self.filename = file
        self.fp = gzip.open(file, "rb")
        self.devices = dict()
        self.tracks = dict()
        self.read_header()
        self.read_metadata()

    def get_gzip_size(self):
        with open(self.filename, 'rb') as f:
            f.seek(-4, 2)
            data = f.read(4)
        size = struct.unpack('<L', data)[0]
        return size

    def read_header(self):
        self.fp.seek(0)
        self.signature = self.fp.read(4)
        self.version = int.from_bytes(self.fp.read(4), byteorder="little", signed=False)
        self.headerlen = int.from_bytes(self.fp.read(2), byteorder="little", signed=False)
        self.tzbias = int.from_bytes(self.fp.read(2), byteorder="little", signed=False)
        self.inst_id = int.from_bytes(self.fp.read(4), byteorder="little", signed=False)
        self.prog_ver = int.from_bytes(self.fp.read(4), byteorder="little", signed=False)

    def write_track_info(self, filename):
        fieldnames = ['tid', 'did', 'rec_type', 'rec_format', 'name', 'unit', 'minval', 'maxval', 'color', 'srate', 'adc_gain', 'adc_offset', 'mon_type', 'dt_length', 'vn_length']
        with open(filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(fieldnames)
            for tid, track in self.tracks:
                csv_writer.writerow([track.did, tid, track.rec_type, track.rec_fmt, track.name, track.unit,
                                     track.minval, track.maxval, track.color, track.srate, track.adc_gain,
                                     track.adc_offset, track.mon_type, len(track.dt)])

    def write_device_info(self, filename):
        fieldnames = ['did', 'typename', 'devname', 'port']
        with open(filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(fieldnames)
            for did, device in self.devices:
                csv_writer.writerow([did, device.typename, device.devname, device.port])

    def get_device_info(self):
        r = list()
        for did, device in self.devices.items():
            r.append(device.typename)
        return r

    def get_track_info(self):
        r = list()
        for tid, track in self.tracks.items():
            r.append((self.devices[track.did].typename, track.name, track.rec_type, track.srate))
        return r

    def get_timestamp_range(self):
        min_dt = list()
        max_dt = list()
        for tid, track in self.tracks.items():
            if len(track.dt):
                min_dt.append(min(track.dt))
                max_dt.append(max(track.dt))
        return min(min_dt), max(max_dt)

    def read_metadata(self, timestamp='unix'):

        self.fp.seek(10 + self.headerlen)

        try:
            while True:
                file_loc = self.fp.tell()
                type = int.from_bytes(self.fp.read(1), byteorder="little", signed=False)
                datalen = int.from_bytes(self.fp.read(4), byteorder="little", signed=False)
                if datalen == 0:
                    break
                else:
                    packet_data = io.BytesIO(self.fp.read(datalen))
                    if type == 0:  # SAVE_TRKINFO
                        tid = int.from_bytes(packet_data.read(2), byteorder="little", signed=False)
                        self.tracks[tid] = vtrack()
                        tt = self.tracks[tid]
                        tt.rec_type = int.from_bytes(packet_data.read(1), byteorder="little", signed=False)
                        tt.rec_fmt = int.from_bytes(packet_data.read(1), byteorder="little", signed=False)
                        tt.name = packet_data.read(int.from_bytes(packet_data.read(4), byteorder="little", signed=False)).decode('utf-8')
                        tt.unit = packet_data.read(int.from_bytes(packet_data.read(4), byteorder="little", signed=False)).decode('utf-8')
                        tt.minval = struct.unpack('<f', packet_data.read(4))[0]
                        tt.maxval = struct.unpack('<f', packet_data.read(4))[0]
                        tt.color = packet_data.read(4)
                        tt.srate = struct.unpack('<f', packet_data.read(4))[0]
                        tt.adc_gain = struct.unpack('<d', packet_data.read(8))[0]
                        tt.adc_offset = struct.unpack('<d', packet_data.read(8))[0]
                        tt.mon_type = int.from_bytes(packet_data.read(1), byteorder="little", signed=False)
                        tt.did = int.from_bytes(packet_data.read(4), byteorder="little", signed=False)
                        tt.n = 0
                        tt.dt = np.empty(default_array_size, dtype=np.float64 if timestamp == 'unix' else dt_datetime)
                        if tt.rec_type == 2:
                            tt.val = np.empty(default_array_size, dtype=np.float)
                        elif tt.rec_type in (1, 6):
                            tt.packet_size = np.empty(default_array_size, dtype=np.int)
                            tt.file_pointer = np.empty(default_array_size, dtype=np.int)
                            tt.packet_pointer = np.empty(default_array_size, dtype=np.int)
                        elif tt.rec_type == 5:
                            tt.string = np.empty(default_array_size, dtype=dt_str)
                            tt.packet_size = np.empty(default_array_size, dtype=np.int)
                        else:
                            assert False, "Unknown rec_type %d in file %s." % (tt.rec_type, self.filename)

                    elif type == 1:  # SAVE_REC
                        p_infolen = int.from_bytes(packet_data.read(2), byteorder="little", signed=False)
                        p_dt = struct.unpack('<d', packet_data.read(8))[0]
                        tt = self.tracks[int.from_bytes(packet_data.read(2), byteorder="little", signed=False)]
                        if tt.rec_type in (1, 6): # Wave
                            if tt.n == len(tt.dt):
                                new_size = len(tt.dt) * 2
                                tt.dt.resize(new_size)
                                tt.packet_size.resize(new_size)
                                tt.file_pointer.resize(new_size)
                                tt.packet_pointer.resize(new_size)
                            num = int.from_bytes(packet_data.read(4), byteorder="little", signed=False)
                            tt.dt[tt.n] = p_dt
                            tt.packet_size[tt.n] = num
                            tt.packet_pointer[tt.n] = tt.packet_pointer[tt.n-1]+tt.packet_size[tt.n-1] if tt.n else 0
                            tt.file_pointer[tt.n] = file_loc
                            tt.n += 1

                        elif tt.rec_type == 2:  # Number
                            if tt.rec_fmt == 1:  # FMT_FLOAT
                                if tt.n == len(tt.dt):
                                    new_size = len(tt.dt) * 2
                                    tt.dt.resize(new_size)
                                    tt.val.resize(new_size)
                                value = struct.unpack('<f', packet_data.read(4))[0]
                                tt.dt[tt.n] = p_dt
                                tt.val[tt.n] = value
                                tt.n += 1
                            else:
                                print("Unknown Format, add codes")
                                exit(1)
                        elif tt.rec_type == 5:  # String
                            if tt.n == len(tt.dt):
                                new_size = len(tt.dt) * 2
                                tt.dt.resize(new_size)
                                tt.packet_size.resize(new_size)
                            tt.dt[tt.n] = p_dt
                            int.from_bytes(packet_data.read(4), byteorder="little", signed=False)
                            sval = packet_data.read(int.from_bytes(packet_data.read(4), byteorder="little", signed=False)).decode('utf-8')
                            tt.packet_size[tt.n] = len(sval)
                            tt.string[tt.n] = sval
                            tt.n += 1
                        else:
                            print("Unknown Record Type")
                            exit(1)

                    elif type == 6:  # SAVE_CMD
                        cmd = int.from_bytes(packet_data.read(1), byteorder="little", signed=False)
                        if cmd == 5:  # CMD_ORDER
                            cnt = int.from_bytes(packet_data.read(2), byteorder="little", signed=False)
                            tv = list()
                            for i in range(cnt):
                                tv.append(int.from_bytes(packet_data.read(2), byteorder="little", signed=False))
                        elif cmd == 6:  # CMD_RESET_EVENTS
                            print("Reset Events : code required")
                            # Do nothing
                        else:
                            print("Error. Unknown Command")
                            print(cmd)
                            exit(1)
                    elif type == 9:  # SAVE_DEVINFO
                        did = int.from_bytes(packet_data.read(4), byteorder="little", signed=False)
                        self.devices[did] = vdevice()
                        td = self.devices[did]
                        td.typename = packet_data.read(int.from_bytes(packet_data.read(4), byteorder="little", signed=False)).decode('utf-8')
                        td.devname = packet_data.read(int.from_bytes(packet_data.read(4), byteorder="little", signed=False)).decode('utf-8')
                        td.port = packet_data.read(int.from_bytes(packet_data.read(4), byteorder="little", signed=False)).decode('utf-8')

                    del packet_data

        except EOFError as e:
            print("Ignoring EOF Error.")
            print(e)

        for tid, track in self.tracks.items():
            if track.rec_type in (1, 2, 5, 6):
                track.dt.resize(track.n)
                if track.rec_type in (1, 6):
                    track.packet_size.resize(track.n)
                    track.file_pointer.resize(track.n)
                    track.packet_pointer.resize(track.n)
                elif track.rec_type == 2:
                    track.val.resize(track.n)
                elif track.rec_type == 5:
                    track.packet_size.resize(track.n)
                    track.string.resize(track.n)

    def export_number(self, device_list=None):
        if device_list is None:
            device_list = list()
        r = list()
        for tid, track in self.tracks.items():
            if track.rec_type == 2 and (not len(device_list) or self.devices[track.did].typename in device_list):
                for i, ti in enumerate(track.dt):
                    r.append([self.devices[track.did].typename, ti, track.name, track.val[i]])
        return r

    def export_wave(self, dev_type, track_name):
        for tid, track in self.tracks.items():
            if track.name == track_name and self.devices[track.did].typename == dev_type and track.rec_type in (1, 6):
                self.load_wave(tid)
                r = (track.dt, track.packet_pointer, track.val)
                del track.val
                return r
        return None

    def load_wave(self, tid):

        track = self.tracks[tid]
        track.val = np.empty(sum(track.packet_size), dtype=np.float32)
        for i, saved_fp in enumerate(track.file_pointer):
            self.fp.seek(saved_fp)
            type = int.from_bytes(self.fp.read(1), byteorder="little", signed=False)
            datalen = int.from_bytes(self.fp.read(4), byteorder="little", signed=False)
            assert datalen, 'Invalid datalen value.'
            assert type == 1, 'Invalid packet pointer.'
            packet_data = io.BytesIO(self.fp.read(datalen))
            p_infolen = int.from_bytes(packet_data.read(2), byteorder="little", signed=False)
            p_dt = struct.unpack('<d', packet_data.read(8))[0]
            p_tid = int.from_bytes(packet_data.read(2), byteorder="little", signed=False)
            assert track.dt[i] == p_dt
            assert tid == p_tid, 'Invalid track.'
            num = int.from_bytes(packet_data.read(4), byteorder="little", signed=False)
            if track.rec_fmt == 1:
                track.val[track.packet_pointer[i]:track.packet_pointer[i]+track.packet_size[i]] =\
                    list(struct.unpack('<'+'f'*num, packet_data.read(4*num)))
            elif track.rec_fmt == 5 or track.rec_fmt == 6:
                listval = list(struct.unpack('<'+'h'*num, packet_data.read(2*num))) # Little Endian
                for j, v in enumerate(listval):
                    track.val[track.packet_pointer[i]+j] = v
        return True
