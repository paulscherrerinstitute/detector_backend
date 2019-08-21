import unittest
from detector_backend.detectors import DetectorDefinition, JUNGFRAU
from detector_backend.module.rb_assembler import ImageAssembler
from detector_backend.utils_ringbuffer import create_rb_files
from tests.utils import cleanup_rb_files


class RbAssemblerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        create_rb_files(100, 64, 2 * 512 * 256)

    @classmethod
    def tearDownClass(cls):
        cleanup_rb_files()

    def test_ImageAssembler(self):

        jf_test_det = DetectorDefinition(
            detector_name="Test JF 4.5M",
            detector_model=JUNGFRAU,
            geometry=[1, 9],
            bit_depth=16
        )

        with self.assertRaisesRegex(ValueError, "Wrong number of assemblers"):
            ImageAssembler(jf_test_det, 0, 7)

        n_assemblers = 4
        image_assember = ImageAssembler(jf_test_det, 0, n_assemblers)
        self.assertEqual(image_assember.n_bytes_buffer_size * n_assemblers, jf_test_det.image_data_n_bytes,
                         "All assemblers combined should give the complete image.")


if __name__ == "__main__":
    unittest.main()