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
import sys

from time import time, sleep
from copy import copy

BUFFER_LENGTH = 4096
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6
INDEX_ARRAY = np.ctypeslib.as_ctypes(np.zeros(1024 * 512, dtype=np.int32))

CACHE_LINE_SIZE = 64

RB_HEAD_FILE = "rb_header.dat"
RB_IMGHEAD_FILE = "rb_image_header.dat"
RB_IMGDATA_FILE = "rb_image_data.dat"


_mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/libudpreceiver.so")

put_data_in_rb = _mod.put_data_in_rb
# put_data_in_rb.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int32), ctypes.c_int16)
put_data_in_rb.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32, 2 * ctypes.c_int32, 2 * ctypes.c_int32, 2 * ctypes.c_int32, 2 * ctypes.c_int32, 2 * ctypes.c_int32, ctypes.c_int32)
put_data_in_rb.restype = ctypes.c_int


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
    return np.array(q_idx, dtype=np.int32, order="C")


class ModuleReceiver(DataFlowNode):
    from mpi4py import MPI
    comm = MPI.COMM_WORLD

    mpi_rank = comm.Get_rank()

    ip = Unicode('192.168.10.10', config=True, help="Ip to listen to for UDP packets")
    port = Int(9000, config=True, help="Port to listen to for UDP packets")
    module_size = List((512, 1024), config=True)
    geometry = List((1, 1), config=True)
    module_index = Int(0, config=True, help="Index within the detector, in the form of e.g. [[0,1,2,3][4,5,6,7]]")

    gap_px_chip = List((0, 0), config=True)  # possibly not used
    gap_px_module = List((0, 0), config=True)

    bit_depth = Int(16, config=True, help="")
    n_frames = Int(-1, config=True, help="Frames to receive")

    rb_id = Int(0, config=True, help="")
    rb_followers = List([1, ], config=True, help="")
    create_and_delete_ringbuffer_header = Bool(False, config=True, help="Index within the module, with NW=0 and SE=3")
    rb_head_file = Unicode('', config=True, help="")
    rb_imghead_file = Unicode('', config=True, help="")
    rb_imgdata_file = Unicode('', config=True, help="")

    def _prepare_ringbuffer_header_files(self):
        files = [self.rb_head_file, ]
        if self.create_and_delete_ringbuffer_header is True:
            self.log.info("create ringbuffer header files")
            for f in files:
                ret = rb.create_header_file(f)
                if not ret:
                    self.log.error("Ring buffer files do not exist!")
                    raise RuntimeError("Ring buffer files do not exist!")
                self.log.debug("created %s", f)
            self.worker_communicator.barrier()
                
        else:
            self.log.info("wait for ringbuffer header files to become available")
            self.worker_communicator.barrier()
            for f in files:
                if not os.path.exists(f):
                    raise RuntimeError("file %s not available " % (f,))
    
    def __init__(self, **kwargs):
        super(ModuleReceiver, self).__init__(**kwargs)
        #self.detector_size = [(self.module_size[0] + self.gap_px_chip[0]) * self.geometry[0], (self.module_size[1] + self.gap_px_chip[1]) * self.geometry[1]]
        self.detector_size = [self.module_size[0] * self.geometry[0], self.module_size[1] * self.geometry[1]]

        self.log.info("PID: %d IP: %s:%d" % (os.getpid(), self.ip, self.port))
        # for setting up barriers
        app = XblBaseApplication.instance()
        self.worker_communicator = app.worker_communicator
        self._prepare_ringbuffer_header_files()

        self.sock = socket.socket(socket.AF_INET,  # Internet
                                  socket.SOCK_DGRAM)  # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, str(10000 * 1024 * 1024))
        self.sock.bind((self.ip, self.port))

        # setting the correct data pointer type
        rb.set_buffer_slot_dtype(dtype=ctypes.__getattribute__('c_uint' + str(self.bit_depth)))

        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_writer_id = rb.create_writer(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)

        # header data is 64b times n_modules. Each entry is a cache line owned by the receiving process
        # TODO add asserts / exceptions
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, self.geometry[0] * self.geometry[1] * 64)
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        nslots = rb.adjust_nslots(self.rb_header_id)
        self.log.info("RB slots: %d" % nslots)
        self.log.info("RB header stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))
        self.log.info("RB data stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))
        self.rb_current_slot = ctypes.c_int(-1)

        self.n_packets_frame = 128
        self.period = 1

        self.total_modules = self.geometry[0] * self.geometry[1]
        self.log.info("Packets per frame: %d" % self.n_packets_frame)
        # idx = define_quadrant(self.detector_size, self.geometry, self.module_index)
        # self.INDEX_ARRAY = np.ctypeslib.as_ctypes(idx)
        # print(self.INDEX_ARRAY[0], idx[0])
        print("Receiver ID2: %d" % self.rb_writer_id)
        self.log.info("Module index: %s" % [int(self.module_index / self.geometry[1]), self.module_index % self.geometry[1]])
        #print(self.n_elements_line, self.n_packets_frame)

    def send(self, data):
        self.log.debug("Opened")
        n_recv_frames = 0

        # cframenum = ctypes.c_uint16(-1)
        # as C time() is seconds
        self.timeout = 1  #ctypes.c_int(max(int(2. * self.period), 1))
        #self.log.info("Timeout is %d" % self.timeout.value)

        # without the copy it seems that it is possible to point to the last allocated memory array
        mod_indexes = np.array([int(self.module_index / self.geometry[1]), self.module_index % self.geometry[1]], dtype=np.int32, order='C')
        det_size = copy(np.ctypeslib.as_ctypes(np.array(self.detector_size, dtype=np.int32, order='C')))
        mod_size = copy(np.ctypeslib.as_ctypes(np.array(self.module_size, dtype=np.int32, order='C')))
        mod_idx = copy(np.ctypeslib.as_ctypes(mod_indexes))
        gap_px_chip_c = copy(np.ctypeslib.as_ctypes(np.array(self.gap_px_chip, dtype=np.int32, order='C')))
        gap_px_module_c = copy(np.ctypeslib.as_ctypes(np.array(self.gap_px_module, dtype=np.int32, order='C')))

        #int put_data_in_rb(int sock, int bit_depth, int *rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, uint32_t nframes, int32_t det_size[2], int32_t *mod_size, int32_t *mod_idx, int timeout, int32_t *gap_px_chips, int32_t *gap_px_modules){

        n_recv_frames = put_data_in_rb(self.sock.fileno(), self.bit_depth, ctypes.byref(self.rb_current_slot),
                                       self.rb_header_id, self.rb_hbuffer_id, self.rb_dbuffer_id, self.rb_writer_id,
                                       self.n_frames, self.total_modules, det_size, mod_size, mod_idx, gap_px_chip_c, gap_px_module_c, self.timeout)

        if self.rb_current_slot.value != -1:
            self.log.debug("Current slot: %d" % self.rb_current_slot.value)
        if n_recv_frames != 0:
            self.log.info("Received %d" % n_recv_frames)

        # FIXME
        # This means that the put_Data_in_rb routine was not able to get a slot
        #if rb.get_buffer_slot(self.rb_writer_id) == -1:
        #    self.log.error("Was not able to get a buffer slot: is Ringbuffer full???")

        self.pass_on(n_recv_frames)
        # needed
        return(n_recv_frames)

    def reconfigure(self, settings):
        super(ModuleReceiver, self).reconfigure(settings)
        #self.log.info(settings)
        if "period" in settings:
            self.period = settings["period"] / 1000000000
        if "n_frames" in settings:
            self.n_frames = settings["n_frames"]
        self._prepare_ringbuffer_header_files()

        rb.set_buffer_slot_dtype(dtype=ctypes.__getattribute__('c_uint' + str(self.bit_depth)))

        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_writer_id = rb.create_writer(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)

        # header data is 64b times n_modules. Each entry is a cache line owned by the receiving process
        # TODO add asserts / exceptions
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, self.geometry[0] * self.geometry[1] * 64)
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        nslots = rb.adjust_nslots(self.rb_header_id)
        self.log.info("RB slots: %d" % nslots)
        self.log.info("RB header stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))
        self.log.info("RB data stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))
        self.rb_current_slot = ctypes.c_int(-1)

        self.n_packets_frame = 128
        self.period = 1

        self.total_modules = self.geometry[0] * self.geometry[1]
        self.log.info("Packets per frame: %d" % self.n_packets_frame)
        # idx = define_quadrant(self.detector_size, self.geometry, self.module_index)
        # self.INDEX_ARRAY = np.ctypeslib.as_ctypes(idx)
        # print(self.INDEX_ARRAY[0], idx[0])
        print("Receiver ID2: %d" % self.rb_writer_id)
        self.log.info("Module index: %s" % [int(self.module_index / self.geometry[1]), self.module_index % self.geometry[1]])
        #print(self.n_elements_line, self.n_packets_frame)


    def reset(self):
        super(ModuleReceiver, self).reset()
        #self.log.info("Restarting the socket connection")
        #self.sock.shutdown(socket.SHUT_RD)
        #self.sock.close()
        #self.sock = socket.socket(socket.AF_INET,  # Internet
        #                          socket.SOCK_DGRAM)  # UDP
        #self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, str(10000 * 1024 * 1024))
        #self.sock.bind((self.ip, self.port))
        #self.log.info("Socket connection restarted")
        rb.reset()

        

