from __future__ import print_function, division, unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float
from dafl.dataflow import DataFlowNode, DataFlow

import socket
import ctypes
import numpy as np
import os
import zmq

from time import time

BUFFER_LENGTH = 8214
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6


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
        ("data", ctypes.c_uint16 * BUFFER_LENGTH)]

packet = PACKET_STRUCT("      ".encode(), ctypes.c_uint64(), ctypes.c_uint64(), DATA_ARRAY)

_mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/libudpreceiver.so")
get_message = _mod.get_message
get_message.argtypes = (ctypes.c_int, ctypes.POINTER(PACKET_STRUCT))
get_message.restype = ctypes.c_int


class ModuleReceiver(DataFlowNode):

    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    ip = Unicode('192.168.10.1', config=True, reconfig=True, help="Ip to listen to for UDP packets")
    port = Int(9000, config=True, reconfig=True, help="Port to listen to for UDP packets")
    n_frames = Int(-1, config=True, reconfig=True, help="Frames to receive")
    
    def __init__(self, **kwargs):
        super(ModuleReceiver, self).__init__(**kwargs)

        self.sock = socket.socket(socket.AF_INET, # Internet
                             socket.SOCK_DGRAM) # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2000 * 1024 * 1024)
        self.sock.bind((self.ip, self.port))
        
        
    def send(self, data):
        image = np.zeros((512, 1024), dtype=np.uint16)
        counter = 0
        total_packets = 0
        framenum_last = -1
        t_i = time()

        while True:
            try:
                if self.n_frames > 0  and counter > self.n_frames:
                    break
                
                # call the C code to get the frames
                nbytes = get_message(self.sock.fileno(), ctypes.byref(packet))
                
                if nbytes == -1:
                    continue
                if framenum_last == -1:
                    framenum_last = packet.framenum

                total_packets += 1

                # reconstruct and ship the image
                if packet.framenum != framenum_last:
                    total_packets -= 1
                    if total_packets != 128 or packet.packetnum != 127:
                        #print(packet.framenum, packet.packetnum)
                        print("[WARNING] missing packets for frame %d (got %d)" % (packet.framenum, total_packets))
                        #error_counter += 1
                        #raise RuntimeException("aa")
                    if packet.framenum % 1 == 0 and image is not None:
                        #print("Full image ", packet.framenum)
                        # il reshape takes a lot of time...
                        self.pass_on([packet.framenum, image])
                        #send_array(writer_socket, image, copy=False, track=True, frame=packet.framenum)
                        framenum_last = packet.framenum
                        image = np.zeros((512, 1024), dtype=np.uint16)
                        total_packets = 1
                        counter += 1
                        if counter % 100 == 0:
                            print("Computed frame rate: %.2f Hz" % (100. / (time() - t_i)))
                            t_i = time()
                line = np.frombuffer(packet.data, np.uint16)[:4096]
                image.reshape([128, 4096])[127 - packet.packetnum] = line
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
    
    def __init__(self, **kwargs):
        super(ZMQSender, self).__init__(**kwargs)
        self.context = zmq.Context()
        self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        self.skt.bind(self.uri)
        
    def send(self, data):
        send_array(self.skt, data[1], copy=False, track=True, frame=data[0])
        #self.log.debug("send() got %s" % (data))
        #print(self.ip)
        #self.pass_on(data)

    def reset(self):
        pass
