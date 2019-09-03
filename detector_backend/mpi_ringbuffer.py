import ctypes
import os
from logging import getLogger

from mpi4py import MPI

from detector_backend import config
import ringbuffer as rb
from detector_backend.detectors import DetectorDefinition

_logger_master = getLogger("mpi_ringbuffer_master")
_logger_client = getLogger("mpi_ringbuffer_client")


class MpiRingBufferMaster(object):

    def __init__(self, rb_folder=config.DEFAULT_RB_FOLDER):
        self.rb_header_file = rb_folder + config.RB_HEAD_FILE
        self.created = False

        self.rb_header_id = None

    def create_buffer(self):

        _logger_master.info("Creating ringbuffer header.")

        if self.created:
            raise RuntimeError("Cannot re-create active RB header.")

        _logger_master.debug("Creating header file %s", self.rb_header_file)
        ret = rb.create_header_file(self.rb_header_file)

        if not ret:
            raise RuntimeError("Cannot create ringbuffer header file.")

        _logger_master.debug("Signal to other processes to use the buffer.")

        # Allow all other processes to load the header.
        MPI.COMM_WORLD.barrier()

        self.rb_header_id = rb.open_header_file(self.rb_header_file)

        self.created = True

        _logger_master.info("Ringbuffer header created.")

    def reset_header(self):

        _logger_master.info("Resetting ringbuffer header.")

        if not self.created:
            raise RuntimeError("Cannot reset RB header before initializing it.")

        _logger_master.debug("Waiting for clients to reset the library.")

        # Wait for all processes to reset.
        MPI.COMM_WORLD.barrier()

        rb.reset_header(self.rb_header_id)

        _logger_master.debug("Signal to clients that the header is reset.")

        # Notify clients to init the RB.
        MPI.COMM_WORLD.barrier()

        _logger_master.info("Ringbuffer Header reset completed.")


class MpiRingBufferClient(object):

    def __init__(self,
                 process_id,
                 follower_ids,
                 detector_def: DetectorDefinition,
                 as_reader=True,
                 rb_folder=config.DEFAULT_RB_FOLDER):

        self.process_id = process_id
        self.follower_ids = follower_ids
        self.image_header_n_bytes = detector_def.image_header_n_bytes
        self.raw_image_data_n_bytes = detector_def.raw_image_data_n_bytes
        self.assembled_image_data_n_bytes = detector_def.image_data_n_bytes
        self.bit_depth = detector_def.bit_depth
        self.as_reader = as_reader

        self.rb_header_file = rb_folder + config.RB_HEAD_FILE
        self.rb_image_head_file = rb_folder + config.RB_IMAGE_HEAD_FILE
        self.rb_raw_image_data_file = rb_folder + config.RB_RAW_IMAGE_DATA_FILE
        self.rb_assembled_image_data_file = rb_folder + config.RB_ASSEMBLED_IMAGE_DATA_FILE

        self.rb_header_id = None
        self.rb_consumer_id = None
        self.rb_hbuffer_id = None
        self.rb_raw_dbuffer_id = None
        self.rb_assembled_dbuffer_id = None

        self.initialized = False

    def init_buffer(self):

        if self.initialized:
            raise RuntimeError("RB already initialized.")

        _logger_client.debug("[%d] Waiting for master to create header file.", self.process_id)

        # Wait for ringbuffer master to create the header file.
        MPI.COMM_WORLD.barrier()

        self._configure_buffer()

    def _configure_buffer(self):

        if not os.path.exists(self.rb_header_file):
            raise RuntimeError("RB header file %s not available " % self.rb_header_file)

        if not os.path.isfile(self.rb_image_head_file):
            raise RuntimeError("No image header file %s" % self.rb_raw_image_data_file)

        if not os.path.isfile(self.rb_raw_image_data_file):
            raise RuntimeError("No raw image data file %s" % self.rb_raw_image_data_file)

        if not os.path.isfile(self.rb_assembled_image_data_file):
            raise RuntimeError("No assembled image data file %s" % self.rb_assembled_image_data_file)

        self.rb_header_id = rb.open_header_file(self.rb_header_file)

        if self.as_reader:
            self.rb_consumer_id = rb.create_reader(self.rb_header_id, self.process_id, self.follower_ids)
        else:
            self.rb_consumer_id = rb.create_writer(self.rb_header_id, self.process_id, self.follower_ids)

        self.rb_hbuffer_id = rb.attach_buffer_to_header(self.rb_image_head_file,
                                                        self.rb_header_id, 0)

        self.rb_raw_dbuffer_id = rb.attach_buffer_to_header(self.rb_raw_image_data_file,
                                                            self.rb_header_id, 0)

        self.rb_assembled_dbuffer_id = rb.attach_buffer_to_header(self.rb_assembled_image_data_file,
                                                                  self.rb_header_id, 0)

        rb.set_buffer_stride_in_byte(self.rb_hbuffer_id, self.image_header_n_bytes)
        rb.set_buffer_stride_in_byte(self.rb_raw_dbuffer_id, self.raw_image_data_n_bytes)
        rb.set_buffer_stride_in_byte(self.rb_assembled_dbuffer_id, self.assembled_image_data_n_bytes)

        n_slots = rb.adjust_nslots(self.rb_header_id)
        buffer_slot_type_name = 'c_uint' + str(self.bit_depth)
        rb.set_buffer_slot_dtype(dtype=ctypes.__getattribute__(buffer_slot_type_name))

        _logger_client.debug("[%d] RB %d slots: %d", self.process_id, self.rb_header_id, n_slots)
        _logger_client.debug("[%d] RB header stride: %d",
                             self.process_id, rb.get_buffer_stride_in_byte(self.rb_hbuffer_id))
        _logger_client.debug("[%d] RB raw data stride: %d",
                             self.process_id, rb.get_buffer_stride_in_byte(self.rb_raw_dbuffer_id))
        _logger_client.debug("[%d] RB assembled data stride: %d",
                             self.process_id, rb.get_buffer_stride_in_byte(self.rb_assembled_dbuffer_id))

        _logger_client.debug("[%d] RB buffer slot type name: %s", self.process_id, buffer_slot_type_name)

        self.initialized = True

    def reset(self):

        if not self.initialized:
            raise RuntimeError("Cannot reset RB before initializing it.")

        rb.reset()

        # Signal to master to re-init the header.
        MPI.COMM_WORLD.barrier()

        # Wait for the master to re-init the header.
        MPI.COMM_WORLD.barrier()

        self._configure_buffer()
