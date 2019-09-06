import unittest

import numpy

from detector_backend.reconstruction.jungfrau import JungfrauAssembler
from detector_backend.detectors import DetectorDefinition, JUNGFRAU
from detector_backend.module.rb_assembler import ImageAssembler, get_image_assembler_function
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

        with self.assertRaisesRegex(ValueError, "must be smaller"):
            ImageAssembler(JungfrauAssembler(jf_test_det), 1, 1)

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

    def test_ImageAssembler_JF_image(self):
        det_def = DetectorDefinition(
            detector_name="",
            detector_model=JUNGFRAU,
            geometry=[4, 3],
            bit_depth=16
        )

        image_assembler = ImageAssembler(JungfrauAssembler(detector_def=det_def), 0, 1)

        raw_image = numpy.zeros(shape=[det_def.n_submodules_total] + det_def.detector_model.submodule_size,
                                dtype="uint%d" % det_def.bit_depth)
        final_image = numpy.zeros(shape=det_def.detector_size,
                                  dtype="uint%d" % det_def.bit_depth)
        move_offsets = numpy.array(image_assembler.move_offsets, dtype="uint32")

        n_packets_per_image = det_def.submodule_data_n_bytes // det_def.detector_model.bytes_data_per_packet
        n_lines_per_packet = det_def.detector_model.bytes_data_per_packet // det_def.submodule_line_n_bytes

        for i_submodule in range(det_def.n_submodules_total):
            for i_packet in range(n_packets_per_image):
                for i_line in range(n_lines_per_packet):
                    i_absolute_line = (i_packet * n_lines_per_packet) + i_line
                    fill_value = i_submodule * 1000 + i_absolute_line

                    raw_image[i_submodule][i_absolute_line].fill(fill_value)

        assemble_image = get_image_assembler_function()

        # TODO: Segmentation fault. Check the C pointers from the numpy array first.
        # assemble_image(raw_image.ctypes.data_as(ctypes.c_char_p),
        #                final_image.ctypes.data_as(ctypes.c_char_p),
        #                move_offsets.ctypes.data_as(POINTER(ctypes.c_size_t)),
        #                image_assembler.n_moves,
        #                10)


if __name__ == "__main__":
    unittest.main()
