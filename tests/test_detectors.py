import unittest

from detector_backend.detectors import DetectorDefinition, JUNGFRAU


class TestDetectors(unittest.TestCase):

    def test_DetectorDefinition_JF(self):

        geometry = [1, 9]

        det_def = DetectorDefinition(
            detector_name="",
            detector_model=JUNGFRAU,
            geometry=geometry,
            bit_depth=16
        )

        self.assertEqual(det_def.detector_size_raw, det_def.detector_size,
                         "Raw and assembled image should be the same.")
        self.assertEqual(det_def.image_data_n_bytes, det_def.raw_image_data_n_bytes,
                         "The n_bytes in the raw and assembled image should be the same.")
        self.assertEqual(det_def.submodule_data_n_bytes * det_def.n_submodules_total, det_def.image_data_n_bytes,
                         "All submodules summed together should give the complete image.")
        self.assertEqual(det_def.n_submodules_total, geometry[0] * geometry[1],
                         "If you multiply the detector geometry together you should get the number of modules.")

        self.assertEqual(det_def.detector_size[0], det_def.detector_model.submodule_size[0] * geometry[0],
                         "Width of the detector should be multiple of the single module size.")
        self.assertEqual(det_def.detector_size[1], det_def.detector_model.submodule_size[1] * geometry[1],
                         "Height of the detector should be multiple of the single module size.")

        self.assertEqual((det_def.detector_size[1] * det_def.bit_depth)//8, det_def.image_line_n_bytes)


if __name__ == "__main__":
    unittest.main()
