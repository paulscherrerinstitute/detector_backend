import unittest

from detector_backend.reconstruction.jungfrau import JungfrauAssembler
from detector_backend.detectors import DetectorDefinition, JUNGFRAU


class TestAssemblers(unittest.TestCase):

    def test_JungfrauAssembler(self):

        def test_jf_assembly(detector_def):

            assembler = JungfrauAssembler(detector_def=detector_def)

            offsets = assembler.get_move_offsets()

            # We are copying line by line.
            self.assertEqual(len(offsets), detector_def.raw_image_data_n_bytes // detector_def.submodule_line_n_bytes)

            self.assertEqual(len(set((x[0] for x in offsets))), len(offsets), "All source offsets should be unique.")
            self.assertEqual(len(set((x[1] for x in offsets))), len(offsets), "All target offsets should be unique.")
            self.assertTrue(all((x[0] >= 0 for x in offsets)), "All source offsets should be >= 0.")
            self.assertTrue(all((x[1] >= 0 for x in offsets)), "All target offsets should be >= 0.")

            for i_offset in range(1, len(offsets)):
                source_gap = offsets[i_offset][0] - offsets[i_offset - 1][0]
                self.assertEqual(source_gap, detector_def.submodule_line_n_bytes,
                                 "Source offsets should be line by line.")

                target_gap = offsets[i_offset][1] - offsets[i_offset - 1][1]
                # We just changed to the next module, which means different offset in target buffer.
                if i_offset % detector_def.detector_model.submodule_size[0] == 0:
                    pass
                else:
                    self.assertEqual(target_gap, detector_def.image_line_n_bytes,
                                     "Target offsets should be line by line.")

            self.assertTrue(max((x[0] for x in offsets)) < detector_def.raw_image_data_n_bytes,
                            "Max source offset should be smaller than total raw image size.")

            self.assertTrue(max((x[1] for x in offsets)) < detector_def.image_data_n_bytes,
                            "Max target offset should be smaller than total image size.")

        for bit_depth in [8, 16, 32]:
            for geometry in [[1, 1], [2, 2], [2, 3], [3, 2], [9, 1], [1, 9]]:
                with self.subTest(geometry=geometry, bit_depth=bit_depth):
                    test_jf_assembly(DetectorDefinition(
                        detector_name="",
                        detector_model=JUNGFRAU,
                        geometry=geometry,
                        bit_depth=bit_depth
                    ))

    def test_JungfrauAssembler_coordinates(self):

        for bit_depth in [8, 16, 32]:
            for geometry in [[1, 1], [3, 3], [1, 3], [3, 1], [4, 3], [3, 4]]:
                with self.subTest(geometry=geometry, bit_depth=bit_depth):

                    assembler = JungfrauAssembler(
                        detector_def=DetectorDefinition(
                            detector_name="",
                            detector_model=JUNGFRAU,
                            geometry=geometry,
                            bit_depth=bit_depth
                        ))

                    i_submodule = 0
                    for y in range(geometry[0]):
                        for x in range(geometry[1]):

                            self.assertEqual((y, x),
                                             assembler._get_submodule_coordinates_in_image(i_submodule),
                                             "The expected and calculated submodule coordinates are not the same.")

                            i_submodule += 1

    def test_JungfrauAssembler_transparent(self):
        det_def = DetectorDefinition(
            detector_name="",
            detector_model=JUNGFRAU,
            geometry=[9, 1],
            bit_depth=16
        )

        assembler = JungfrauAssembler(detector_def=det_def)
        offsets = assembler.get_move_offsets()

        for move in offsets:
            self.assertEqual(move[0], move[1],
                             "The mapping should be one to one - transparent reconstruction.")
