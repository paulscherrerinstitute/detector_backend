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
import sys

from time import time, sleep

BUFFER_LENGTH = 4096
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6

CACHE_LINE_SIZE = 64

class Mystruct(ctypes.Structure):
    _fields_ = [("framemetadata", ctypes.c_uint64 * 8), ]


#_mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/libstruct_array.so")

HEADER = Mystruct * 10


def send_array(socket, A, flags=0, copy=False, track=True, metadata={}):
    """send a numpy array with metadata"""
    metadata["htype"] = "array-1.0"
    metadata["type"] = str(A.dtype)
    metadata["shape"] = A.shape

    #md = dict(
    #    htype="array-1.0",
    #    type=str(A.dtype),
    #    shape=A.shape,
    #    frame=frame,
    #    is_good_frame=is_good_frame,
    #)
    #print(md)
    socket.send_json(metadata, flags | zmq.SNDMORE)
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

    def open_sockets(self):
        self.log.info("CALLING OPEN")
        self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        self.skt.bind(self.uri)
        self.skt.SNDTIMEO = 1000

    def close_sockets(self):
        #self.skt.unbind(self.uri)
        self.log.info("CALLING CLOSE")
        self.skt.close(linger=0)
        #self.skt.destroy()
        while not self.skt.closed:
            #print(self.skt.closed)
            sleep(1)

    def __init__(self, **kwargs):
        super(ZMQSender, self).__init__(**kwargs)
        self.detector_size = (self.module_size[0] * self.geometry[0], self.module_size[1] * self.geometry[1])
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

        self.context = zmq.Context(io_threads=2)
        self.open_sockets()

        self.rb_current_slot = -1

        self.n_frames = -1
        self.period = 1
        self.first_frame = -1

        self.n_modules = self.geometry[0] * self.geometry[1]

        self.counter = 0
        self.sent_frames = 0
        self.frames_with_missing_packets = 0
        self.total_missing_packets = 0
        self.first_frame = 0

        self.fakedata = np.zeros([1536, 1024], dtype=np.uint16)
        self.entry_size_in_bytes = -1

        self.log.info("ZMQ streamer initialized")

    def reconfigure(self, settings):
        self.log.info(settings)
        if "n_frames" in settings:
            self.n_frames = settings["n_frames"]
        if "period" in settings:
            self.period = settings["period"] / 1e9
        self.first_frame = 0

    def send(self, data):
        # FIXME
        timeout = 1  # ctypes.c_int(max(int(2. * self.period), 1))

        ref_time = time()
        frame_comp_time = time()
        frame_comp_counter = 0
        #frames_with_missing_packets = 0
        is_good_frame = True
        #total_missing_packets = 0
        
        # FIXME avoid infinit loop
        while True:
            if(self.counter >= self.n_frames and self.n_frames != -1) or (time() - ref_time > timeout):
                break

            self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)

            if self.rb_current_slot == -1:
                continue

            pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot),
                                   ctypes.POINTER(HEADER))

            # check that all frame numbers are the same
            if self.check_framenum:
                framenums = [pointerh.contents[i].framemetadata[0] for i in range(self.n_modules)]
                is_good_frame = len(set(framenums)) == 1

            framenum = pointerh.contents[0].framemetadata[0]
            daq_rec = pointerh.contents[0].framemetadata[4]
            pulseid = pointerh.contents[0].framemetadata[5]

            if self.first_frame == 0:
                self.log.info("First frame got: %d" % framenum)
                self.first_frame = framenum

            framenum -= self.first_frame

            # check if packets are missing
            missing_packets = sum([pointerh.contents[i].framemetadata[1] for i in range(self.n_modules)])
            is_good_frame = missing_packets == 0
            if missing_packets != 0:
                #self.log.warning("Frame %d lost frames %d" % (framenum, missing_packets))
                frames_with_missing_packets += 1
                total_missing_packets += missing_packets

            pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)

            #if self.entry_size_in_bytes == -1:
            #    self.entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
            #    data_size = (int(self.entry_size_in_bytes / (self.bit_depth / 8) / self.detector_size[1], self.detector_size[1])
            #                 print(self.entry_size_in_bytes, data_size)
            #    # TODO: benchmark speed of this:
            data = np.ctypeslib.as_array(pointer, self.detector_size, )
            #print(data.shape)
            #data = self.fakedata

            try:
                send_array(self.skt, data, metadata={"frame": framenum, "is_good_frame": is_good_frame, "daq_rec": daq_rec, "pulseid": pulseid})
                #pass
            except:
                pass #print(sys.exc_info())
            self.metrics.set("received_frames", {"total": self.counter, "incomplete": frames_with_missing_packets, "packets_lost": total_missing_packets, "epoch": time()})

            if self.counter % 1000 == 0:
                print(time(), " ", self.counter)

            self.counter += 1
            frame_comp_counter += 1
            ref_time = time()

            if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                self.log.error("RINGBUFFER: CANNOT COMMIT SLOT")
                #break
            #except KeyboardInterrupt:
            #    raise StopIteration

        self.log.debug("Writer loop exited")
        self.pass_on(self.counter)
        return(self.counter)
    
    def reset(self):
        self.counter = 0
        self.sent_frames = 0
        self.first_frame = 0
        self.frames_with_missing_packets = 0
        self.total_missing_packets = 0

        self.metrics.set("received_frames", {"total": self.counter, "incomplete": self.frames_with_missing_packets, 
                                             "packets_lost": self.total_missing_packets, "epoch": time()})
        self.metrics.set("sent_frames", self.sent_frames)

        self.close_sockets()
        sleep(1)
        self.open_sockets()
        self.log.info("Reset done")
