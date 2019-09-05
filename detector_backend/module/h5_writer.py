import logging

import h5py as h5py
import numpy

from detector_backend.detectors import DetectorDefinition

IMAGE_DATASET_NAME = "/data/"
INITIAL_IMAGE_DATASET_SIZE = 1000

_logger = logging.getLogger("h5_writer")


class H5Writer(object):
    def __init__(self, detector_def: DetectorDefinition, output_file="/dev/null", parameters=None):
        self.detector_def = detector_def
        self.output_file = output_file
        self.parameters = parameters or {}

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

    def write_medadata(self, metadata):
        for name, value in metadata.items():

            if name not in self.cache:
                self.cache[name] = []

            self.cache.append(value)

    def _flush_metadata(self):
        if not self.cache:
            return

        for name, value in self.cache.items():
            pass

    def close(self):
        self._flush_metadata()

        self.image_dataset.resize(size=self.image_write_index, axis=0)

        self.file.close()


def start_writing():
    pass
