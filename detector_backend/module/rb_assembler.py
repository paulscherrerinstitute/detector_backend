import ctypes
import os
from _ctypes import POINTER
from logging import getLogger
import ringbuffer as rb

from time import time, sleep

from detector_backend import config
from detector_backend.config import MPI_COMM_DELAY
from detector_backend.detectors import DetectorDefinition
from detector_backend.mpi_control import MpiControlClient
from detector_backend.mpi_ringbuffer import MpiRingBufferClient
from detector_backend.utils_ringbuffer import get_frame_metadata, get_frame_data

_logger = getLogger("rb_assembler")


class ImageAssembler(object):
    def __init__(self, detector_def: DetectorDefinition, assembler_index, n_total_assemblers):
        self.detector_def = detector_def
        self.assembler_index = assembler_index
        self.n_total_assemblers = n_total_assemblers

        _logger.info("Creating assembler_index=%d out of n_total_assemblers=%d",
                     self.assembler_index, self.n_total_assemblers)

        if self.detector_def.detector_size[0] % self.n_total_assemblers != 0:
            raise ValueError("Wrong number of assemblers. "
                             "Assembled image of height=%d is not divisible by n_total_assemblers=%s"
                             % (self.detector_def.detector_size[0], self.n_total_assemblers))

        self.n_bytes_per_move = detector_def.submodule_line_n_bytes

        total_required_moves = detector_def.raw_image_data_n_bytes // self.n_bytes_per_move
        if total_required_moves % self.n_total_assemblers != 0:
            raise ValueError("Wrong number of assemblers. "
                             "The total_required_moves=%d is not divisible by n_total_assemblers=$s"
                             % (total_required_moves, n_total_assemblers))

        self.n_moves = total_required_moves // self.n_total_assemblers

        self.move_offsets = self._get_move_offsets()

        if len(self.move_offsets) != self.n_moves:
            raise ValueError("The move offset calculation went wrong."
                             "The number of n_moves=%s should be the same as the len(move_offsets)=%d"
                             % (self.n_moves, len(self.move_offsets)))

    @staticmethod
    def get_image_assembler_function():
        expected_library_location = os.path.dirname(os.path.realpath(__file__)) + "/../../libimageassembler.so"

        try:
            _mod = ctypes.cdll.LoadLibrary(expected_library_location)

            assemble_image = _mod.assemble_image
            assemble_image.argtypes = (ctypes.c_char_p, POINTER(ctypes.c_size_t), ctypes.c_uint32, ctypes.c_size_t)
            assemble_image.restype = ctypes.c_int

            return assemble_image

        except:
            _logger.error("Could not image assembler shared library from %s." % expected_library_location)

    def _get_move_offsets(self):
        # TODO: Implement this.
        return []


def read_frame(detector_def: DetectorDefinition, metadata_pointer, data_pointer):
    data_shape = [detector_def.n_submodules_total] + detector_def.detector_model.submodule_size

    data = get_frame_data(data_pointer, data_shape)
    metadata = get_frame_metadata(metadata_pointer, detector_def.n_submodules_total)

    return data, metadata


def start_rb_assembler(name, detector_def: DetectorDefinition, ringbuffer: MpiRingBufferClient,
                       assembler_index, n_total_assemblers):

    _logger.info("Starting assembler with name='%s'." % name)

    ringbuffer.init_buffer()

    control_client = MpiControlClient()

    mpi_ref_time = time()

    image_assembler = ImageAssembler(detector_def=detector_def,
                                     assembler_index=assembler_index,
                                     n_total_assemblers=n_total_assemblers)

    # Function signature:
    # char* source_root, char* destination_root, size_t* dest_move_offsets, uint32_t n_moves, size_t n_bytes_per_move
    assemble_image = image_assembler.get_image_assembler_function()

    dest_move_offsets = image_assembler.move_offsets
    n_moves = image_assembler.n_moves
    n_bytes_per_move = image_assembler.n_bytes_per_move

    while True:

        if (time() - mpi_ref_time) > MPI_COMM_DELAY:

            # TODO: Currently the only message is a reset message.
            if control_client.is_message_ready():
                control_client.get_message()
                ringbuffer.reset()
                _logger.info("[%s] Ringbuffer reset." % name)

            mpi_ref_time = time()

        rb_current_slot = rb.claim_next_slot(ringbuffer.rb_consumer_id)
        if rb_current_slot == -1:
            sleep(config.RB_RETRY_DELAY)
            continue

        raw_data_pointer = rb.get_buffer_slot(ringbuffer.rb_raw_dbuffer_id, rb_current_slot)
        assembled_data_pointer = rb.get_buffer_slot(ringbuffer.rb_assembled_dbuffer_id, rb_current_slot)

        assemble_image(raw_data_pointer, assembled_data_pointer, dest_move_offsets, n_moves, n_bytes_per_move)

        if not rb.commit_slot(ringbuffer.rb_consumer_id, rb_current_slot):
            error_message = "[%s] Cannot commit rb slot %d." % (name, rb_current_slot)
            _logger.error(error_message)

            raise RuntimeError(error_message)
