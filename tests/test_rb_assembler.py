import unittest

from detector_backend.assemblers import JungfrauAssembler
from detector_backend.detectors import DetectorDefinition, JUNGFRAU
from detector_backend.module.rb_assembler import ImageAssembler
from detector_backend.utils_ringbuffer import create_rb_files
from tests.utils import cleanup_rb_files


class RbAssemblerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        create_rb_files(100, 64, 2 * 512 * 256, 2 * 540 * 256)

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
            ImageAssembler(JungfrauAssembler(jf_test_det), 0, 7)

        total_moves = jf_test_det.raw_image_data_n_bytes // jf_test_det.submodule_line_n_bytes

        for n_assemblers in range(1, 12):
            with self.subTest(n_assemblers=n_assemblers):
                if total_moves % n_assemblers == 0:

                    image_assember = ImageAssembler(JungfrauAssembler(jf_test_det), 0, n_assemblers)
                    self.assertEqual(image_assember.n_moves * n_assemblers, total_moves,
                                     "All assemblers combined should combine the entire image.")

                    self.assertEqual(len(image_assember.move_offsets), image_assember.n_moves)
                    self.assertEqual(len(image_assember.move_offsets) * n_assemblers, total_moves)

                else:
                    with self.assertRaisesRegex(ValueError, "Wrong number of assemblers"):
                        ImageAssembler(JungfrauAssembler(jf_test_det), 0, n_assemblers)

    def test_ImageAssembler_move_offsets(self):

        jf_test_det = DetectorDefinition(
            detector_name="Test JF 4.5M",
            detector_model=JUNGFRAU,
            geometry=[3, 9],
            bit_depth=16
        )

        jf_assembler = JungfrauAssembler(jf_test_det)
        total_moves = jf_test_det.raw_image_data_n_bytes // jf_test_det.submodule_line_n_bytes

        for n_assemblers in range(1, 20):

            if n_assemblers % total_moves != 0:
                continue

            with self.subTest(n_assemblers=n_assemblers):
                total_moves = []

                for i_assembler in range(n_assemblers):
                    image_assember = ImageAssembler(JungfrauAssembler(jf_test_det),
                                                    i_assembler,
                                                    n_assemblers)

                    total_moves += image_assember.move_offsets

                self.assertListEqual(total_moves, jf_assembler.get_move_offsets())


if __name__ == "__main__":
    unittest.main()
