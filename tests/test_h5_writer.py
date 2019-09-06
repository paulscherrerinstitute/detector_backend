import os
import unittest

import h5py
import numpy

from detector_backend.detectors import DetectorDefinition, JUNGFRAU
from detector_backend.module.h5_writer import H5Writer, DEFAULT_PARAMETERS_VALUE, IMAGE_DATASET_NAME


class H5WriterTests(unittest.TestCase):
    TEST_FILENAME = "test_file.h5"

    def setUp(self):
        if os.path.isfile(self.TEST_FILENAME):
            os.remove(self.TEST_FILENAME)   

    def tearDown(self):
        if os.path.isfile(self.TEST_FILENAME):
            os.remove(self.TEST_FILENAME)   

    def test_H5Writer_normal_workflow(self):

        n_images = 10

        jf_test_det = DetectorDefinition(
            detector_name="Test JF 4.5M",
            detector_model=JUNGFRAU,
            geometry=[3, 9],
            bit_depth=16
        )

        parameters = {
            "general/created": "Hamster",
            "general/instrument": "drums",
            "general/user": "the best",
        }

        writer = H5Writer(jf_test_det, self.TEST_FILENAME, parameters)

        image_data = numpy.zeros(shape=jf_test_det.detector_size, dtype="uint%d" % jf_test_det.bit_depth)

        for i in range(n_images):
            image_data.fill(i)
            writer.write_image(image_data.tobytes())

            metadata = {
                "pulse_id": i,
                "frame": i+100,
                "is_good_frame": 1,
                "daq_rec": -1,

                "missing_packets_1": [1] * jf_test_det.n_submodules_total,
                "missing_packets_2": [2] * jf_test_det.n_submodules_total,
                "daq_recs": [-1] * jf_test_det.n_submodules_total,

                "pulse_ids": [i] * jf_test_det.n_submodules_total,
                "framenums": [i+100] * jf_test_det.n_submodules_total,
            }
            writer.write_metadata(metadata)

        writer.close()

        file = h5py.File(self.TEST_FILENAME)

        for name, value in parameters.items():
            self.assertEqual(value, file[name][()].decode())

        self.assertEqual(file["/general/process"][()].decode(), DEFAULT_PARAMETERS_VALUE)
        self.assertEqual(file["/general/detector_name"][()].decode(), jf_test_det.detector_name)

        self.assertTrue(IMAGE_DATASET_NAME % jf_test_det.detector_name in file)
        images = file[IMAGE_DATASET_NAME % jf_test_det.detector_name]
        self.assertListEqual(list(images.shape), [n_images] + jf_test_det.detector_size)

        for i in range(n_images):
            self.assertEqual(images[i].min(), i)
            self.assertEqual(images[i].min(), images[i].max())

        file.close()

        # TODO: Test metadata length.
        # TODO: Test non defined parameters
        # TODO: Test custom datasets in parameters
