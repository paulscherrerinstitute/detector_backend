from __future__ import print_function, division, unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float, List, Bool, Unicode
from dafl.dataflow import DataFlowNode, DataFlow
from dafl.application import XblBaseApplication
#import matplotlib.pyplot as plt

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

CACHE_LINE_SIZE = 64

class HEADER(ctypes.Structure):
    _fields_ = [
        ("framenum", ctypes.c_uint16),
        ("packetnum", ctypes.c_uint8),
        ("padding", ctypes.c_uint8 * (CACHE_LINE_SIZE - 2 - 1))
        ]

header = HEADER(ctypes.c_uint16(), ctypes.c_uint8(),  np.ctypeslib.as_ctypes(np.zeros(CACHE_LINE_SIZE - 2 - 1, dtype=np.uint8)))


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



class ZMQSender(DataFlowNode):

    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    uri = Unicode('tcp://192.168.10.1:9999', config=True, reconfig=True, help="URI which binds for ZMQ")
    socket_type = Unicode('PUB', config=True, reconfig=True, help="ZMQ socket type")
    send_rate = Float(1, config=True, reconfig=True, help="Frame fraction to be sent")
    module_size = List((512, 1024), config=True, reconfig=True)
    geometry = List((1, 1), config=True, reconfig=True)

    rb_id = Int(0, config=True, reconfig=True, help="")
    rb_followers = List([1, ], config=True, reconfig=True, help="")
    bit_depth = Int(16, config=True, reconfig=True, help="")

    rb_head_file = Unicode('', config=True, reconfig=True, help="")
    rb_imghead_file = Unicode('', config=True, reconfig=True, help="")
    rb_imgdata_file = Unicode('', config=True, reconfig=True, help="")

    def __init__(self, **kwargs):
        super(ZMQSender, self).__init__(**kwargs)
        self.detector_size = [self.module_size[0] * self.geometry[0], self.module_size[1] * self.geometry[1]]
        app = XblBaseApplication.instance()
        self.worker_communicator = app.worker_communicator
        self.worker_communicator.barrier()
        
        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_reader_id = rb.create_reader(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64)

        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id,
                                           int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        rb.adjust_nslots(self.rb_header_id)
        
        self.context = zmq.Context()
        self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        self.skt.bind(self.uri)

        self.rb_current_slot = -1

        print("READER:",)
        
    def send(self, data):    
        while True:
            try:
                self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)

                if self.rb_current_slot == -1:
                    continue
                self.log.debug("READER: self.rb_current_slot" + str(self.rb_current_slot))

                pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot), type(ctypes.pointer(header)))
                pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
                
                self.log.debug("WRITER " +  str(pointerh.contents.framenum))

                entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
                data = np.ctypeslib.as_array(pointer, (int(entry_size_in_bytes / (self.bit_depth / 8)), ), )
                send_array(self.skt, data.reshape(self.detector_size), frame=pointerh.contents.framenum)
                if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                    print("CANNOT COMMIT SLOT")
            except KeyboardInterrupt:
                break
     
        self.pass_on(1)
        return(1)
    
    def reset(self):
        pass
