from __future__ import print_function, division, unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float, List, Bool
from dafl.dataflow import DataFlowNode, DataFlow
from dafl.application import XblBaseApplication

import struct

import ringbuffer as rb
import ctypes

import socket
import ctypes
import numpy as np
import os
import zmq

from time import time

BUFFER_LENGTH = 1024
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint32))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6

CACHE_LINE_SIZE = 64

RB_HEAD_FILE = "rb_header.dat"
RB_IMGHEAD_FILE = "rb_image_header.dat"
RB_IMGDATA_FILE = "rb_image_data.dat"

MODULE_SIZE = (512, 512)


def send_array(socket, A, flags=0, copy=True, track=False, frame=-1):
    """send a numpy array with metadata"""
    md = dict(
        htype=["array-1.0", ],
        type=str(A.dtype),
        shape=A.shape,
        frame=frame
    )
    socket.send_json(md, flags | zmq.SNDMORE)
    return socket.send(A, flags, copy=copy, track=track)



class PACKET_STRUCT(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("emptyheader", HEADER_ARRAY),
        ("framenum", ctypes.c_uint64),
        ("packetnum", ctypes.c_uint64),
        ("data", ctypes.c_uint32 * BUFFER_LENGTH)]

packet = PACKET_STRUCT("      ".encode(), ctypes.c_uint64(), ctypes.c_uint64(), DATA_ARRAY)

#_mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/libudpreceiver.so")
#get_message = _mod.get_message
#get_message.argtypes = (ctypes.c_int, ctypes.POINTER(PACKET_STRUCT))
#get_message.restype = ctypes.c_int


class HEADER(ctypes.Structure):
    _fields_ = [
        ("emptyheader", HEADER_ARRAY),
        ("framenum", ctypes.c_uint64),
        ("packetnum", ctypes.c_uint64),
        ("padding", ctypes.c_uint8 * (CACHE_LINE_SIZE - 6 - 8 - 8))
        ]

header = HEADER("      ".encode(), ctypes.c_uint64(), ctypes.c_uint64(),  np.ctypeslib.as_ctypes(np.zeros(CACHE_LINE_SIZE - 6 - 8 - 8, dtype=np.uint8)))


class UdpPacket(object):
    framenum = -1
    packetnum = -1
    data = None

    
def unpack_data(x, bit_depth=16):
    if bit_depth == 16:
        fmt = "IHBB2048H"
    elif bit_depth == 32:
        fmt = "IHBB1024I"
    elif bit_depth == 8:
        fmt = "IHBB4096B"
    rdata = struct.unpack(fmt, x[:-8])

    subframe_num = rdata[0]
    internal1 = rdata[1]
    memaddress = rdata[2]
    internal2 = rdata[3]
    data = np.array(rdata[4:], dtype='uint' + str(bit_depth))
    x1, x2, x3 = struct.unpack('<HIH', x[-8:])
    return x1 | (x2 << 16), x3, data

    
class ModuleReceiver(DataFlowNode):
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    
    mpi_rank = comm.Get_rank()
    
    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    ip = Unicode('192.168.10.10', config=True, reconfig=True, help="Ip to listen to for UDP packets")
    port = Int(9000, config=True, reconfig=True, help="Port to listen to for UDP packets")
    submodule_index = Int(0, config=True, reconfig=True, help="Index within the module, with NW=0 and SE=3")
    bit_depth = Int(32, config=True, reconfig=True, help="")
    n_frames = Int(-1, config=True, reconfig=True, help="Frames to receive")
    rb_id = Int(0, config=True, reconfig=True, help="")
    rb_followers = List([1, ], config=True, reconfig=True, help="")
    create_and_delete_ringbuffer_header = Bool(False, config=True, reconfig=True, help="Index within the module, with NW=0 and SE=3")


    def _prepare_ringbuffer_header_files(self):
        
        files = [RB_HEAD_FILE, ]
        print("MPI,", self.mpi_rank, self.create_and_delete_ringbuffer_header)
        if self.create_and_delete_ringbuffer_header is True:
            self.log.debug("create ringbuffer header files")
            for f in files:
                ret = rb.create_header_file(f)
                assert ret == True
                self.log.debug("created %s", f)
            self.worker_communicator.barrier()
                
        else:
            self.log.debug("wait for ringbuffer header files to become available")
            self.worker_communicator.barrier()
            for f in files:   
                if not os.path.exists(f) :
                    raise RuntimeError("file %s not available " % (f,))
    
    def __init__(self, **kwargs):
        super(ModuleReceiver, self).__init__(**kwargs)
        app = XblBaseApplication.instance()
        self.worker_communicator = app.worker_communicator

        self._prepare_ringbuffer_header_files()

        self.sock = socket.socket(socket.AF_INET, # Internet
                             socket.SOCK_DGRAM) # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2000 * 1024 * 1024)
        self.sock.bind((self.ip, self.port))
        # ringbuffer
        rb.set_buffer_slot_dtype(dtype=ctypes.c_uint32)
        #if self.rb_id == 0:
        #    _ = rb.create_header_file(RB_HEAD_FILE)
        self.rb_header_id = rb.open_header_file(RB_HEAD_FILE)
        #print(rb.print_header(self.rb_header_id))
        self.rb_writer_id = rb.create_writer(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(RB_IMGHEAD_FILE, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(RB_IMGDATA_FILE, self.rb_header_id, 0)

        print(rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64))
        print("Receiver ID:", self.rb_id)
        #print(rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, 2 * 512 * 1024))
        print(rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * 512 * 512))
        rb.adjust_nslots(self.rb_header_id);
        self.rb_current_slot = -1

        self.new_frame = True

        self.n_elements_line = int(8 * 4096 / self.bit_depth)
        self.n_packets_frame = int(MODULE_SIZE[0] * MODULE_SIZE[1] / 4 / self.n_elements_line)
        print(self.n_elements_line, self.n_packets_frame)
        
    def send(self, data):

        print("Receiver ID:", self.rb_id)
        counter = 0
        total_packets = 0
        framenum_last = -1
        t_i = time()

        if self.submodule_index == 0 or self.submodule_index == 1:
            if self.submodule_index == 0:
                idx_s = [i for i in range(int(MODULE_SIZE[0] / 2 ))]
            else:
                idx_s = [int(i + MODULE_SIZE[1] / 2) for i in range(int(MODULE_SIZE[0] / 2))]
            idx = idx_s
            for x in range(int(MODULE_SIZE[1] / 2 - 1)):
                idx = idx + [i + (x + 1) * MODULE_SIZE[1] for i in idx_s]
        elif self.submodule_index == 2 or self.submodule_index == 3:
            if self.submodule_index == 2:
                idx_s = [int(i + MODULE_SIZE[1]*MODULE_SIZE[0]/2)  for i in range(int(MODULE_SIZE[0] / 2))]
            else:
                idx_s = [int(i +  MODULE_SIZE[1] / 2  + MODULE_SIZE[1]*MODULE_SIZE[0]/2)  for i in range(int(MODULE_SIZE[0] / 2))]         
            idx = idx_s
            for x in range(int(MODULE_SIZE[1] / 2 - 1)):
                idx = idx + [i + (x + 1) * MODULE_SIZE[1] for i in idx_s]
        idx = np.array(idx)
        print(idx.shape)
        print(idx)
        if self.rb_current_slot == -1:
            self.rb_current_slot = rb.claim_next_slot(self.rb_writer_id)
        
        while True:
            try:
                if self.n_frames > 0  and counter > self.n_frames:
                    break
                
                # call the C code to get the frames
                #nbytes = get_message(self.sock.fileno(), ctypes.byref(packet))
                packet = UdpPacket()
                rdata, sender = self.sock.recvfrom(2000 * 1024 * 1024)
                data_size = len(rdata)
                print("DATA_SIZE", data_size, counter)
                
                if data_size == 48:
                    if counter == 0:
                        counter += 1
                        continue
                    #print("TESTL", packet.framenum, pointerh.contents.framenum)
                    
                    if total_packets != 64 or packet.packetnum != 63:
                        print("[WARNING] missing packets for frame %d (got %d)" % (packet.framenum, total_packets))
                        
                    framenum_last = packet.framenum
                    total_packets = 1
                    
                    if not rb.commit_slot(self.rb_writer_id, self.rb_current_slot):
                        print("CANNOT COMMIT SLOT")
                    self.rb_current_slot = rb.claim_next_slot(self.rb_writer_id)
                    #print("self.rb_current_slot", self.rb_current_slot)
                    pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot), type(ctypes.pointer(header)))
                    header.framenum = packet.framenum
                    # see https://docs.python.org/3/library/ctypes.html#ctypes-pointers
                    # this copies data 
                    pointerh[0] = header
                    # this changes the pointer
                    #ph.contents = header
                    
                    if counter % 1 == 0:
                        print("Computed frame rate: %.2f Hz" % (100. / (time() - t_i)))
                        t_i = time()
                else:
                    packet.framenum, packet.packetnum, packet.data = unpack_data(rdata, self.bit_depth)
                    print("framenum, packetnum, shape:", packet.framenum, packet.packetnum, packet.data.shape)
                    
                    #if nbytes == -1:
                    #    continue
                    if framenum_last == -1:
                        framenum_last = packet.framenum

                    total_packets += 1
                    pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot), type(ctypes.pointer(header)))
                    #= np.ctypeslib.as_array(pointer, (entry_size_in_bytes / 2,), )
                    
                    if pointerh.contents.framenum == 0:
                        header.framenum = packet.framenum
                        pointerh[0] = header
                        print("setup first header")
                        print("TESTS", packet.framenum, pointerh.contents.framenum)

                    #line = np.frombuffer(packet.data, np.uint16)[:1024]
                    line = packet.data  # np.frombuffer(packet.data, np.uint16)
                                       
                    pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
                   
                    entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
                    data = np.ctypeslib.as_array(pointer, (entry_size_in_bytes / (self.bit_depth / 8), ), )
                    
                    # dependng on submodule index, lines are sent in different order
                    if self.submodule_index % 2 == 0:
                        idxn = idx.reshape(self.n_packets_frame, -1)[packet.packetnum - 1].ravel()
                    else:
                        idxn = idx.reshape(self.n_packets_frame, -1)[self.n_packets_frame - packet.packetnum].ravel()
                   
                    #if self.submodule_index == 2:
                        #line = 42939842400 * np.ones(line.shape)
                    np.put(data, idxn, line)
                    #for ii, ix in enumerate(idxn):
                    #    data[ix] = line[ii]
                    
            except KeyboardInterrupt:
                break
        self.pass_on("test")
        # needed
        return(1)
        
    def reset(self):
        pass


class ZMQSender(DataFlowNode):

    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    uri = Unicode('tcp://192.168.10.1:9999', config=True, reconfig=True, help="URI which binds for ZMQ")
    socket_type = Unicode('PUSH', config=True, reconfig=True, help="ZMQ socket type")
    send_rate = Float(1, config=True, reconfig=True, help="Frame fraction to be sent")

    rb_id = Int(0, config=True, reconfig=True, help="")
    rb_followers = List([1, ], config=True, reconfig=True, help="")
    
    def __init__(self, **kwargs):
        super(ZMQSender, self).__init__(**kwargs)
        
        #self.rb_header_id = rb.open_header_file(RB_HEAD_FILE)
        #self.rb_reader_id = rb.create_reader(self.rb_header_id, self.rb_id, self.rb_followers)
        #self.rb_hbuffer_id = rb.attach_buffer_to_header(RB_IMGHEAD_FILE, self.rb_header_id, 0)
        #self.rb_dbuffer_id = rb.attach_buffer_to_header(RB_IMGDATA_FILE, self.rb_header_id, 0)

        #self.context = zmq.Context()
        #self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        #self.skt.bind(self.uri)

        self.rb_current_slot = -1

        print("READER:",)
        
    def send(self, data):
        #send_array(self.skt, data[1], copy=False, track=True, frame=data[0])
        #print("0MQ data:", data)
        self.pass_on(1)
        #self.log.debug("send() got %s" % (data))
        #print(self.ip)
        #self.pass_on(data)
        return(1)
    
        while True:
            self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)
            if self.rb_current_slot == -1:
                continue
            print("self.rb_current_slot", self.rb_current_slot)
            pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot), type(ctypes.pointer(header)))
            print("pointerh.contents.framenum", pointerh.contents.framenum)
            pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
                   
            entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
            data = np.ctypeslib.as_array(pointer, (entry_size_in_bytes / (self.bit_depth / 8), ), )
            print(data.shape, data.sum())
            if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                print("CANNOT COMMIT SLOT")
            
        self.pass_on(1)
        #self.log.debug("send() got %s" % (data))
        #print(self.ip)
        #self.pass_on(data)
        return(1)
    
    def reset(self):
        pass
