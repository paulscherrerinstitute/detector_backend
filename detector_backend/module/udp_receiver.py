from logging import getLogger

import ctypes

import socket
from numpy.ctypeslib import as_ctypes
from numpy import array
import os
import sys

from detector_backend import config
from detector_backend.utils_detectors import get_n_bytes_per_submodule_line, get_n_bytes_per_frame_line, \
    get_n_packets_per_frame, get_n_lines_per_packet, \
    get_current_module_index, get_current_module_offset_in_pixels

_logger = getLogger("udp_receiver")

UDP_RCVBUF_SIZE = 1 * 1024 * 1024


class CDetectorSubmodule(ctypes.Structure):
    _fields_ = [
        ('submodule_index', ctypes.uint16_t),
        ('n_packets_per_frame', ctypes.uint16_t),

        ('bytes_per_packet', ctypes.uint32_t),
        ('bytes_data_per_packet', ctypes.uint32_t),

        ('submodule_data_slot_offset', ctypes.uint64_t)
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
        put_data_in_rb.argtypes = (ctypes.c_int, CRbMetadata, CDetectorSubmodule, ctypes.c_uint32, ctypes.c_float)
        put_data_in_rb.restype = ctypes.c_int

        return put_data_in_rb

    except:
        _logger.error("Could not load udp receiver shared library from %s." % expected_library_location)
        sys.exit(-1)


def get_c_det_submodule(detector_def, submodule_id):
    c_det_submodule = CDetectorSubmodule()
    c_det_submodule.submodule_index = submodule_id
    c_det_submodule.n_packets_per_frame = get_n_packets_per_frame(detector_def)

    detector_model = detector_def.detector_model

    c_det_submodule.bytes_per_packet = as_ctypes(
        array(detector_model.bytes_per_packet, dtype="uint32", order='C'))

    c_det_submodule.bytes_data_per_packet = as_ctypes(
        array(detector_model.bytes_data_per_packet, dtype="uint32", order='C'))

    c_det_submodule.submodule_data_slot_offset = \
        c_det_submodule.submodule_index * c_det_submodule.bytes_data_per_packet

    return c_det_submodule


def get_c_rb_metadata(detector_def, ringbuffer, module_id, submodule_id):
    c_rb_meta = CRbMetadata()

    c_rb_meta.rb_writer_id = ringbuffer.rb_consumer_id
    c_rb_meta.rb_header_id = ringbuffer.rb_header_id

    c_rb_meta.rb_hbuffer_id = ringbuffer.rb_hbuffer_id
    c_rb_meta.rb_dbuffer_id = ringbuffer.rb_dbuffer_id

    c_rb_meta.mod_origin = get_current_module_offset_in_pixels(detector_def, module_id, submodule_id)
    c_rb_meta.mod_number = get_current_module_index(detector_def, module_id, submodule_id)

    c_rb_meta.n_lines_per_packet = get_n_lines_per_packet(detector_def)
    c_rb_meta.n_packets_per_frame = get_n_packets_per_frame(detector_def)
    c_rb_meta.bit_depth = detector_def.bit_depth

    c_rb_meta.n_bytes_per_frame_line = get_n_bytes_per_frame_line(detector_def)
    c_rb_meta.n_bytes_per_submodule_line = get_n_bytes_per_submodule_line(detector_def)

    return c_rb_meta


def start_udp_receiver(udp_ip, udp_port, detector_def, submodule_id, ringbuffer, control_client):

    _logger.info("Starting udp_receiver with udp_ip='%s', udp_port=%d, submodule_id=%d" %
                 (udp_ip, udp_port, submodule_id))

    ringbuffer.init_buffer()

    _logger.debug("[%d] Ringbuffer initialized." % udp_port)

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_RCVBUF_SIZE)
    udp_socket.bind((udp_ip, udp_port))

    c_det_submodule = get_c_det_submodule(detector_def, submodule_id)
    c_rb_meta = get_c_rb_metadata(detector_def, ringbuffer, module_id, submodule_id)

    # Function signature
    # int sock, int bit_depth,
    # int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id,
    # uint32_t n_frames, float timeout, detector_definition det
    udp_receive = get_udp_receive_function()

    while True:

        _logger.debug("[%d] Starting udp_receive function." % udp_port)

        udp_receive(udp_socket.fileno(), c_rb_meta, c_det_submodule, config.MPI_COMM_DELAY)

        if control_client.is_message_ready():
            control_client.get_message()
            ringbuffer.reset()
            _logger.info("[%s] Ringbuffer reset." % udp_port)
