from __future__ import print_function, division, unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float, List, Bool, Unicode
from dafl.dataflow import DataFlowNode, DataFlow
from dafl.application import XblBaseApplication
#import matplotlib.pyplot as plt

import struct

import ringbuffer as rb
import ctypes

import ctypes
import numpy as np
import os
import zmq

from time import time, sleep

BUFFER_LENGTH = 4096
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6

CACHE_LINE_SIZE = 64

class Mystruct(ctypes.Structure):
    _fields_ = [("framemetadata", ctypes.c_uint64 * 8), ]


#_mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/libstruct_array.so")

HEADER = Mystruct * 10


def send_array(socket, A, flags=0, copy=False, track=True, frame=-1, is_good_frame=True, packets_lost=[0,0]):
    """send a numpy array with metadata"""
    md = dict(
        htype="array-1.0",
        type=str(A.dtype),
        shape=A.shape,
        frame=frame,
        is_good_frame=is_good_frame,
    )
    #print(md)
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

    check_framenum = Bool(True, config=True, reconfig=True, help="Check that the frame numbers of all the modules are the same")
    
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
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64 * self.geometry[0] * self.geometry[1])

        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id,
                                           int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        rb.adjust_nslots(self.rb_header_id)
        
        self.context = zmq.Context()
        self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        self.skt.bind(self.uri)

        self.rb_current_slot = -1

        self.n_frames = -1
        self.period = 1
        self.first_frame = -1

        self.n_modules = self.geometry[0] * self.geometry[1]
        self.log.info("ZMQ streamer initialized")

    def reconfigure(self, settings):
        self.log.info(settings)
        if "n_frames" in settings:
            self.n_frames = settings["n_frames"]
        if "period" in settings:
            self.period = settings["period"] / 1000000000
        self.first_frame = -1

    def send(self, data):
        # FIXME
        timeout = 1  # ctypes.c_int(max(int(2. * self.period), 1))

        ref_time = time()
        counter = 0
        frames_with_missing_packets = 0
        is_good_frame = True
        total_missing_packets = 0
        while (counter < self.n_frames or self.n_frames == -1) and (time() - ref_time < timeout):
            try:
                self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)

                if self.rb_current_slot == -1:
                    continue
                    #sleep(1)
                    #self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)
                    #if self.rb_current_slot == -1:
                    #    break
                #self.log.debug("READER: self.rb_current_slot" + str(self.rb_current_slot))

                pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot),
                                       ctypes.POINTER(HEADER))

                # check that all frame numbers are the same
                if self.check_framenum:
                    framenums = [pointerh.contents[i].framemetadata[0] for i in range(self.n_modules)]
                    is_good_frame = len(set(framenums)) == 1

                framenum = pointerh.contents[0].framemetadata[0]

                # check if packets are missing
                missing_packets = sum([pointerh.contents[i].framemetadata[1] for i in range(self.n_modules)])
                is_good_frame = missing_packets == 0
                if missing_packets != 0:
                    self.log.warning("Frame %d lost frames %d" % (framenum, missing_packets))
                    frames_with_missing_packets += 1
                    total_missing_packets += missing_packets

                for i in range(self.n_modules):
                    self.log.debug("%d %d %d %d %d" % (i, pointerh.contents[i].framemetadata[0], pointerh.contents[i].framemetadata[1],                                  pointerh.contents[i].framemetadata[2], pointerh.contents[i].framemetadata[3]))
                pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)

                entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
                # TODO: benchmark speed of this:
                data = np.ctypeslib.as_array(pointer, (int(entry_size_in_bytes / (self.bit_depth / 8)), ), )

                send_array(self.skt, data.reshape(self.detector_size), frame=framenum, is_good_frame=is_good_frame)
                self.metrics.set("received_frames", {"total": counter, "incomplete": frames_with_missing_packets, 
                                                     "packets_lost": total_missing_packets})

                counter += 1
                ref_time = time()

                #self.log.debug("WRITER " +  str(pointerh.contents.framenum - self.first_frame))
                if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                    self.log.error("RINGBUFFER: CANNOT COMMIT SLOT")

            except KeyboardInterrupt:
                raise StopIteration

        self.log.debug("Writer loop exited")
        self.pass_on(counter)
        return(counter)
    
    def reset(self):
        pass
