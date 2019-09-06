import logging
from time import time, sleep
import ringbuffer as rb

import h5py as h5py
import numpy

from detector_backend import config
from detector_backend.config import MPI_COMM_DELAY
from detector_backend.detectors import DetectorDefinition
from detector_backend.mpi_control import MpiControlClient
from detector_backend.utils_ringbuffer import read_data_from_rb

_logger = logging.getLogger("h5_writer")


IMAGE_DATASET_NAME = "/data/%s/data"
INITIAL_IMAGE_DATASET_SIZE = 1000
METADATA_DATASET_NAME_FORMAT = "/data/%s/%s"
DEFAULT_PARAMETERS_VALUE = "not given"


# TODO: Do we really need per_module?
# metadata_name: (metdata_type, per_module)
METADATA_MAPPING = {
    "pulse_id": ("uint64", False),
    "frame": ("uint64", False),
    "is_good_frame": ("uint64", False),
    "daq_rec": ("int64", False),

    "missing_packets_1": ("uint64", True),
    "missing_packets_2": ("uint64", True),
    "daq_recs": ("uint64", True),

    "pulse_ids": ("uint64", True),
    "framenums": ("uint64", True),
}


class H5Writer(object):
    def __init__(self, detector_def: DetectorDefinition,
                 output_file="/dev/null",
                 parameters=None):
        self.detector_def = detector_def
        self.output_file = output_file
        self.parameters = parameters or {}

        _logger.info("Writing detector_name=%s to output_file=%s with parameters %s",
                     self.detector_def.detector_name, self.output_file, self.parameters)

        self.image_write_index = 0
        # TODO: Add possibility to write to /dev/null
        self.file = h5py.File(output_file, 'w')

        # TODO: Add possiblity to add custom datasets.
        self._prepare_format_datasets()

        self.image_dataset = self.file.create_dataset(
            name=IMAGE_DATASET_NAME % self.detector_def.detector_name,
            shape=tuple([INITIAL_IMAGE_DATASET_SIZE] + self.detector_def.detector_size),
            maxshape=tuple([None] + self.detector_def.detector_size),
            chunks=tuple([1] + self.detector_def.detector_size),
            dtype="uint%d" % self.detector_def.bit_depth,
        )

        self.cache = {}

    def _prepare_format_datasets(self):

        self.file.create_dataset("/general/created",
                                 data=numpy.string_(self.parameters.get("general/created",
                                                                        DEFAULT_PARAMETERS_VALUE)))

        self.file.create_dataset("/general/instrument",
                                 data=numpy.string_(self.parameters.get("general/instrument",
                                                                        DEFAULT_PARAMETERS_VALUE)))

        self.file.create_dataset("/general/process",
                                 data=numpy.string_(self.parameters.get("general/process",
                                                                        DEFAULT_PARAMETERS_VALUE)))

        self.file.create_dataset("/general/user",
                                 data=numpy.string_(self.parameters.get("general/user",
                                                                        DEFAULT_PARAMETERS_VALUE)))

        self.file.create_dataset("/general/detector_name",
                                 data=numpy.string_(self.detector_def.detector_name))

    def write_image(self, image_bytes):
        # TODO: Resize dataset.
        self.image_dataset.id.write_direct_chunk((self.image_write_index, 0, 0), image_bytes)
        self.image_write_index += 1

    def write_metadata(self, metadata):
        for name, value in metadata.items():

            if name not in self.cache:
                self.cache[name] = []

            self.cache[name].append(value)

    def _flush_metadata(self):
        if not self.cache:
            _logger.info("No metadata in cache. Returning")

        for name, value in self.cache.items():

            if name not in METADATA_MAPPING:
                _logger.warning("Metadata name=%s not in mapping. Will not be written to file.", name)
                continue

            dataset_name = METADATA_DATASET_NAME_FORMAT % (self.detector_def.detector_name, name)
            dtype = METADATA_MAPPING[name][0]

            _logger.debug("Creating dataset_name=%s and dtype=%s", dataset_name, dtype)

            dataset = numpy.array(value, dtype=dtype)
            self.file[dataset_name] = dataset

    def close(self):
        self._flush_metadata()

        self.image_dataset.resize(size=self.image_write_index, axis=0)
        _logger.debug("Image dataset to image_write_index=%s", self.image_write_index)

        self.file.close()
        _logger.info("Writing completed.")


def start_h5_writer(name, detector_def, ringbuffer):

    _logger.info("Starting h5 writer with name='%s'" % name)

    ringbuffer.init_buffer()

    writer = H5Writer(detector_def)
    control_client = MpiControlClient()

    mpi_ref_time = time()

    while True:

        if (time() - mpi_ref_time) > MPI_COMM_DELAY:

            # TODO: Currently the only message is a reset message.
            if control_client.is_message_ready():
                control_client.get_message()

                writer.close()
                writer = H5Writer(detector_def)

                _logger.info("[%s] Ringbuffer reset." % name)

            mpi_ref_time = time()

        rb_current_slot = rb.claim_next_slot(ringbuffer.rb_reader_id)
        if rb_current_slot == -1:
            sleep(config.RB_RETRY_DELAY)
            continue

        metadata, data = read_data_from_rb(
            rb_current_slot=rb_current_slot,
            rb_hbuffer_id=ringbuffer.rb_hbuffer_id,
            rb_dbuffer_id=ringbuffer.rb_dbuffer_id,
            n_submodules=detector_def.n_submodules_total,
            image_size=detector_def.detector_size
        )

        writer.write_image(data.tobytes())
        writer.write_metadata(metadata)

        if not rb.commit_slot(ringbuffer.rb_reader_id, rb_current_slot):
            error_message = "[%s] Cannot commit rb slot %d." % (name, rb_current_slot)
            _logger.error(error_message)

            raise RuntimeError(error_message)