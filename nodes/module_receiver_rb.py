from __future__ import print_function, division  # , unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float, List, Bool, Unicode
from dafl.dataflow import DataFlowNode, DataFlow
from dafl.application import XblBaseApplication

import struct

import ringbuffer as rb
import ctypes

import socket
import numpy as np
import os
import sys

from time import time, sleep
from copy import copy


class DETECTOR(ctypes.Structure):
    _fields_ = [
        ('detector_name', 10 * ctypes.c_char),
        ('submodule_n', ctypes.c_uint8),
        ('detector_size', 2 * ctypes.c_int),
        ('module_size', 2 * ctypes.c_int),
        ('submodule_size', 2 * ctypes.c_int),
        ('module_idx', 2 * ctypes.c_int),
        ('submodule_idx', 2 * ctypes.c_int),
        ('gap_px_chips', 2 * ctypes.c_uint16),
        ('gap_px_modules', 2 * ctypes.c_uint16),
    ]

    gap_px_chips = [0, 0]
    gap_px_modules = [0, 0]


BUFFER_LENGTH = 4096
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6
INDEX_ARRAY = np.ctypeslib.as_ctypes(np.zeros(1024 * 512, dtype=np.int32))

# the C library receiving udp packets
try:
    # _mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/../libudpreceiver.so")
    _mod = ctypes.cdll.LoadLibrary(os.path.dirname(os.path.realpath(__file__)) + "/../libudpreceiver.so")

    put_data_in_rb = _mod.put_data_in_rb
    put_data_in_rb.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint32,
                                 ctypes.c_float, DETECTOR)
    put_data_in_rb.restype = ctypes.c_int

    put_data_in_rb.restype = ctypes.c_int
except:
    print(os.path.dirname(os.path.realpath(__file__)) + "/../libudpreceiver.so")
    print(sys.exc_info()[1])
    sys.exit(-1)

    
# not actually used, but I like it
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

    name = Unicode('Receiver', config=True)
    ip = Unicode('192.168.10.10', config=True, help="Ip to listen to for UDP packets")
    port = Int(9000, config=True, help="Port to listen to for UDP packets")
    module_size = List((512, 1024), config=True)
    submodule_size = List((512, 1024), config=True)
    geometry = List((1, 1), config=True)
    module_index = Int(0, config=True, help="Index within the detector, in the form of e.g. [[0,1,2,3][4,5,6,7]]")
    detector_size = List((-1, -1), config=True)
    detector_name = Unicode('', config=True)
    submodule_n = Int(1, config=True)
    submodule_index = Int(0, config=True, help="Index within the detector, in the form of e.g. [[0,1,2,3][4,5,6,7]]")

    gap_px_chips = List((0, 0), config=True)  # possibly not used
    gap_px_modules = List((0, 0), config=True)

    bit_depth = Int(16, config=True, help="")
    n_frames = Int(-1, config=True, help="Frames to receive")

    rb_id = Int(0, config=True, help="")
    rb_followers = List([1, ], config=True, help="")
    create_and_delete_ringbuffer_header = Bool(False, config=True, help="Index within the module, with NW=0 and SE=3")
    rb_head_file = Unicode('', config=True, help="")
    rb_imghead_file = Unicode('', config=True, help="")
    rb_imgdata_file = Unicode('', config=True, help="")

    def _prepare_ringbuffer_header_files(self):
        """Prepares the RB. An MPI barrier is needed to synchronize all the workers"""
        files = [self.rb_head_file, ]
        if self.create_and_delete_ringbuffer_header is True:
            self.log.info("create ringbuffer header files")
            for f in files:
                ret = rb.create_header_file(f)
                if not ret:
                    self.log.error("Ring buffer files do not exist!")
                    raise RuntimeError("Ring buffer files do not exist!")
                self.log.info("created %s", f)
            self.worker_communicator.barrier()
                
        else:
            self.log.info("wait for ringbuffer header files to become available")
            self.worker_communicator.barrier()
            for f in files:
                if not os.path.exists(f):
                    raise RuntimeError("file %s not available " % (f,))
    
    def __init__(self, **kwargs):
        super(ModuleReceiver, self).__init__(**kwargs)
        self.detector = DETECTOR()
        self.detector.detector_name = self.detector_name
        if self.detector_name == "":
            raise RuntimeError("No detector has been selected")
        self.detector.submodule_n  = self.submodule_n

        # FIXME: change to row and columnwise option
        # Column-first numeration
        if self.detector_name == "EIGER":
            mod_indexes = np.array([self.module_index % self.geometry[0], int(self.module_index / self.geometry[0])], dtype=np.int32, order='C')
        # Row-first numeration
        else:
            mod_indexes = np.array([int(self.module_index / self.geometry[1]), self.module_index % self.geometry[1]], dtype=np.int32, order='C')
    
        #if self.detector_size == [-1, -1]:
        #    self.detector_size = [self.module_size[0] * self.geometry[0], self.module_size[1] * self.geometry[1]]

        self.detector.detector_size = np.ctypeslib.as_ctypes(np.array(self.detector_size, dtype=np.int32, order='C'))
        self.detector.module_size = copy(np.ctypeslib.as_ctypes(np.array(self.module_size, dtype=np.int32, order='C')))
        self.detector.module_idx = copy(np.ctypeslib.as_ctypes(mod_indexes))

        self.detector.submodule_size = copy(np.ctypeslib.as_ctypes(np.array(self.submodule_size, dtype=np.int32, order='C')))
        self.detector.submodule_idx = copy(np.ctypeslib.as_ctypes(np.array([int(self.submodule_index / 2), self.submodule_index % 2], dtype=np.int32, order='C')))
        
        self.detector.gap_px_chips = copy(np.ctypeslib.as_ctypes(np.array(self.gap_px_chips, dtype=np.uint16, order="C")))
        self.detector.gap_px_modules = copy(np.ctypeslib.as_ctypes(np.array(self.gap_px_modules, dtype=np.uint16, order="C")))

        self.log.info("%s PID: %d IP: %s:%d" % (self.name, os.getpid(), self.ip, self.port))
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
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, self.geometry[0] * self.geometry[1] * self.submodule_n * 64)
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        nslots = rb.adjust_nslots(self.rb_header_id)

        if self.create_and_delete_ringbuffer_header:
            self.log.info("RB %d %d slots: %d" % (self.rb_header_id, self.rb_writer_id, nslots))
            self.log.info("RB header stride: %d" % rb.get_buffer_stride_in_byte(self.rb_hbuffer_id))
            self.log.info("RB data stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))

        self.rb_current_slot = ctypes.c_int(-1)

        self.n_packets_frame = 128
        self.period = 1

        self.total_modules = self.geometry[0] * self.geometry[1]
        if self.create_and_delete_ringbuffer_header:
            self.log.info("Packets per frame: %d" % self.n_packets_frame)

        self.log.info("Module index: %s" % [int(self.module_index / self.geometry[1]), self.module_index % self.geometry[1]])
        #print(self.n_elements_line, self.n_packets_frame)

    def send(self, data):
        n_recv_frames = 0

        # cframenum = ctypes.c_uint16(-1)
        # as C time() is seconds
        self.timeout = 1.0  #ctypes.c_int(max(int(2. * self.period), 1))
        #self.log.info("Timeout is %d" % self.timeout.value)

        # without the copy it seems that it is possible to point to the last allocated memory array
        n_recv_frames = put_data_in_rb(self.sock.fileno(), self.bit_depth, self.rb_current_slot, 
                                        self.rb_header_id, self.rb_hbuffer_id, self.rb_dbuffer_id, self.rb_writer_id, 
                                        self.n_frames, 
                                        self.timeout,
                                        self.detector
                                        )


        #if self.rb_current_slot.value != -1:
        self.log.debug("Current slot: %d" % self.rb_current_slot.value)
        #if n_recv_frames != 0:
        #    self.log.info("Received %d" % n_recv_frames)

        # FIXME
        # This means that the put_Data_in_rb routine was not able to get a slot
        #if rb.get_buffer_slot(self.rb_writer_id) == -1:
        #    self.log.error("Was not able to get a buffer slot: is Ringbuffer full???")

        if n_recv_frames != 0:
            self.log.info("Received %d frames" % n_recv_frames)

        self.pass_on(n_recv_frames)
        # needed
        return(n_recv_frames)

    def reconfigure(self, settings):
        super(ModuleReceiver, self).reconfigure(settings)
        #self.log.info(settings)

        rb.reset()

        self.log.info("Committed slots %s" % rb.get_header_info(self.rb_header_id).committed_slots[self.mpi_rank])

        if "period" in settings:
            self.period = settings["period"] / 1000000000
        if "n_frames" in settings:
            self.n_frames = settings["n_frames"]
        if "bit_depth" in settings:
            self.bit_depth = settings["bit_depth"]

        self._prepare_ringbuffer_header_files()

        rb.set_buffer_slot_dtype(dtype=ctypes.__getattribute__('c_uint' + str(self.bit_depth)))

        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_writer_id = rb.create_writer(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)

        # header data is 64b times n_modules. Each entry is a cache line owned by the receiving process
        # TODO add asserts / exceptions
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, self.geometry[0] * self.geometry[1] * self.submodule_n * 64)
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        nslots = rb.adjust_nslots(self.rb_header_id)
      
        if self.create_and_delete_ringbuffer_header:
            self.log.info("[%s] RB HeaderID: %d buffers: Header %d Data %d" % (self.name, self.rb_header_id, self.rb_hbuffer_id, self.rb_dbuffer_id))
            self.log.info("RB slots: %d" % nslots)
            self.log.info("RB header stride: %d" % rb.get_buffer_stride_in_byte(self.rb_hbuffer_id))
            self.log.info("RB data stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))

        self.rb_current_slot = ctypes.c_int(-1)

        self.n_packets_frame = 128
        self.period = 1

        self.total_modules = self.geometry[0] * self.geometry[1]

        if self.create_and_delete_ringbuffer_header:
            self.log.info("Packets per frame: %d" % self.n_packets_frame)

        # idx = define_quadrant(self.detector_size, self.geometry, self.module_index)
        # self.INDEX_ARRAY = np.ctypeslib.as_ctypes(idx)
        # print(self.INDEX_ARRAY[0], idx[0])
        # print("Receiver ID2: %d" % self.rb_writer_id)
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

        

