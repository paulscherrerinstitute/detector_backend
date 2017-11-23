from __future__ import print_function, division, unicode_literals
from dafl.application import XblLoggingConfigurable
from dafl.traits import Int, Unicode, Float, List, Bool, Unicode
from dafl.dataflow import DataFlowNode, DataFlow
from dafl.application import XblBaseApplication

import struct

import ringbuffer as rb
import ctypes

import ctypes
import numpy as np
import os
import zmq
import sys

import h5py
from time import time, sleep

from numba import jit

from copy import copy


BUFFER_LENGTH = 4096
DATA_ARRAY = np.ctypeslib.as_ctypes(np.zeros(BUFFER_LENGTH, dtype=np.uint16))  # ctypes.c_uint16 * BUFFER_LENGTH
HEADER_ARRAY = ctypes.c_char * 6

CACHE_LINE_SIZE = 64

class Mystruct(ctypes.Structure):
    _fields_ = [("framemetadata", ctypes.c_uint64 * 8), ]


#_mod = ctypes.cdll.LoadLibrary(os.getcwd() + "/libstruct_array.so")

HEADER = Mystruct * 10


@jit(nopython=True, nogil=True, cache=True)
def do_corrections(m, n, image, G, P, pede_mask, mask, mask2):
    #m, n = image.shape
    gain_mask = np.bitwise_and(np.right_shift(image, 14), mask2)
    data = np.bitwise_and(image, mask)
    res = np.empty((m, n), dtype=np.float32)

    for i in range(m):
        for j in range(n):
            if pede_mask[i][j] != 0:
                res[i][j] = 0
                continue
            gm = gain_mask[i][j]
            if gm == 3:
                gm = 2
            res[i][j] = (data[i][j] - P[gm][i][j]) / G[gm][i][j]
    return res


def send_array(socket, A, flags=0, copy=False, track=True, metadata={}):
    """send a numpy array with metadata"""
    metadata["htype"] = "array-1.0"
    metadata["type"] = str(A.dtype)
    metadata["shape"] = A.shape

    socket.send_json(metadata, flags | zmq.SNDMORE)
    return socket.send(A, flags, copy=copy, track=track)


class ZMQSender(DataFlowNode):

    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    defaults = {}
    name = Unicode("ZMQSender", config=True, reconfig=True)
    uri = Unicode('tcp://192.168.10.1:9999', config=True, reconfig=True, help="URI which binds for ZMQ")
    socket_type = Unicode('PUB', config=True, reconfig=True, help="ZMQ socket type")
    send_every_s = Float(0, config=True, reconfig=True, help="send every n second")
    module_size = List((512, 1024), config=True, reconfig=True)
    geometry = List((1, 1), config=True, reconfig=True)

    gap_px_chip = List((0, 0), config=True, reconfig=True)  # possibly not used
    gap_px_module = List((0, 0), config=True, reconfig=True)

    rb_id = Int(0, config=True, reconfig=True, help="")
    rb_followers = List([1, ], config=True, reconfig=True, help="")
    bit_depth = Int(16, config=True, reconfig=True, help="")

    rb_head_file = Unicode('', config=True, reconfig=True, help="")
    rb_imghead_file = Unicode('', config=True, reconfig=True, help="")
    rb_imgdata_file = Unicode('', config=True, reconfig=True, help="")

    check_framenum = Bool(True, config=True, reconfig=True, help="Check that the frame numbers of all the modules are the same")
    reset_framenum = Bool(True, config=True, reconfig=True, help="Normalizes framenumber to the first caught frame")
    #output_file = Unicode('', config=True, reconfig=True)

    gain_corrections_filename = Unicode('', config=True, reconfig=True)
    gain_corrections_dataset = Unicode('', config=True, reconfig=True)
    pede_corrections_filename = Unicode('', config=True, reconfig=True)
    pede_corrections_dataset = Unicode('', config=True, reconfig=True)
    pede_mask_dataset = Unicode('', config=True, reconfig=True)
    
    activate_corrections_preview = Bool(False, config=True, reconfig=True, help="")
    activate_corrections = Bool(False, config=True, reconfig=True, help="")

    send_fake_data = Bool(False, config=True, reconfig=True, help="")
    #gain_corrections_list = List((0,), config=True, reconfig=True, help="")
    #pedestal_corrections_list = List((0,), config=True, reconfig=True, help="")

    def _reset_defaults(self):
        self.reset_framenum = True
        self.gain_corrections_filename = ''
        self.gain_corrections_dataset = ''
        self.pede_corrections_filename = ''
        self.pede_corrections_dataset = ''
        self.activate_corrections_preview = False
        self.activate_corrections = False
    
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
        #self.log.debug(self.socket.closed)
        while not self.skt.closed:
            sleep(1)

    def __init__(self, **kwargs):
        super(ZMQSender, self).__init__(**kwargs)
        self.detector_size = (self.module_size[0] * self.geometry[0], self.module_size[1] * self.geometry[1])
        #self.detector_size = ((self.module_size[0] + self.gap_px_chip[0]) * self.geometry[0], (self.module_size[1] + self.gap_px_chip[1]) * self.geometry[1])

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

        self.n_modules = self.geometry[0] * self.geometry[1]

        self.counter = 0
        self.sent_frames = 0
        self.frames_with_missing_packets = 0
        self.total_missing_packets = 0
        self.first_frame = 0

        self.fake_data = np.zeros([2, 2], dtype=np.uint16)
        self.entry_size_in_bytes = -1

        self.recv_frames = 0

        self.gain_corrections = np.ones((3, self.detector_size[0], self.detector_size[1]), dtype=np.float32)
        self.pede_corrections = np.zeros((3, self.detector_size[0], self.detector_size[1]), dtype=np.float32)
        self.pede_mask = np.zeros((3, self.detector_size[0], self.detector_size[1]), dtype=np.float32)

        self.metrics.set("activate_corrections", self.activate_corrections)
        self.metrics.set("activate_corrections_preview", self.activate_corrections_preview)
        self.metrics.set("name", self.name)

        if self.activate_corrections or (self.activate_corrections_preview and self.name == "preview"):
            self.setup_corrections()

        self.send_time = 0
        #if self.output_file != '':
        #    self.log.info("writing to %s " % self.output_file)
        #    self.outfile = h5py.File(self.output_file, "w")
        #    self.dst = self.outfile.create_dataset("/data", shape=(1000, ) + self.detector_size, dtype=np.uint16)
            
    def reconfigure(self, settings):
        self.log.warning("%s.reconfigure()",self.__class__.__name__)
        super(ZMQSender, self).reconfigure(settings)
        self.log.info(settings)
        if "n_frames" in settings:
            self.n_frames = settings["n_frames"]
        if "period" in settings:
            self.period = settings["period"] / 1e9

        if "activate_corrections" in settings:
            self.activate_corrections = settings["activate_corrections"]
        if "activate_corrections_preview" in settings:
            self.activate_corrections_preview = settings["activate_corrections_preview"]

        if "gain_corrections_filename" in settings:
            self.gain_corrections_filename = settings["gain_corrections_filename"]
        if "pede_corrections_filename" in settings:
            self.pede_corrections_filename = settings["pede_corrections_filename"]
        if "gain_corrections_dataset" in settings:
            self.gain_corrections_dataset = settings["gain_corrections_dataset"]
        if "pede_corrections_dataset" in settings:
            self.pede_corrections_dataset = settings["pede_corrections_dataset"]
        if "pede_mask_dataset" in settings:
            self.pede_mask_dataset = settings["pede_mask_dataset"]

        if self.activate_corrections or (self.activate_corrections_preview and self.name == "preview"):
            self.setup_corrections()
        if "send_fake_data" in settings:
            self.send_fake_data = settings["send_fake_data"]
        self.first_frame = 0
        self.recv_frames = 0

    def initialize(self):
        self.log.warning("%s.initialize()",self.__class__.__name__)
        #super(ZMQSender, self).initialize()

    def reset(self):
        self.log.warning("%s.reset()",self.__class__.__name__)
        #super(ZMQSender, self).reset()
        #if self.output_file != '':
        #    self.outfile.close()
        self.counter = 0
        self.sent_frames = 0
        self.first_frame = 0
        self.frames_with_missing_packets = 0
        self.total_missing_packets = 0

        self.metrics.set("received_frames", {"name": self.name, "total": self.counter,
                                             "incomplete": self.frames_with_missing_packets,
                                             "packets_lost": self.total_missing_packets, "epoch": time()})
        self.metrics.set("sent_frames", {"name": self.name, "total": self.sent_frames, "epoch": time()})

        # logging stats
        self.log.info("%s" % {"received_frames": {"total": self.counter,
                                                  "incomplete": self.frames_with_missing_packets,
                                                  "packets_lost": self.total_missing_packets, "epoch": time()}
                        })
        self.log.info("%s" % {"sent_frames": self.sent_frames})
        self.pede_corrections = np.zeros((3, self.detector_size[0], self.detector_size[1]), dtype=np.float32)
        self.pede_mask = np.zeros((3, self.detector_size[0], self.detector_size[1]), dtype=np.float32)
        
        self._reset_defaults()
        
        self.send_fake_data = False
        self.close_sockets()
        sleep(0.2)
        self.open_sockets()
        self.log.info("Reset done")

    def setup_corrections(self, ):
        self.log.info("calling setup corrections")
        self.log.info(self.gain_corrections_filename + " " + self.pede_corrections_filename)
        self.log.info(self.gain_corrections_dataset + " " + self.pede_corrections_dataset)
        # TODO add shape check
        if self.gain_corrections_filename != "" and self.gain_corrections_dataset != "":
            gain_corrections_file = h5py.File(self.gain_corrections_filename)
            self.gain_corrections = gain_corrections_file[self.gain_corrections_dataset][:]
            gain_corrections_file.close()
        if self.pede_corrections_filename != "" and self.pede_corrections_dataset != "":
            pede_corrections_file = h5py.File(self.pede_corrections_filename)
            self.pede_corrections = pede_corrections_file[self.pede_corrections_dataset][:]
            if self.pede_mask_dataset != "":
                self.pede_mask = pede_corrections_file[self.pede_mask_dataset][:]
            pede_corrections_file.close()

        if len(self.gain_corrections.shape) != 3 or len(self.pede_corrections.shape) != 3:
            self.log.error("Gain and pede corrections must be provided in a 3D array, e.g. [G0, G1, G2]. Provided respectively %s and %s. Will not apply corrections" % (self.gain_corrections.shape, self.pede_corrections.shape))
            raise ValueError("Gain and pede corrections must be provided in a 3D array, e.g. [G0, G1, G2]. Provided respectively %s and %s. Will not apply corrections" % (self.gain_corrections.shape, self.pede_corrections.shape))
            
        self.log.info("Gain and pede corrections will be applied")
        self.metrics.set("activate_corrections", self.activate_corrections)
        self.metrics.set("activate_corrections_preview", self.activate_corrections_preview)

    def send(self, data):
        # FIXME
        timeout = max(2. * self.period, 1)

        ref_time = time()
        frame_comp_time = time()
        frame_comp_counter = 0
        is_good_frame = True

        # need to stay here because of numba
        # for gain plus data masking
        mask = int('0b' + 14 * '1', 2)
        mask2 = int('0b' + 2 * '1', 2)

        # getting data from RB
        while True:
            if(self.counter >= self.n_frames and self.n_frames != -1) or (time() - ref_time > timeout):
                break

            self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)

            if self.rb_current_slot == -1:
                continue

            pointerh = ctypes.cast(rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot),
                                   ctypes.POINTER(HEADER))

            # check that all frame numbers are the same
            daq_recs = [pointerh.contents[i].framemetadata[5] for i in range(self.n_modules)]
            framenums = [pointerh.contents[i].framemetadata[0] for i in range(self.n_modules)]
            pulseids = [pointerh.contents[i].framemetadata[4] for i in range(self.n_modules)]
            if self.check_framenum:
                is_good_frame = len(set(framenums)) == 1
            framenum = copy(pointerh.contents[0].framemetadata[0])
            pulseid = pointerh.contents[0].framemetadata[4]
            daq_rec = pointerh.contents[0].framemetadata[5]
            

            if self.first_frame == 0:
                self.log.info("First frame got: %d" % framenum)
                self.first_frame = framenum

            if self.reset_framenum:
                framenum -= self.first_frame

            if self.send_every_s != 0 and pulseid % 100 != 0:  #and (time() - self.send_time) < self.send_every_s:
                self.recv_frames += 1
                if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                    self.log.error("RINGBUFFER: CANNOT COMMIT SLOT")
                continue
            self.recv_frames += 1
            self.send_time = time()
            
            self.log.debug("Received %d frames" % self.recv_frames)

            # check if packets are missing
            missing_packets = sum([pointerh.contents[i].framemetadata[1] for i in range(self.n_modules)])
            is_good_frame = missing_packets == 0
            if missing_packets != 0:
                self.log.warning("Frame %d lost frames %d" % (framenum, missing_packets))
                self.frames_with_missing_packets += 1
                self.total_missing_packets += missing_packets

            pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
            data = np.ctypeslib.as_array(pointer, self.detector_size, )
            self.counter += 1
            self.metrics.set("received_frames", {"total": self.counter, "incomplete": self.frames_with_missing_packets, "packets_lost": self.total_missing_packets, "epoch": time()})

            if self.send_fake_data:
                data = self.fake_data

            if self.activate_corrections or (self.name == "preview" and self.activate_corrections_preview):
                t_i = time()
                data = do_corrections(data.shape[0], data.shape[1], data, self.gain_corrections, self.pede_corrections, self.pede_mask, mask, mask2)
                self.log.debug("Corrections done")
                self.log.info("Correction took %.3f seconds" % (time() - t_i))
                self.sent_frames += 1
            try:
                send_array(self.skt, data, metadata={"frame": framenum, "is_good_frame": is_good_frame, "daq_rec": daq_rec, "pulse_id": pulseid, "daq_recs": daq_recs, "pulse_ids": pulseids, "framenums": framenums, "pulse_id_diff": [pulseids[0] - i for i in pulseids], "framenum_diff": [framenums[0] - i for i in framenums]})
            except:
                #pass
                self.log.error(sys.exc_info()[1])
            self.metrics.set("sent_frames", {"name": self.name, "total": self.sent_frames, "epoch": time()})        

            #if self.counter % 1000 == 0:
            #    print(time(), " ", self.counter)

            frame_comp_counter += 1
            ref_time = time()

            if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                self.log.error("RINGBUFFER: CANNOT COMMIT SLOT")
                #break
            #except KeyboardInterrupt:
            #    raise StopIteration
        #self.outfile.close()

        self.log.debug("Writer loop exited")
        self.pass_on(self.counter)
        return(self.counter)
    
        
