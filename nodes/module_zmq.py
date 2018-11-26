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


@jit(nopython=True, nogil=True, cache=True)
def do_corrections(m, n, image, G, P, pede_mask, mask, mask2):
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



def expand_image(image, mods, mod_gaps, chip_gaps, chips):
    shape = [512 * mods[0], 1024 * mods[1]]
    new_shape = [shape[i] + (mod_gaps[i]) * (mods[i] - 1) + (chips[i] - 1) * chip_gaps[i] * mods[i] for i in range(2)]
    res = np.zeros(new_shape)
    m = [mod_gaps[i] - chip_gaps[i] for i in range(2)]

    for i in range(mods[0] * chips[0]):
        for j in range(mods[1] * chips[1]):
            mod_size = [256, 256]  # [int(shape[0] / mods[0]), int(shape[1] / mods[1])]

            disp = [int(i / chips[0]) * m[0] + i * chip_gaps[0], int(j / chips[1]) * m[1] + j * chip_gaps[1]]
            init = [i * mod_size[0], j * mod_size[1]]
            end = [(1 + i) * mod_size[0], (1 + j) * mod_size[1]]
            res[disp[0] + init[0]: disp[0] + end[0], disp[1] + init[1]:disp[1] + end[1]] = image[init[0]:end[0], init[1]:end[1]]
    return res


def convert_stripsel(imgin):
    imgout = np.zeros((86, (1024 * 3 + 18)), dtype=imgin.dtype)
    # 256 not divisible by 3, so we round up
    # 18 since we have 6 more pixels in H per gap

    # first we fill the normal pixels, the gap ones will be overwritten later
    for yin in range(256):
        for xin in range(1024):
            ichip = xin // 256
            xout = (ichip * 774) + (xin % 256) * 3 + yin % 3
            # 774 is the chip period, 256*3+6
            yout = yin // 3
            imgout[yout, xout] = imgin[yin, xin]
    # now the gap pixels...
    for igap in range(3):
        for yin in range(256):
            yout = (yin // 6) * 2
            # first the left side of gap
            xin = igap * 64 + 63
            xout = igap * 774 + 765 + yin % 6
            imgout[yout, xout] = imgin[yin, xin]
            imgout[yout + 1, xout] = imgin[yin, xin]
            #then the right side is mirrored
            xin = igap * 64 + 63 + 1
            xout = igap * 774 + 765 + 11 - yin % 6
            imgout[yout, xout] = imgin[yin, xin]
            imgout[yout + 1, xout] = imgin[yin, xin]
            # imgout[yout,xout]=imgout[yout,xout]/2 if we want a proper normalization (the area of those pixels is double, so they see 2x the signal)

    return imgout


class ZMQSender(DataFlowNode):

    #filename = Unicode(u'data.txt', config=True, reconfig=True, help='output filename with optional path')
    name = Unicode("ZMQSender", config=True)
    uri = Unicode('tcp://192.168.10.1:9999', config=True, help="URI which binds for ZMQ")
    socket_type = Unicode('PUB', config=True, help="ZMQ socket type")

    send_every_s = Float(0, config=True, help="send every n second")
    preview_modulo = Int(0, config=True, help="Send on modulo. 0 for turning off.")
    preview_modulo_offset = Int(0, config=True, help="Offset to add to the modulo calculation. Default: 0.")

    module_size = List((512, 1024), config=True)
    exp_module_size = List((0, 0), config=True) 
    expand_gaps = Bool(True, config=True)
    geometry = List((1, 1), config=True)
    detector_size = List((-1, -1), config=True)
    submodule_n = Int(1, config=True)

    gap_px_chip = List((2, 2), config=True, reconfig=False)  # possibly not used
    gap_px_module = List((0, 0), config=True, reconfig=False)
    chips_module = List((2, 4), config=True, reconfig=False)
    
    rb_id = Int(0, config=True, help="")
    rb_followers = List([1, ], config=True, help="")
    bit_depth = Int(16, config=True, help="")

    rb_head_file = Unicode('', config=True, help="")
    rb_imghead_file = Unicode('', config=True, help="")
    rb_imgdata_file = Unicode('', config=True, help="")

    check_framenum = Bool(True, config=True, reconfig=True, help="Check that the frame numbers of all the modules are the same")
    reset_framenum = Bool(True, config=True, reconfig=True, help="Normalizes framenumber to the first caught frame")
    #output_file = Unicode('', config=True, reconfig=True)

    gain_corrections_filename = Unicode('', config=True, reconfig=False)
    gain_corrections_dataset = Unicode('', config=True, reconfig=False)
    pede_corrections_filename = Unicode('', config=True, reconfig=False)
    pede_corrections_dataset = Unicode('', config=True, reconfig=False)
    pede_mask_dataset = Unicode('', config=True, reconfig=False)
    
    activate_corrections_preview = Bool(False, config=True, reconfig=False, help="")
    activate_corrections = Bool(False, config=True, reconfig=False, help="")

    send_fake_data = Bool(False, config=True, reconfig=True, help="")
    #gain_corrections_list = List((0,), config=True, reconfig=True, help="")
    #pedestal_corrections_list = List((0,), config=True, reconfig=True, help="")

    flip = List((-1, ), config=True, reconfig=False)

    is_HG0 = Bool(False, config=True)

    modules_orig_x = List([], config=True, help="Modules origin for image assembly, X coordinate")
    modules_orig_y = List([], config=True, help="Modules origin for image assembly, Y coordinate")

    stripsel_module = Bool(False, config=True)

    def _reset_defaults(self):
        self.reset_framenum = True
        self.gain_corrections_filename = ''
        self.gain_corrections_dataset = ''
        self.pede_corrections_filename = ''
        self.pede_corrections_dataset = ''
        self.pede_mask_dataset = ''
        self.activate_corrections_preview = False
        self.activate_corrections = False
    
    def open_sockets(self):
        self.log.info("CALLING OPEN")
        self.skt = self.context.socket(zmq.__getattribute__(self.socket_type))
        self.skt.bind(self.uri)
        self.skt.SNDTIMEO = 1000

    def close_sockets(self):
        self.log.info("CALLING CLOSE")
        self.skt.close(linger=0)
        while not self.skt.closed:
            sleep(1)

    def __init__(self, **kwargs):
        super(ZMQSender, self).__init__(**kwargs)
        #if self.detector_size == [-1, -1]:
        #    self.detector_size = [self.module_size[0] * self.geometry[0], self.module_size[1] * self.geometry[1]]

        app = XblBaseApplication.instance()
        self.worker_communicator = app.worker_communicator
        self.worker_communicator.barrier()
        
        self.n_modules = self.geometry[0] * self.geometry[1]
        self.n_submodules = self.geometry[0] * self.geometry[1] * self.submodule_n
        self.log.debug("Using n_modules %d and n_submodules %d", self.n_modules, self.n_submodules)

        self.HEADER = Mystruct * self.n_submodules

        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_reader_id = rb.create_reader(self.rb_header_id, self.rb_id, self.rb_followers)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)

        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64 * self.n_submodules)

        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id,
                                     int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        n_slots = rb.adjust_nslots(self.rb_header_id)

        self.log.info("RB %d slots: %d" % (self.rb_header_id, n_slots))
        self.log.info("RB header stride: %d" % rb.get_buffer_stride_in_byte(self.rb_hbuffer_id))
        self.log.info("RB data stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))

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

        self.fake_data = np.zeros([2, 2], dtype=np.uint16)
        self.entry_size_in_bytes = -1

        self.recv_frames = 0

        print(self.detector_size)
        self.gain_corrections = np.ones((3, self.detector_size[0], self.detector_size[1]), dtype=np.float32)
        self.pede_corrections = np.zeros((3, self.detector_size[0], self.detector_size[1]), dtype=np.float32)
        self.pede_mask = np.zeros((self.detector_size[0], self.detector_size[1]), dtype=np.int16)

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
        self.recv_frames = 0
        self.worker_communicator.barrier()
        
        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_reader_id = rb.create_reader(self.rb_header_id, self.rb_id, self.rb_followers)
        
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_imghead_file, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_imgdata_file, self.rb_header_id, 0)

        self.log.info("[%s] RB buffers: Header %d Data %d" % (self.name, self.rb_hbuffer_id, self.rb_dbuffer_id))
        
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, 64 * self.n_submodules)

        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id,
                                     int(self.bit_depth / 8) * self.detector_size[0] * self.detector_size[1])
        rb.adjust_nslots(self.rb_header_id)

        
    def initialize(self):
        self.log.info("%s.initialize()", self.__class__.__name__)
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

        self.pede_corrections = np.zeros((4, self.detector_size[0], self.detector_size[1]), dtype=np.float32)
        self.pede_mask = np.zeros((self.detector_size[0], self.detector_size[1]), dtype=np.float32)

        #self.flip = [-1, ]
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
            with h5py.File(self.gain_corrections_filename) as gain_corrections_file:
                           self.gain_corrections = gain_corrections_file[self.gain_corrections_dataset][:]

        if self.pede_corrections_filename != "" and self.pede_corrections_dataset != "":
            with h5py.File(self.pede_corrections_filename) as pede_corrections_file:
                self.pede_corrections = pede_corrections_file[self.pede_corrections_dataset][:]
                if self.pede_mask_dataset != "":
                    self.pede_mask = pede_corrections_file[self.pede_mask_dataset][:]

        if len(self.gain_corrections.shape) != 3 or len(self.pede_corrections.shape) != 3:
            self.log.error("Gain and pede corrections must be provided in a 3D array, e.g. [G0, G1, G2, HG0]. Provided respectively %s and %s. Will not apply corrections" % (self.gain_corrections.shape, self.pede_corrections.shape))
            raise ValueError("Gain and pede corrections must be provided in a 3D array, e.g. [G0, G1, G2, HG0]. Provided respectively %s and %s. Will not apply corrections" % (self.gain_corrections.shape, self.pede_corrections.shape))

        if self.is_HG0:
            self.log.info("Setup HG0 corrections")
            self.pede_corrections[0] = self.pede_corrections[3]
            self.gain_corrections[0] = self.gain_corrections[3]
            
        self.log.info("Gain and pede corrections will be applied")
        self.metrics.set("activate_corrections", self.activate_corrections)
        self.metrics.set("activate_corrections_preview", self.activate_corrections_preview)

    def send(self, data):
        # FIXME
        timeout = max(2. * self.period, 1)

        ref_time = time()
        # frame_comp_time = time()
        frame_comp_counter = 0
        is_good_frame = int(True)

        # need to stay here because of numba
        # for gain plus data masking
        mask = int('0b' + 14 * '1', 2)
        mask2 = int('0b' + 2 * '1', 2)

        pulseid = -1
        # getting data from RB



        if self.expand_gaps :  ### True expansion (GAPS) is enabled, False expansion is disabled
            for i in range(2):
                self.exp_module_size[i]=self.module_size[i]+self.gap_px_chip[i]*(self.chips_module[i]-1)            
        else:
            for i in range(2):
                self.exp_module_size[i]=self.module_size[i]

        
        if self.modules_orig_x != []:
            if self.activate_corrections or (self.activate_corrections_preview and self.name == "preview"):
                data_with_geom = np.zeros([max(self.modules_orig_x) + self.exp_module_size[0], max(self.modules_orig_y) + self.exp_module_size[1]], dtype=np.float32)
            else:
                data_with_geom = np.zeros([max(self.modules_orig_x) + self.exp_module_size[0], max(self.modules_orig_y) + self.exp_module_size[1]], dtype=np.uint16)


        while True:
            ti = time()
            if(self.counter >= self.n_frames and self.n_frames != -1) or (ti - ref_time > timeout):
                self.log.debug("Timeout %d / %d, %.2f on pulseid %d" % (self.n_frames, self.counter, ti - ref_time, pulseid))
                break

            self.rb_current_slot = rb.claim_next_slot(self.rb_reader_id)

            if self.rb_current_slot == -1:
                #self.log.debug("No RB slot")
                continue

            rb_header_slot = rb.get_buffer_slot(self.rb_hbuffer_id, self.rb_current_slot)
            pointerh = ctypes.cast(rb_header_slot, ctypes.POINTER(self.HEADER))

            # check that all frame numbers are the same
            try:
                framenum = copy(pointerh.contents[0].framemetadata[0])
                self.log.debug("Preparing to send rb_current_slot %d, framenum %d", self.rb_current_slot, framenum)

                daq_recs = [pointerh.contents[i].framemetadata[5] for i in range(self.n_submodules)]
                framenums = [pointerh.contents[i].framemetadata[0] for i in range(self.n_submodules)]
                pulseids = [pointerh.contents[i].framemetadata[4] for i in range(self.n_submodules)]
                framenum = copy(pointerh.contents[0].framemetadata[0])
                pulseid = pointerh.contents[0].framemetadata[4]
                daq_rec = pointerh.contents[0].framemetadata[5]
                mod_numbers = [pointerh.contents[i].framemetadata[6] for i in range(self.n_submodules)]
                mod_enabled = [pointerh.contents[i].framemetadata[7] for i in range(self.n_submodules)]
                if self.check_framenum:
                    is_good_frame = int(len(set(framenums)) == 1)
            except:
                # FIXME: not clear why I get here
                print(rb.gf_perror())
                self.log.error("[%s] RB buffers: Header %s Data %s" % (self.name, self.rb_hbuffer_id, self.rb_hbuffer_id))
                # rb.gf_get_error does not work
                self.log.error("[%s] RB got error %s" % (self.name, rb.gf_get_error()))
                self.log.error("[%s] Issues with getting the RB header pointer (it is %r), current_slot: %d, first frame %d, recv_frame: %d. Casting exception" % 
                               (self.name, bool(pointerh), self.rb_current_slot, self.first_frame, self.recv_frames))
                self.log.error(sys.exc_info())
                raise RuntimeError

            if self.first_frame == 0:
                self.log.info("First frame got: %d pulse_id: %d" % (framenum, pulseid))
                self.first_frame = framenum

            if self.reset_framenum:
                framenum -= self.first_frame

            self.recv_frames += 1

            # Use the modulo and every_s only for the preview strem.
            # TODO: Refactor this in separate class.
            if self.name == "preview":

                # TODO: use milliseconds
                if self.send_every_s != 0:
                   if framenum != 0 and (time() - self.send_time) < self.send_every_s:

                        if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                           self.log.error("RINGBUFFER: CANNOT COMMIT SLOT on send_every_s.")

                        continue

                # TODO: Modulo currently works on the consequtive received frame - pulse_id for JF?
                elif self.preview_modulo != 0:
                    if (self.recv_frames + self.preview_modulo_offset) % self.preview_modulo:

                        if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                            self.log.error("RINGBUFFER: CANNOT COMMIT SLOT on send_modulo.")

                        continue

            self.send_time = time()

            # check if packets are missing
            missing_packets = sum([pointerh.contents[i].framemetadata[1] for i in range(self.n_submodules)])
            #missing_packets = 0
            is_good_frame = missing_packets == 0
            if missing_packets != 0:
                self.log.warning("Frame %d lost frames %d" % (framenum, missing_packets))
                self.frames_with_missing_packets += 1
                self.total_missing_packets += missing_packets

            entry_size_in_bytes = rb.get_buffer_stride_in_byte(self.rb_dbuffer_id)
            pointer = rb.get_buffer_slot(self.rb_dbuffer_id, self.rb_current_slot)
            
            data = np.ctypeslib.as_array(pointer, (int(entry_size_in_bytes / (self.bit_depth / 8)), ), ).reshape(self.detector_size)

            self.log.debug("Got Frame %d %d" % (framenum, pulseid))

            self.counter += 1
            #self.metrics.set("received_frames", {"name": self.name, "total": self.recv_frames, "incomplete": self.frames_with_missing_packets, "packets_lost": self.total_missing_packets, "epoch": time()})


            if self.flip[0] != -1:
                if len(self.flip) == 1:
                    data = np.ascontiguousarray(np.flip(data, self.flip[0]))
                else:
                    data = np.ascontiguousarray(np.flip(np.flip(data, 0), 1))

            if self.activate_corrections or (self.name == "preview" and self.activate_corrections_preview):
                #t_i = time()
                data = do_corrections(data.shape[0], data.shape[1], data, self.gain_corrections, self.pede_corrections, self.pede_mask, mask, mask2)
                #self.log.debug("Correction took %.3f seconds" % (time() - t_i))
                self.sent_frames += 1


            if self.name == "preview":
                if self.expand_gaps :  ### True expansion (GAPS) is enabled, False expansion is disabled 
                    data = expand_image(data, self.geometry, self.gap_px_module, self.gap_px_chip, self.chips_module)
                
                if self.modules_orig_x != []:
                    for i in range(self.n_modules):
                        data_with_geom[self.modules_orig_x[i]:self.modules_orig_x[i] + self.exp_module_size[0], 
                                       self.modules_orig_y[i]:self.modules_orig_y[i] + self.exp_module_size[1]] = data[i * self.exp_module_size[0]:(i + 1) *  self.exp_module_size[0], :]
                    
                    data = np.zeros((data_with_geom.shape[1],data_with_geom.shape[0]), dtype=data_with_geom.dtype)
                    data = np.rot90(data_with_geom).copy()

                if self.stripsel_module:
                    data = convert_stripsel(data)

            try:
                
                metadata = {
                  "frame": framenum, 
                  "daq_rec": daq_rec, 
                  "pulse_id": pulseid, 
                  "is_good_frame": int(is_good_frame), 
                  "daq_recs": daq_recs, 
                  "pulse_ids": pulseids, 
                  "framenums": framenums,                        
                  "pulse_id_diff": [pulseids[0] - i for i in pulseids], 
                  "framenum_diff": [framenums[0] - i for i in framenums], 
                  "missing_packets_1": [pointerh.contents[i].framemetadata[2] for i in range(self.n_submodules)], 
                  "missing_packets_2": [pointerh.contents[i].framemetadata[3] for i in range(self.n_submodules)],
                  "module_number": mod_numbers,
                  "module_enabled": mod_enabled
                }

                self.send_array(self.skt, data, metadata=metadata, copy=True)
                
            except:
                self.log.error("Error in sending array: %s" % sys.exc_info()[1])

            self.metrics.set("sent_frames", {"name": self.name, "total": self.sent_frames, "epoch": time()})

            frame_comp_counter += 1
            ref_time = time()

            if not rb.commit_slot(self.rb_reader_id, self.rb_current_slot):
                self.log.error("RINGBUFFER: CANNOT COMMIT SLOT")
                #break
            #except KeyboardInterrupt:
            #    raise StopIteration
        #self.outfile.close()


        self.log.debug("Writer loop exited")
        #self.log.info("received_frames %s" % ({"name": self.name, "total": self.recv_frames, "incomplete": self.frames_with_missing_packets, "packets_lost": self.total_missing_packets, "epoch": time()}))
        #self.log.info("sent_frames %s" % {"name": self.name, "total": self.sent_frames, "epoch": time()})
        self.pass_on(self.counter)
        return(self.counter)
    
        
    def send_array(self, socket, A, flags=0, copy=False, track=True, metadata={}):
        """send a numpy array with metadata"""
        metadata["htype"] = "array-1.0"
        metadata["type"] = str(A.dtype)
        metadata["shape"] = A.shape

        self.log.info("[%s] Sending frame %d", self.name, metadata["frame"])
        self.log.debug("[%s] Frame %d metadata %s", self.name, metadata["frame"], metadata)

        socket.send_json(metadata, flags | zmq.SNDMORE)
        return socket.send(A, flags, copy=copy, track=track)

