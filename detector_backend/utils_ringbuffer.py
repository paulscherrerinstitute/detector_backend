import ctypes
import os
from logging import getLogger

from mpi4py import MPI

from detector_backend import config
import ringbuffer as rb


_logger = getLogger(__name__)


class RingBuffer(object):

    def __init__(self,
                 process_id,
                 follower_ids,
                 detector_config,
                 rb_folder=config.DEFAULT_RB_FOLDER,
                 rb_head_file=config.DEFAULT_RB_HEAD_FILE,
                 rb_image_head_file=config.DEFAULT_RB_IMAGE_HEAD_FILE,
                 rb_image_data_file=config.DEFAULT_RB_IMAGE_DATA_FILE):

        self.process_id = process_id
        self.follower_ids = follower_ids
        self.detector_config = detector_config

        self.rb_folder = rb_folder
        self.rb_head_file = rb_head_file
        self.rb_image_head = rb_image_head_file
        self.rb_image_data = rb_image_data_file

        self.rb_header_id = None
        self.rb_reader_id = None
        self.rb_hbuffer_id = None
        self.rb_dbuffer_id = None

        self.image_header_n_bytes = None
        self.image_data_n_bytes = None

    def init_buffer(self, setup_header_file=False):

        if self.rb_header_id is not None:
            raise ValueError("Ring buffer already initialized. Cannot call init_buffer twice.")

        if setup_header_file:
            ret = rb.create_header_file(self.rb_head_file)

            if not ret:
                raise RuntimeError("Ring buffer files do not exist!")

            MPI.COMM_WORLD.barrier()

        else:
            MPI.COMM_WORLD.barrier()

            if not os.path.exists(self.rb_head_file):
                raise RuntimeError("File %s not available " % self.rb_head_file)

        self.rb_header_id = rb.open_header_file(self.rb_head_file)
        self.rb_reader_id = rb.create_reader(self.rb_header_id, self.process_id, self.follower_ids)
        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_image_head, self.rb_header_id, 0)
        self.rb_dbuffer_id = rb.attach_buffer_to_header(self.rb_image_data, self.rb_header_id, 0)

        self.image_header_n_bytes = self.detector_config.n_submodules_total * config.IMAGE_HEADER_SUBMODULE_SIZE_BYTES
        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, self.image_header_n_bytes)

        self.image_data_n_bytes = (self.detector_config.detector_size[0] *
                                   self.detector_config.detector_size[1] * self.detector_config.bit_depth) / 8
        rb.set_buffer_stride_in_byte(self.rb_dbuffer_id, self.image_data_n_bytes)

        n_slots = rb.adjust_nslots(self.rb_header_id)
        buffer_slot_type_name = 'c_uint' + str(self.detector_config.bit_depth)
        rb.set_buffer_slot_dtype(dtype=ctypes.__getattribute__(buffer_slot_type_name))

        _logger.info("RB %d slots: %d" % (self.rb_header_id, n_slots))
        _logger.info("RB header stride: %d" % rb.get_buffer_stride_in_byte(self.rb_hbuffer_id))
        _logger.info("RB data stride: %d" % rb.get_buffer_stride_in_byte(self.rb_dbuffer_id))
        _logger.info("RB buffer slot type name: %s" % buffer_slot_type_name)
