from logging import getLogger
import ringbuffer as rb

import zmq

from time import time, sleep

from detector_backend import config
from detector_backend.config import MPI_COMM_DELAY
from detector_backend.mpi_control import MpiControlClient
from detector_backend.utils_ringbuffer import get_frame_metadata, get_frame_data

_logger = getLogger("zmq_sender")

ZMQ_IO_THREADS = 4


class DetectorZMQSender(object):

    def __init__(self, name, socket, ringbuffer, detector_def, reset_frame_number=False):

        self.name = name
        self.socket = socket
        self.ringbuffer = ringbuffer
        self.detector_def = detector_def
        self.reset_frame_number = reset_frame_number

        self.n_submodules = detector_def.n_submodules_total

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

    def read_data(self, rb_current_slot):

        try:
            metadata_pointer = rb.get_buffer_slot(self.ringbuffer.rb_hbuffer_id, rb_current_slot)
            metadata = get_frame_metadata(metadata_pointer, self.n_submodules)

            data_pointer = rb.get_buffer_slot(self.ringbuffer.rb_dbuffer_id, rb_current_slot)
            data = get_frame_data(data_pointer, self.detector_def.detector_size)

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

    def reset(self):
        self.first_received_frame_number = 0


def start_writer_sender(name, bind_url, zmq_mode, detector_def, ringbuffer):

    _logger.info("Starting sender with name='%s', bind_url='%s', zmq_mode='%s'" %
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
                zmq_sender.reset()
                _logger.info("[%s] Ringbuffer reset." % name)

            mpi_ref_time = time()

        rb_current_slot = rb.claim_next_slot(ringbuffer.rb_reader_id)
        if rb_current_slot == -1:
            sleep(config.RB_RETRY_DELAY)
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
