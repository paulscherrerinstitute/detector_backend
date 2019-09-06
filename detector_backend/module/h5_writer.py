import logging

import h5py as h5py
import numpy

from detector_backend.detectors import DetectorDefinition

_logger = logging.getLogger("h5_writer")


IMAGE_DATASET_NAME = "/data/"
INITIAL_IMAGE_DATASET_SIZE = 1000
METADATA_DATASET_NAME_FORMAT = "/data/%s/%s"

# metadata_name: (metdata_type, per_module)
METADATA_MAPPING = {
    "pulse_id": ("uint64", False),
    "frame": ("uint64", False),
    "is_good_frame": ("uint64", False),
    "daq_rec": ("int64", False),

    "missing_packets_1": ("uint64", True),
    "missing_packets_2": ("uint64", True),
    "daq_recs": ("daq_recs", True),

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
        self.image_dataset = None

        self.file = h5py.File(output_file, 'w')

        self._prepare_format_datasets()

        self.image_dataset = self.file.create_dataset(
            name="/data/%s/data" % self.detector_def.detector_name,
            shape=tuple([INITIAL_IMAGE_DATASET_SIZE] + self.detector_def.detector_size),
            maxshape=tuple([None] + self.detector_def.detector_size),
            chunks=tuple([1] + self.detector_def.detector_size),
            dtype="uint%d" % self.detector_def.bit_depth,
        )

        self.cache = {}

    def _prepare_format_datasets(self):

        self.file.create_dataset("/general/created",
                                 data=numpy.string_(self.parameters.get("general/created", "not given")))

        self.file.create_dataset("/general/instrument",
                                 data=numpy.string_(self.parameters.get("general/instrument", "not given")))

        self.file.create_dataset("/general/process",
                                 data=numpy.string_(self.parameters.get("general/process", "not given")))

        self.file.create_dataset("/general/user",
                                 data=numpy.string_(self.parameters.get("general/user", "not given")))

        self.file.create_dataset("/general/detector_name",
                                 data=numpy.string_(self.detector_def.detector_name))

    def write_image(self, image_bytes):
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


def start_writing():
    pass
