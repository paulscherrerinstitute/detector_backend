from logging import getLogger
import ringbuffer as rb

import zmq

from time import time, sleep

from detector_backend.config import MPI_COMM_DELAY
from detector_backend.mpi_control import MpiControlClient
from detector_backend.utils_ringbuffer import get_frame_metadata, get_frame_data

_logger = getLogger("rb_assembler")

RB_RETRY_DELAY = 0.01
ZMQ_IO_THREADS = 4


def assemble_frame(metadata_pointer, data_pointer):
    pass

def start_rb_assembler(name, detector_def, ringbuffer):

    _logger.info("Starting assembler with name='%s'." % name)

    ringbuffer.init_buffer()

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

        # TODO: Do the actual conversion.

        if not rb.commit_slot(ringbuffer.rb_reader_id, rb_current_slot):
            error_message = "[%s] Cannot commit rb slot %d." % (name, rb_current_slot)
            _logger.error(error_message)

            raise RuntimeError(error_message)
