from logging import getLogger
import ringbuffer as rb

import ctypes
import numpy as np
import zmq

from time import time, sleep

from detector_backend.config import MPI_COMM_DELAY
from detector_backend.mpi_control import MpiControlClient

_logger = getLogger("zmq_sender")

RB_RETRY_DELAY = 0.01
ZMQ_IO_THREADS = 4


class CRingBufferImageHeaderData(ctypes.Structure):
    _fields_ = [("framemetadata", ctypes.c_uint64 * 8), ]


class DetectorZMQSender(object):

    def __init__(self, name, socket, ringbuffer, detector_def, reset_frame_number=False):

        self.name = name
        self.socket = socket
        self.ringbuffer = ringbuffer
        self.detector_def = detector_def
        self.reset_frame_number = reset_frame_number

        self.n_submodules = detector_def.n_submodules_total
        self.rb_image_header_pointer = CRingBufferImageHeaderData * self.n_submodules

        self.first_received_frame_number = 0

    def reset(self):
        self.first_received_frame_number = 0

    def send_frame(self, data, metadata, flags=0, copy=False, track=True):
        metadata["htype"] = "array-1.0"
        metadata["type"] = str(data.dtype)
        metadata["shape"] = data.shape

        _logger.info("[%s] Sending frame %d", self.name, metadata["frame"])
        _logger.debug("[%s] Frame %d metadata %s", self.name, metadata["frame"], metadata)

        self.socket.send_json(metadata, flags | zmq.SNDMORE)
        return self.socket.send(data, flags, copy=copy, track=track)

    def get_frame_data(self, data_pointer):
        data = np.ctypeslib.as_array(data_pointer, shape=self.detector_def.detector_size)
        return data

    def get_frame_metadata(self, metadata_pointer):
        metadata_struct = ctypes.cast(metadata_pointer, ctypes.POINTER(self.rb_image_header_pointer))

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

        metadata["is_good_frame"] = int(len(set(metadata["framenums"])) == 1 and missing_packets == 0)
        metadata["pulse_id_diff"] = [metadata["pulse_id"] - i for i in metadata["pulse_ids"]]
        metadata["framenum_diff"] = [metadata["frame"] - i for i in metadata["framenums"]]

        return metadata

    def read_data(self, rb_current_slot):

        try:
            metadata_pointer = rb.get_buffer_slot(self.ringbuffer.rb_hbuffer_id, rb_current_slot)
            metadata = self.get_frame_metadata(metadata_pointer)

            data_pointer = rb.get_buffer_slot(self.ringbuffer.rb_dbuffer_id, rb_current_slot)
            data = self.get_frame_data(data_pointer)

            frame_number = metadata["frame"]
            pulse_id = metadata["pulse_id"]

            _logger.debug("Retrieved data and metadata for frame %d, pulse_id %d.",
                          frame_number,
                          pulse_id)

        except:
            _logger.exception("Could not interpret data from ringbuffer for slot %d." % rb_current_slot)
            raise RuntimeError

        # Reset frame number if the detector does not do this by default (WT-JF?!).
        if self.first_received_frame_number == 0:
            _logger.info("First frame got: %d pulse_id: %d" % (frame_number, pulse_id))
            self.first_received_frame_number = frame_number

        if self.reset_frame_number:
            metadata["frame"] -= self.first_received_frame_number

        return metadata, data

    def send_data(self, metadata, data):

        try:
            self.send_frame(data, metadata, flags=zmq.NOBLOCK, copy=True)
            return True

        except zmq.EAGAIN:
            _logger.warning("[%s] Frame %d dropped because no receiver was available." % (self.name, metadata["frame"]))

        except:
            _logger.exception("[%s] Unknown error in sending frame %d." % (self.name, metadata["frame"]))

        return False


def start_writer_sender(name, bind_url, zmq_mode, detector_def, ringbuffer):

    _logger.info("Starting writer with name='%s', bind_url='%s', zmq_mode='%s'" %
                 (name, bind_url, zmq_mode))

    ringbuffer.init_buffer()

    context = zmq.Context(io_threads=ZMQ_IO_THREADS)
    socket = context.socket(zmq.__getattribute__(zmq_mode))
    socket.bind(bind_url)

    zmq_sender = DetectorZMQSender(name, socket, ringbuffer, detector_def)
    control_client = MpiControlClient()

    mpi_ref_time = time()

    while True:

        if (time() - mpi_ref_time) > MPI_COMM_DELAY:

            # TODO: Currently the only message is a reset message.
            if control_client.is_message_ready():
                control_client.get_message()
                ringbuffer.reset()
                _logger.info("[%s] Ringbuffer reset." % name)

            mpi_ref_time = time()

        rb_current_slot = rb.claim_next_slot(ringbuffer.rb_reader_id)
        if rb_current_slot == -1:
            sleep(RB_RETRY_DELAY)
            continue

        metadata, data = zmq_sender.read_data(rb_current_slot)

        zmq_sender.send_data(metadata, data)

        if not rb.commit_slot(ringbuffer.rb_reader_id, rb_current_slot):
            error_message = "[%s] Cannot commit rb slot %d." % (name, rb_current_slot)
            _logger.error(error_message)

            raise RuntimeError(error_message)


def start_preview_sender(name, bind_url, zmq_mode, detector_def, ringbuffer):
    # TODO: Implement real preview sender.
    start_writer_sender(name, bind_url, zmq_mode, detector_def, ringbuffer)
