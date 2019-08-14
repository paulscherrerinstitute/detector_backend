import ctypes
import os
import socket

import numpy

import ringbuffer as rb
from detector_backend import config

from detector_backend.mpi_ringbuffer import MpiRingBufferClient, MpiRingBufferMaster


class MockRingBufferMaster(MpiRingBufferMaster):

    def create_buffer(self):

        ret = rb.create_header_file(self.rb_header_file)

        if not ret:
            raise RuntimeError("Cannot create ringbuffer header file.")

        self.rb_header_id = rb.open_header_file(self.rb_header_file)

    def reset_header(self):
        rb.reset_header(self.rb_header_id)


class MockRingBufferClient(MpiRingBufferClient):

    def init_buffer(self):
        self._configure_buffer()

    def reset(self):
        pass


class MockControlClient(object):

    def is_message_ready(self):
        pass

    def get_message(self):
        pass


class CEigerPacket(ctypes.Structure):

    N_BYTES_DATA = 4096

    _fields_ = [
        ('framenum', ctypes.c_uint64),
        ('exptime', ctypes.c_uint32),
        ('packetnum', ctypes.c_uint32),

        ('bunchid', ctypes.c_double),
        ('timestamp', ctypes.c_uint64),

        ('moduleID', ctypes.c_uint16),
        ('xCoord', ctypes.c_uint16),
        ('yCoord', ctypes.c_uint16),
        ('zCoord', ctypes.c_uint16),

        ('debug', ctypes.c_uint32),
        ('roundRobin', ctypes.c_uint16),

        ('detectortype', ctypes.c_uint8),
        ('headerVersion', ctypes.c_uint8),

        ('data', N_BYTES_DATA * ctypes.c_char)
    ]


def generate_submodule_eiger_packets(bit_depth, n_frames, debug=0):

    total_frame_bytes = (256 * 512 * bit_depth) // 8
    n_packets = total_frame_bytes // CEigerPacket.N_BYTES_DATA
    n_pixels_per_packet = (CEigerPacket.N_BYTES_DATA * 8) // bit_depth

    data = numpy.zeros(shape=[n_pixels_per_packet], dtype="uint" + str(bit_depth))

    for framenum in range(n_frames):
        for packetnum in range(n_packets):
            c_eiger_packet = CEigerPacket()

            c_eiger_packet.framenum = framenum + 1
            c_eiger_packet.bunchid = framenum
            c_eiger_packet.packetnum = packetnum
            c_eiger_packet.debug = debug

            data.fill(packetnum)
            c_eiger_packet.data = data.tobytes()

            yield c_eiger_packet


def generate_udp_stream(udp_ip, udp_port, message_generator):

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    for message in message_generator:
        udp_socket.sendto(message, (udp_ip, udp_port))

    udp_socket.close()


def cleanup_rb_files():
    if os.path.isfile(config.DEFAULT_RB_HEAD_FILE):
        os.remove(config.DEFAULT_RB_HEAD_FILE)

    if os.path.isfile(config.DEFAULT_RB_IMAGE_HEAD_FILE):
        os.remove(config.DEFAULT_RB_IMAGE_HEAD_FILE)

    if os.path.isfile(config.DEFAULT_RB_IMAGE_DATA_FILE):
        os.remove(config.DEFAULT_RB_IMAGE_DATA_FILE)