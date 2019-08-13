from logging import getLogger

import ctypes

import socket
from numpy.ctypeslib import as_ctypes
from numpy import array
import os
import sys

from detector_backend import config
from detector_backend.utils_detectors import get_n_packets_per_frame

_logger = getLogger("udp_receiver")

UDP_RCVBUF_SIZE = 1 * 1024 * 1024


class CDetectorSubmodule(ctypes.Structure):
    _fields_ = [
        ('submodule_index', ctypes.c_uint16),
        ('n_packets_per_frame', ctypes.c_uint16),

        ('bytes_per_packet', ctypes.c_uint32),
        ('bytes_data_per_packet', ctypes.c_uint32),

        ('submodule_data_slot_offset', ctypes.c_uint64)
    ]


class CRbMetadata(ctypes.Structure):
    _fields_ = [
        ('rb_writer_id', ctypes.c_uint),
        ('rb_header_id', ctypes.c_uint),

        ('rb_hbuffer_id', ctypes.c_uint),
        ('rb_dbuffer_id', ctypes.c_uint),

        ('mod_origin', ctypes.c_uint32),
        ('mod_number', ctypes.c_uint),
        ('n_lines_per_packet', ctypes.c_uint),
        ('n_packets_per_frame', ctypes.c_uint),
        ('bit_depth', ctypes.c_uint),

        ('n_bytes_per_frame_line', ctypes.c_uint32),
        ('n_bytes_per_submodule_line', ctypes.c_uint32),
    ]


def get_udp_receive_function():
    expected_library_location = os.path.dirname(os.path.realpath(__file__)) + "/../../libudpreceiver.so"

    try:
        _mod = ctypes.cdll.LoadLibrary(expected_library_location)

        put_data_in_rb = _mod.put_data_in_rb
        put_data_in_rb.argtypes = (ctypes.c_int, CRbMetadata, CDetectorSubmodule, ctypes.c_float)
        put_data_in_rb.restype = ctypes.c_int

        return put_data_in_rb

    except:
        _logger.error("Could not load udp receiver shared library from %s." % expected_library_location)
        sys.exit(-1)


def get_c_det_submodule(detector_def, submodule_index):
    c_det_submodule = CDetectorSubmodule()
    c_det_submodule.submodule_index = submodule_index
    c_det_submodule.n_packets_per_frame = get_n_packets_per_frame(detector_def)

    detector_model = detector_def.detector_model

    c_det_submodule.bytes_per_packet = as_ctypes(
        array(detector_model.bytes_per_packet, dtype="uint32", order='C'))

    c_det_submodule.bytes_data_per_packet = as_ctypes(
        array(detector_model.bytes_data_per_packet, dtype="uint32", order='C'))

    c_det_submodule.submodule_data_slot_offset = \
        c_det_submodule.submodule_index * c_det_submodule.bytes_data_per_packet * c_det_submodule.n_packets_per_frame

    return c_det_submodule


def get_c_rb_metadata(ringbuffer):
    c_rb_meta = CRbMetadata()

    c_rb_meta.rb_writer_id = ringbuffer.rb_consumer_id
    c_rb_meta.rb_header_id = ringbuffer.rb_header_id

    c_rb_meta.rb_hbuffer_id = ringbuffer.rb_hbuffer_id
    c_rb_meta.rb_dbuffer_id = ringbuffer.rb_dbuffer_id

    return c_rb_meta


def start_udp_receiver(udp_ip, udp_port, detector_def, submodule_index, ringbuffer, control_client):

    _logger.info("Starting udp_receiver submodule_index=%d with udp_ip='%s', udp_port=%d, " %
                 (submodule_index, udp_ip, udp_port))

    ringbuffer.init_buffer()

    _logger.debug("[%d] Ringbuffer initialized." % udp_port)

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RCVBUF_SIZE)
    udp_socket.bind((udp_ip, udp_port))

    c_det_submodule = get_c_det_submodule(detector_def, submodule_index)
    c_rb_meta = get_c_rb_metadata(ringbuffer)

    # Function signature
    # int sock, rb_metadata rb_meta, detector_submodule det_submodule, float timeout
    udp_receive = get_udp_receive_function()

    while True:

        _logger.debug("[%d] Starting udp_receive function." % udp_port)

        udp_receive(udp_socket.fileno(), c_rb_meta, c_det_submodule, config.MPI_COMM_DELAY)

        if control_client.is_message_ready():
            control_client.get_message()
            ringbuffer.reset()
            _logger.info("[%s] Ringbuffer reset." % udp_port)
