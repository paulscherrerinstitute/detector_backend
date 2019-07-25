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


class Mystruct(ctypes.Structure):
    _fields_ = [("framemetadata", ctypes.c_uint64 * 8), ]


class DetectorZMQSender(DataFlowNode):

    name = Unicode("DetectorZMQSender", config=True)
    uri = Unicode('tcp://0.0.0.0:40000', config=True, help="URI which binds for ZMQ")
    socket_type = Unicode('PUSH', config=True, help="ZMQ socket type")
    
    rb_id = Int(0, config=True, help="")
    rb_followers = List([1, ], config=True, help="")

    rb_head_file = Unicode('', config=True, help="")
    rb_imghead_file = Unicode('', config=True, help="")
    rb_imgdata_file = Unicode('', config=True, help="")

    geometry = List((1, 1), config=True)
    detector_size = List((-1, -1), config=True)
    submodule_n = Int(1, config=True)

    reset_framenum = Bool(True, config=True, reconfig=True, help="Normalizes framenumber to the first caught frame")

    def _setup_ringbuffer(self):
        self.HEADER = Mystruct * self.n_submodules

        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_reader_id = rb.create_reader(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)

        # 64 bytes = 8 * uint64_t == 8 * (64bit/8bit)
        frame_header_n_bytes = 64 * self.n_submodules
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, frame_header_n_bytes)
        
        frame_data_n_bytes = int((self.detector_size[0] * self.detector_size[1] * self.bit_depth) / 8)
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, frame_data_n_bytes)
                                     
        n_slots = rb.adjust_nslots(self.rb_header_id)
        rb.set_buffer_slot_dtype(dtype=ctypes.__getattribute__('c_uint' + str(self.bit_depth)))

        self.log.info("RB %d slots: %d" % (self.rb_header_id, n_slots))
        self.log.info("RB header stride: %d" % rb.get_buffer_stride_in_byte(self.rb_hbuffer_id))
        self.log.info("RB data stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))

    def _reset_defaults(self):
        self.reset_framenum = True
    
    def open_sockets(self):
        self.log.info("CALLING OPEN")
        self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        self.skt.bind(self.uri)

    def close_sockets(self):
        self.log.info("CALLING CLOSE")
        self.skt.close(linger=0)
        while not self.skt.closed:
            sleep(0.01)

    def __init__(self, **kwargs):

        app = XblBaseApplication.instance()
        self.worker_communicator = app.worker_communicator
        self.worker_communicator.barrier()
        
        self.n_modules = self.geometry[0] * self.geometry[1]
        self.n_submodules = self.geometry[0] * self.geometry[1] * self.submodule_n
        self.log.debug("Using n_modules %d and n_submodules %d", self.n_modules, self.n_submodules)

        self._setup_ringbuffer()

        self.context = zmq.Context(io_threads=4)
        self.open_sockets()

        self.rb_current_slot = -1

        self.n_frames = -1
        self.period = 1

        self.counter = 0
        self.sent_frames = 0
        self.frames_with_missing_packets = 0
        self.total_missing_packets = 0
        self.first_frame = 0

        self.entry_size_in_bytes = -1

        self.metrics.set("activate_corrections", self.activate_corrections)
        self.metrics.set("activate_corrections_preview", self.activate_corrections_preview)
        self.metrics.set("name", self.name)

        self.send_time = 0
        #if self.output_file != '':
        #    self.log.info("writing to %s " % self.output_file)
        #    self.outfile = h5py.File(self.output_file, "w")
        #    self.dst = self.outfile.create_dataset("/data", shape=(1000, ) + self.detector_size, dtype=np.uint16)
            
    def reconfigure(self, settings):
        self.log.info("%s.reconfigure()", self.__class__.__name__)
        super(ZMQSender, self).reconfigure(settings)
        rb.reset()
        self.log.info(settings)

        for k, v in settings.iteritems():
            try:
                _ = self.__getattribute__(k)
            except AttributeError:
                self.log.warning("%s has no %s configurable, ignoring" % (self.name, k))
            if k.find("filename") != -1:
                if v != "":
                    if not os.path.exists(v):
                        self.worker_communicator.barrier()
                        raise RuntimeError("File %s not available as %s. Please RESET and retry" % (v, k))

            self.log.debug("Setting %s to %s" % (k, v))
            setattr(self, k, v)

        if "period" in settings:
            self.period = settings["period"] / 1e9

        if self.activate_corrections or (self.activate_corrections_preview and self.name == "preview"):
            self.setup_corrections()
        
        self.first_frame = 0
        self.worker_communicator.barrier()
        
        self._setup_ringbuffer()

        
    def initialize(self):
        self.log.info("%s.initialize()", self.__class__.__name__)
        self.log.info("Initializing writer name=%s.", self.name)
        #super(ZMQSender, self).initialize()

    def reset(self):
        self.log.info("%s.reset()", self.__class__.__name__)
        # logging stats
        self.log.info("%s" % {"received_frames": {"total": self.counter,
                                                  "incomplete": self.frames_with_missing_packets,
                                                  "packets_lost": self.total_missing_packets, "epoch": time()}
                        })
        self.log.info("%s" % {"sent_frames": self.sent_frames})
        
        super(ZMQSender, self).reset()
        rb.reset()

        #if self.output_file != '':
        #    self.outfile.close()
        self.counter = 0
        self.sent_frames = 0
        self.first_frame = 0
        self.frames_with_missing_packets = 0
        self.total_missing_packets = 0
        self.is_HG0 = False

        self.metrics.set("received_frames", {"name": self.name, "total": self.counter,
                                             "incomplete": self.frames_with_missing_packets,
                                             "packets_lost": self.total_missing_packets, "epoch": time()})
        self.metrics.set("sent_frames", {"name": self.name, "total": self.sent_frames, "epoch": time()})


        self._reset_defaults()
        
        self.send_fake_data = False
        self.close_sockets()
        sleep(0.2)
        self.open_sockets()
        self.log.info("Reset done")


    def send_frame(self, data, metadata, flags=0, copy=False, track=True):
        """send a numpy array with metadata"""
        metadata["htype"] = "array-1.0"
        metadata["type"] = str(data.dtype)
        metadata["shape"] = data.shape

        self.log.info("[%s] Sending frame %d", self.name, metadata["frame"])
        self.log.debug("[%s] Frame %d metadata %s", self.name, metadata["frame"], metadata)

        self.skt.send_json(metadata, flags | zmq.SNDMORE)
        return self.skt.send(data, flags, copy=copy, track=track)

    def get_frame_data(self, pointerd):
        data = np.ctypeslib.as_array(pointerd, shape=self.detector_size)
        return data

    def get_frame_metadata(self, metadata_pointer):
        metadata_struct = ctypes.cast(metadata_pointer, ctypes.POINTER(self.HEADER))

        metadata = {
            "framenums": [metadata_struct.contents[i].framemetadata[0] for i in range(self.n_submodules)],
            "missing_packets_1": [metadata_struct.contents[i].framemetadata[2] for i in range(self.n_submodules)], 
            "missing_packets_2": [metadata_struct.contents[i].framemetadata[3] for i in range(self.n_submodules)],
            "pulse_ids": [metadata_struct.contents[i].framemetadata[4] for i in range(self.n_submodules)],
            "daq_recs": [metadata_struct.contents[i].framemetadata[5] for i in range(self.n_submodules)],
            "module_number": [metadata_struct.contents[i].framemetadata[6] for i in range(self.n_submodules)],
            "module_enabled": [metadata_struct.contents[i].framemetadata[7] for i in range(self.n_submodules)]
        }

        metadata["frame"] = metadata["framenums"][0]
        metadata["daq_rec"] = metadata["daq_recs"][0]
        metadata["pulse_id"] = metadata["pulse_ids"][0]

        missing_packets = sum([metadata_struct.contents[i].framemetadata[1] for i in range(self.n_submodules)])
        if missing_packets != 0:
            self.log.warning("Frame %d lost frames %d" % (metadata["frame"], missing_packets))
            self.frames_with_missing_packets += 1
            self.total_missing_packets += missing_packets

        metadata["is_good_frame"] = int(len(set(metadata["framenums"])) == 1 and missing_packets == 0)
        metadata["pulse_id_diff"] = [metadata["pulse_id"] - i for i in metadata["pulse_ids"]]
        metadata["framenum_diff"] = [metadata["frame"] - i for i in metadata["framenums"]]

        return metadata

    def send(self, data):
        # FIXME
        timeout = max(2. * self.period, 1)

        ref_time = time()
        frame_comp_counter = 0
        pulseid = -1

        while True:

            # Check for timeout.
            ti = time()
            if(self.counter >= self.n_frames and self.n_frames != -1) or (ti - ref_time > timeout):
                self.log.debug("Timeout %d / %d, %.2f on pulseid %d" % (self.n_frames, self.counter, ti - ref_time, pulseid))
                break

            # Get next slot.
            self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)
            if self.rb_current_slot == -1:
                continue

            # Collect data from slot.
            try:
                metadata_pointer = rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot)
                metadata = self.get_frame_metadata(metadata_pointer)

                data_pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
                data = self.get_frame_data(data_pointer)

                self.log.debug("Retrieved data and metadata for frame %d, pulse_id %d.", metadata["frame"], metadata["pulse_id"])

            except:
                self.log.error("[%s] RB buffers: Header %s Data %s" % (self.name, self.rb_hbuffer_id, self.rb_hbuffer_id))
                # rb.gf_get_error does not work
                self.log.error("[%s] RB got error %s" % (self.name, rb.gf_get_error()))
                self.log.error("[%s] Issues with getting the RB header pointer (it is %r), current_slot: %d, first frame %d, recv_frame: %d. Casting exception" % 
                                (self.name, bool(pointerh), self.rb_current_slot, self.first_frame, self.counter))
                self.log.error(sys.exc_info())
                raise RuntimeError
            
            # Some frame math
            if self.first_frame == 0:
                self.log.info("First frame got: %d pulse_id: %d" % (metadata["frame"], metadata["pulse_id"]))
                self.first_frame = metadata["frame"]

            if self.reset_framenum:
                metadata["frame"] -= self.first_frame

            self.counter += 1
            
            # Send frame.
            try:
                self.send_frame(data, metadata, flags=zmq.NOBLOCK, copy=True)
            except zmq.EAGAIN:
                self.log.error("[%s] Frame %d dropped because no receiver was available." % (self.name, framenum))
            except:
                self.log.error("Unknown in sending array: %s" % sys.exc_info()[1])

            if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                self.log.error("RINGBUFFER: CANNOT COMMIT SLOT")

            self.metrics.set("sent_frames", {"name": self.name, "total": self.sent_frames, "epoch": time()})

            frame_comp_counter += 1
            ref_time = time()
            

        self.log.debug("Writer loop exited")

        self.pass_on(self.counter)
        return(self.counter)
