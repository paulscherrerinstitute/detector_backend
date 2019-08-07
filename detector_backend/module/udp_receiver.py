from logging import getLogger

import ctypes

import socket
from numpy.ctypeslib import as_ctypes
from numpy import array
import os
import sys

from copy import copy

from detector_backend.mpi_control import MpiControlClient

_logger = getLogger("udp_receiver")

UDP_RCVBUF_SIZE = 10000 * 1024 * 1024


class CDetDef(ctypes.Structure):
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


def get_udp_receive_function():
    expected_library_location = os.path.dirname(os.path.realpath(__file__)) + "/../libudpreceiver.so"

    try:
        _mod = ctypes.cdll.LoadLibrary(expected_library_location)

        put_data_in_rb = _mod.put_data_in_rb

        put_data_in_rb.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_uint32, ctypes.c_float, CDetDef)

        put_data_in_rb.restype = ctypes.c_int

        return put_data_in_rb

    except:
        _logger.error("Could not load udp receiver shared library from %s." % expected_library_location)
        sys.exit(-1)


def get_c_det_def(detector_def, module_id, submodule_id):
    c_det_def = CDetDef()
    c_det_def.detector_name = detector_def.detector_name

    detector_model = detector_def.detector_model

    c_det_def.submodule_n = detector_model.n_submodules
    c_det_def.detector_size = as_ctypes(array(detector_def.detector_size, dtype="int32", order='C'))

    c_det_def.module_size = as_ctypes(array(detector_def.module_size, dtype="int32", order='C'))
    c_det_def.submodule_size = as_ctypes(array(detector_def.submodule_size, dtype="int32", order='C'))

    c_det_def.gap_px_chips = copy(as_ctypes(array(detector_def.gap_px_chips, dtype="uint16", order="C")))
    c_det_def.gap_px_modules = copy(as_ctypes(array(detector_def.gap_px_modules, dtype="uint16", order="C")))

    # FIXME: change to row and columnwise option
    # Column-first numeration
    if detector_model == "EIGER":
        mod_indexes = array([module_id % detector_model.geometry[0],
                             int(module_id / detector_model.geometry[0])], dtype="int32", order='C')
    # Row-first numeration
    else:
        mod_indexes = array([int(module_id / detector_model.geometry[1]),
                             module_id % detector_model.geometry[1]], dtype="int32", order='C')

    c_det_def.module_idx = as_ctypes(mod_indexes)
    c_det_def.submodule_idx = as_ctypes(array([int(submodule_id / 2), submodule_id % 2], dtype="int32", order='C'))

    return c_det_def


def start_udp_receiver(udp_ip, udp_port, detector_def, ringbuffer, module_id, submodule_id):

    _logger.info("Starting udp_receiver with udp_ip='%s', udp_port=%d, module_id=%d, submodule_id=%d" %
                 (udp_ip, udp_port, module_id, submodule_id))

    ringbuffer.init_buffer()

    _logger.debug("[%d] Ringbuffer initialized." % udp_port)

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RCVBUF_SIZE)
    udp_socket.bind((udp_ip, udp_port))

    c_det_def = get_c_det_def(detector_def, module_id, submodule_id)

    # Function signature
    # int sock, int bit_depth,
    # int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id,
    # uint32_t n_frames, float timeout, detector_definition det
    udp_receive = get_udp_receive_function()

    control_client = MpiControlClient()

    while True:

        _logger.debug("[%d] Starting udp_receive function." % udp_port)

        udp_receive(
            udp_socket.fileno(), detector_def.bit_depth,
            ringbuffer.rb_header_id, ringbuffer.rb_hbuffer_id, ringbuffer.rb_dbuffer_id, ringbuffer.rb_writer_id,
            -1, 1000, c_det_def
        )

        if control_client.is_message_ready():
            control_client.get_message()
            ringbuffer.reset()
            _logger.info("[%s] Ringbuffer reset." % udp_port)

        ringbuffer.reset()
        _logger.info("[%d] Ringbuffer reset." % udp_port)
