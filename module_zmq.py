from __future__ import print_function, division, unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float, List, Bool
from dafl.dataflow import DataFlowNode, DataFlow
from dafl.application import XblBaseApplication
import matplotlib.pyplot as plt

import struct

import ringbuffer as rb
import ctypes

import socket
import ctypes
import numpy as np
import os
import zmq

from time import time, sleep

BUFFER_LENGTH = 1024
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint32))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6

CACHE_LINE_SIZE = 64

RB_HEAD_FILE = "rb_header.dat"
RB_IMGHEAD_FILE = "rb_image_header.dat"
RB_IMGDATA_FILE = "rb_image_data.dat"

MODULE_SIZE = (512, 512)


class HEADER(ctypes.Structure):
    _fields_ = [
        ("emptyheader", HEADER_ARRAY),
        ("framenum", ctypes.c_uint64),
        ("packetnum", ctypes.c_uint64),
        ("padding", ctypes.c_uint8 * (CACHE_LINE_SIZE - 6 - 8 - 8))
        ]

header = HEADER("      ".encode(), ctypes.c_uint64(), ctypes.c_uint64(),  np.ctypeslib.as_ctypes(np.zeros(CACHE_LINE_SIZE - 6 - 8 - 8, dtype=np.uint8)))



class ZMQSender(DataFlowNode):

    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    uri = Unicode('tcp://192.168.10.1:9999', config=True, reconfig=True, help="URI which binds for ZMQ")
    socket_type = Unicode('PUSH', config=True, reconfig=True, help="ZMQ socket type")
    send_rate = Float(1, config=True, reconfig=True, help="Frame fraction to be sent")

    rb_id = Int(0, config=True, reconfig=True, help="")
    rb_followers = List([1, ], config=True, reconfig=True, help="")
    bit_depth = Int(32, config=True, reconfig=True, help="")

    def __init__(self, **kwargs):
        super(ZMQSender, self).__init__(**kwargs)
        app = XblBaseApplication.instance()
        self.worker_communicator = app.worker_communicator
        self.worker_communicator.barrier()
        
        self.rb_header_id = rb.open_header_file(RB_HEAD_FILE)
        self.rb_reader_id = rb.create_reader(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(RB_IMGHEAD_FILE, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(RB_IMGDATA_FILE, self.rb_header_id, 0)
        print(rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64))

        print(rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, int(self.bit_depth / 8) * 512 * 512))
        rb.adjust_nslots(self.rb_header_id);
        
        #self.context = zmq.Context()
        #self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        #self.skt.bind(self.uri)

        self.rb_current_slot = -1

        print("READER:",)
        
    def send(self, data):
        #send_array(self.skt, data[1], copy=False, track=True, frame=data[0])
        #print("0MQ data:", data)
        #self.pass_on(1)
        #self.log.debug("send() got %s" % (data))
        #print(self.ip)
        #self.pass_on(data)
        #return(1)
    
        while True:
            self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)
            if self.rb_current_slot == -1:
                sleep(0.1)
                continue
            print("self.rb_current_slot", self.rb_current_slot)
            pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot), type(ctypes.pointer(header)))
            print("pointerh.contents.framenum", pointerh.contents.framenum)
            pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
                   
            entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
            data = np.ctypeslib.as_array(pointer, (entry_size_in_bytes / (self.bit_depth / 8), ), )
            print(data.shape, data.sum())
            plt.figure()
            plt.imshow(data.reshape(512, -1))
            plt.show()
            if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                print("CANNOT COMMIT SLOT")
            
        self.pass_on(1)
        #self.log.debug("send() got %s" % (data))
        #print(self.ip)
        #self.pass_on(data)
        return(1)
    
    def reset(self):
        pass
