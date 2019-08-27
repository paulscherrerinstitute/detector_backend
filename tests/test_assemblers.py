import unittest

from detector_backend.assemblers import JungfrauAssembler
from detector_backend.detectors import DetectorDefinition, JUNGFRAU


class TestAssemblers(unittest.TestCase):

    def test_JungfrauAssembler(self):

        jf_test_det = DetectorDefinition(
            detector_name="Test JF 4.5M",
            detector_model=JUNGFRAU,
            geometry=[2, 2],
            bit_depth=16
        )

        assembler = JungfrauAssembler(detector_def=jf_test_det)

        offsets = assembler.get_move_offsets()

        # We are copying line by line.
        self.assertEqual(len(offsets), jf_test_det.raw_image_data_n_bytes // jf_test_det.submodule_line_n_bytes)

        self.assertEqual(len(set((x[0] for x in offsets))), len(offsets), "All source offsets should be unique.")
        self.assertEqual(len(set((x[1] for x in offsets))), len(offsets), "All target offsets should be unique.")
        self.assertTrue(all((x[0] >= 0 for x in offsets)), "All source offsets should be >= 0.")
        self.assertTrue(all((x[1] >= 0 for x in offsets)), "All target offsets should be >= 0.")

        for i_offset in range(1, len(offsets)):
            source_gap = offsets[i_offset][0] - offsets[i_offset-1][0]
            self.assertEqual(source_gap, jf_test_det.submodule_line_n_bytes, "Source offsets should be line by line.")

            target_gap = offsets[i_offset][1] - offsets[i_offset-1][1]
            # We just changed to the next module, which means different offset in target buffer.
            if i_offset % jf_test_det.detector_model.submodule_size[0] == 0:
                pass
            else:
                self.assertEqual(target_gap, jf_test_det.image_line_n_bytes, "Target offsets should be line by line.")

        self.assertTrue(max((x[0] for x in offsets)) < jf_test_det.raw_image_data_n_bytes,
                        "Max source offset should be smaller than total raw image size.")

        self.assertTrue(max((x[1] for x in offsets)) < jf_test_det.image_data_n_bytes,
                        "Max target offset should be smaller than total image size.")
