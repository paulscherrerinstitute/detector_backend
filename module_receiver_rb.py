from __future__ import print_function, division  # , unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float, List, Bool, Unicode
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

BUFFER_LENGTH = 4096
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6

CACHE_LINE_SIZE = 64

RB_HEAD_FILE = "rb_header.dat"
RB_IMGHEAD_FILE = "rb_image_header.dat"
RB_IMGDATA_FILE = "rb_image_data.dat"


# Jungfrau
class PACKET_STRUCT(ctypes.Structure):
    _pack_ = 2
    _fields_ = [
        ("emptyheader", HEADER_ARRAY),
        ("reserved", ctypes.c_uint32),
        ("packetnum2", ctypes.c_char),
        ("framenum2", 3 * ctypes.c_char),
        ("bunchid", ctypes.c_uint64),
        ("data", ctypes.c_uint16 * BUFFER_LENGTH),
        ("framenum", ctypes.c_uint16),
        ("packetnum", ctypes.c_uint8),
    ]

#packet = PACKET_STRUCT("      ".encode('utf-8'), ctypes.c_uint32(), " ".encode('utf-8'), " ".encode('utf-8'),
#                       ctypes.c_uint64(), DATA_ARRAY, ctypes.c_uint16(), ctypes.c_uint8())
packet = PACKET_STRUCT("      ", ctypes.c_uint32(), " ", "   ",
                       ctypes.c_uint64(), DATA_ARRAY, ctypes.c_uint16(), ctypes.c_uint8())

_mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/libudpreceiver.so")
get_message = _mod.get_message
get_message.argtypes = (ctypes.c_int, ctypes.POINTER(PACKET_STRUCT))
get_message.restype = ctypes.c_int


class HEADER(ctypes.Structure):
    _fields_ = [
        ("emptyheader", HEADER_ARRAY),
        ("framenum", ctypes.c_uint16),
        ("packetnum", ctypes.c_uint8),
        ("padding", ctypes.c_uint8 * (CACHE_LINE_SIZE - 6 - 2 - 1))
        ]

header = HEADER("      ", ctypes.c_uint16(), ctypes.c_uint8(),
                np.ctypeslib.as_ctypes(np.zeros(CACHE_LINE_SIZE - 6 - 2 - 1, dtype=np.uint8)))



class ModuleReceiver(DataFlowNode):
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    
    mpi_rank = comm.Get_rank()
    
    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    ip = Unicode('192.168.10.10', config=True, reconfig=True, help="Ip to listen to for UDP packets")
    port = Int(9000, config=True, reconfig=True, help="Port to listen to for UDP packets")
    module_size = List((512, 1024), config=True, reconfig=True)
    submodule_index = Int(0, config=True, reconfig=True, help="Index within the module, with NW=0 and SE=3")
    bit_depth = Int(16, config=True, reconfig=True, help="")
    n_frames = Int(-1, config=True, reconfig=True, help="Frames to receive")
    
    rb_id = Int(0, config=True, reconfig=True, help="")
    rb_followers = List([1, ], config=True, reconfig=True, help="")
    create_and_delete_ringbuffer_header = Bool(False, config=True, reconfig=True, help="Index within the module, with NW=0 and SE=3")
    rb_head_file = Unicode('', config=True, reconfig=True, help="")
    rb_imghead_file = Unicode('', config=True, reconfig=True, help="")
    rb_imgdata_file = Unicode('', config=True, reconfig=True, help="")

        
    def _prepare_ringbuffer_header_files(self):
        files = [self.rb_head_file, ]
        #print("MPI,", self.mpi_rank, self.create_and_delete_ringbuffer_header)
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

        # for setting up barriers
        app = XblBaseApplication.instance()
        self.worker_communicator = app.worker_communicator
        self._prepare_ringbuffer_header_files()

        self.sock = socket.socket(socket.AF_INET, # Internet
                             socket.SOCK_DGRAM) # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2000 * 1024 * 1024)
        self.sock.bind((self.ip, self.port))

        # setting the correct data pointer type
        rb.set_buffer_slot_dtype(dtype=ctypes.__getattribute__('c_uint' + str(self.bit_depth)))

        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_writer_id = rb.create_writer(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)

        self.log.debug("Receiver ID: %d" % self.rb_id)
        #print(rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, 2 * 512 * 1024))
        print(rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64))
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * self.module_size[0] * self.module_size[1])
        nslots = rb.adjust_nslots(self.rb_header_id)
        self.log.debug("RB slots: %d" % nslots)
        self.rb_current_slot = -1

        self.n_packets_frame = 128
        self.log.info("Packets per frame: %d" % self.n_packets_frame)
        #print(self.n_elements_line, self.n_packets_frame)
        
    def send(self, data):

        print("Receiver ID:", self.rb_id)
        counter = 0
        total_packets = 0
        framenum_last = -1
        t_i = time()

        #idx = select_quadrant(self.module_size, self.submodule_index)
        #print(idx.shape)
        #print(idx)
        if self.rb_current_slot == -1:
            self.rb_current_slot = rb.claim_next_slot(self.rb_writer_id)
        
        while True:
            try:
                if self.n_frames > 0  and counter > self.n_frames:
                    break
                
                # call the C code to get the frames
                nbytes = get_message(self.sock.fileno(), ctypes.byref(packet))
                #packet = UdpPacket()
                #rdata, sender = self.sock.recvfrom(2000 * 1024 * 1024)
                #data_size = len(rdata)
                #print("DATA_SIZE", data_size, counter)
                if nbytes == -1:
                    continue
                if framenum_last == -1:
                    framenum_last = packet.framenum

                #print("packet num, nbytes: %d %d" % (packet.framenum, nbytes))
                #print("-" + str(packet.framenum2))
                total_packets += 1

                # reconstruct and ship the image
                if packet.framenum != framenum_last:

                    if self.mpi_rank == 0:
                        self.log.debug("Total recv for frame %d: %d" % (packet.framenum, total_packets))
                    if total_packets != self.n_packets_frame:
                        self.log.warn("missing packets for frame %d (got %d)" % (packet.framenum, total_packets))

                    framenum_last = packet.framenum
                    total_packets = 0
                    
                    if not rb.commit_slot(self.rb_writer_id, self.rb_current_slot):
                        print("CANNOT COMMIT SLOT")
                    self.rb_current_slot = rb.claim_next_slot(self.rb_writer_id)
                    self.log.debug("WRITER: self.rb_current_slot %d" % self.rb_current_slot)
                    if self.rb_current_slot == -1:
                        while self.rb_current_slot == -1:
                            self.rb_current_slot = rb.claim_next_slot(self.rb_writer_id)

                    pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot), type(ctypes.pointer(header)))
                    header.framenum = packet.framenum
                    # see https://docs.python.org/3/library/ctypes.html#ctypes-pointers
                    # this copies data 
                    pointerh[0] = header
                    # this changes the pointer
                    #ph.contents = header
                    
                    if packet.framenum % 100 == 0:
                        print("Computed frame rate: %.2f Hz" % (100. / (time() - t_i)))
                        t_i = time()

                #packet.framenum, packet.packetnum, packet.data = unpack_data(rdata, self.bit_depth)
                self.log.debug("Frame, packet, size, sender: %d %d %d" % (packet.framenum, packet.packetnum, len(packet.data)))

                if framenum_last == -1:
                    framenum_last = packet.framenum

                #pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot), type(ctypes.pointer(header)))
                #= np.ctypeslib.as_array(pointer, (entry_size_in_bytes / 2,), )

                #if pointerh.contents.framenum == 0:
                #    header.framenum = packet.framenum
                #    pointerh[0] = header

                #print(pointerh.contents.framenum)
                #line = np.frombuffer(packet.data, np.uint16)[:1024]
                line = packet.data  # np.frombuffer(packet.data, np.uint16)
                pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
                entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
                data = np.ctypeslib.as_array(pointer, (int(entry_size_in_bytes / (self.bit_depth / 8)), ), )

                # dependng on submodule index, lines are sent in different order
                #if self.submodule_index % 2 == 0:
                #    idxn = idx.reshape(self.n_packets_frame, -1)[packet.packetnum - 1].ravel()
                #else:
                #    idxn = idx.reshape(self.n_packets_frame, -1)[self.n_packets_frame - packet.packetnum].ravel()

                line = np.frombuffer(packet.data, np.uint16)[:4096]
                data.reshape([128, 4096])[127 - packet.packetnum] = line
                #self.log.debug("data.shape, idxn.shape, max_index, line.shape: %s %s %d %s" % (data.shape, idxn.shape, idxn.max(), line.shape))
                #np.put(data, idxn, line)

            except KeyboardInterrupt:
                break
        self.pass_on("test")
        # needed
        return(1)
        
    def reset(self):
        pass


