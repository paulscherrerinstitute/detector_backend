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

from time import time, sleep

BUFFER_LENGTH = 4096
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6
INDEX_ARRAY = np.ctypeslib.as_ctypes(np.zeros(1024 * 512, dtype=np.int32))

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
put_udp_in_rb = _mod.put_udp_in_rb
put_udp_in_rb.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_uint16))
put_udp_in_rb.restype = ctypes.c_int

put_data_in_rb = _mod.put_data_in_rb
put_data_in_rb.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int32), ctypes.c_int16)
put_data_in_rb.restype = ctypes.c_int


class HEADER(ctypes.Structure):
    _fields_ = [
        ("framenum", ctypes.c_uint16),
        ("packetnum", ctypes.c_uint8),
        ("padding", ctypes.c_uint8 * (CACHE_LINE_SIZE - 2 - 1))
        ]

header = HEADER(ctypes.c_uint16(), ctypes.c_uint8(),
                np.ctypeslib.as_ctypes(np.zeros(CACHE_LINE_SIZE - 2 - 1, dtype=np.uint8)))


def define_quadrant(total_size, geometry, quadrant_index, index_axis=0):
    """
    Geometry is the module placement (e.g. 3x2)
    """
    L, H = total_size
    m, n = geometry
    if L % m != 0 or H % n != 0:
        print("not supported")
        return None
    # get the base module
    module_size = (int(L / m), int(H / n))
    line = [x for x in range(module_size[1])]
    # fills the base module
    base_q = line
    base_q = np.ndarray(module_size[0] * module_size[1], dtype=np.int64).reshape(module_size[0], module_size[1])
    for i in range(0, module_size[0]):
        base_q[i] = np.array(line) + i * H
    # get the module index
    # module index grows on the first index
    if index_axis == 0:
        module_indices = np.arange(m * n).reshape(np.array(geometry)[::-1]).T
    else:
        module_indices = np.arange(m * n).reshape(geometry)
    module_index = np.argwhere(module_indices == quadrant_index)
    if len(module_index) == 0:
        print("wrong module index, can me max: ", module_indices, quadrant_index)
        return None
    h_i, l_i = module_index[0]
    # do the required translations
    base_q = [x + module_size[1] * l_i + module_size[0] * h_i * H for x in base_q.ravel()]
    q_idx = base_q
    return np.array(q_idx,  dtype=np.int32, order="C")



class ModuleReceiver(DataFlowNode):
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    
    mpi_rank = comm.Get_rank()
    
    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    ip = Unicode('192.168.10.10', config=True, reconfig=True, help="Ip to listen to for UDP packets")
    port = Int(9000, config=True, reconfig=True, help="Port to listen to for UDP packets")
    module_size = List((512, 1024), config=True, reconfig=True)
    geometry = List((1, 1), config=True, reconfig=True)
    module_index = Int(0, config=True, reconfig=True, help="Index within the detector, in the form of e.g. [[0,1,2,3][4,5,6,7]]")

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
        self.detector_size = [self.module_size[0] * self.geometry[0], self.module_size[1] * self.geometry[1]]

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

        print("Receiver ID: %d" % self.rb_writer_id)
        #print(rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, 2 * 512 * 1024))
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64)
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        nslots = rb.adjust_nslots(self.rb_header_id)
        self.log.debug("RB slots: %d" % nslots)
        self.rb_current_slot = -1

        self.n_packets_frame = 128
        self.log.info("Packets per frame: %d" % self.n_packets_frame)
        idx = define_quadrant(self.detector_size, self.geometry, self.module_index)
        self.INDEX_ARRAY = np.ctypeslib.as_ctypes(idx)
        print(self.INDEX_ARRAY[0], idx[0])
        print("Receiver ID2: %d" % self.rb_writer_id)
        #print(self.n_elements_line, self.n_packets_frame)
        
    def send(self, data):

        #print("Receiver ID:", self.rb_id)
        counter = 0
        total_packets = 0
        framenum_last = -1
        t_i = time()
        n_recv_frames = 0
        lost_frames = 0
        tot_lost_frames = 0
        
        cframenum = ctypes.c_uint16(-1)

        print("A", self.mpi_rank, self.rb_header_id, self.rb_hbuffer_id, self.rb_dbuffer_id, self.rb_writer_id)
        ret = put_data_in_rb(self.sock.fileno(), self.bit_depth, self.rb_current_slot, self.rb_header_id, self.rb_hbuffer_id, self.rb_dbuffer_id, self.rb_writer_id, self.INDEX_ARRAY, self.n_frames)

        print("OUTTTTT")
        while True:
            try:
                if self.n_frames > 0 and counter > self.n_frames:
                    break
                
                # call the C code to get the frames
                #nbytes = get_message(self.sock.fileno(), ctypes.byref(packet))
                ret = put_udp_in_rb(self.sock.fileno(), self.bit_depth, self.rb_current_slot, self.rb_header_id, self.rb_hbuffer_id, self.rb_dbuffer_id, self.rb_writer_id, self.INDEX_ARRAY, ctypes.byref(cframenum))
                # possible new function
                
                if ret == -1:
                    continue

                self.rb_current_slot = ret  # , framenum = np.ctypeslib.as_array(ret, (2, ), )
                #pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot),
                #                       type(ctypes.pointer(header)))
                
                #framenum = pointerh.contents.framenum
                #framenum = cframenum.value
                if framenum_last == -1:
                    framenum_last = cframenum.value
                total_packets += 1
                
                # reconstruct and ship the image
                if cframenum.value != framenum_last or total_packets == self.n_packets_frame:
                    self.log.debug("%d %d" % (0, cframenum.value))

                    if self.mpi_rank == 0:
                        self.log.debug("Total recv for frame %d: %d" % (framenum_last, total_packets))
                    if total_packets != self.n_packets_frame:
                        lost_frames += 1
                        tot_lost_frames += 1
                        self.log.debug("missing packets for frame %d (got %d)" % (framenum_last, total_packets))
                    if total_packets == self.n_packets_frame:
                        framenum_last = -1
                    else:
                        framenum_last = cframenum.value
                    total_packets = 0
                    n_recv_frames += 1

                    if n_recv_frames % 1000 == 0:
                        print("Computed frame rate at frame %d: %.2f Hz Lost frames: %d (%d)" % (cframenum.value, 1000. / (time() - t_i), lost_frames, tot_lost_frames))
                        t_i = time()
                        lost_frames = 0

            except KeyboardInterrupt:
                raise StopIteration

        self.pass_on(n_recv_frames)
        # needed
        return(n_recv_frames)
        
    def reset(self):
        pass


