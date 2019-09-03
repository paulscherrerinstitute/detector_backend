from detector_backend.detectors import DetectorDefinition


class JungfrauAssembler(object):
    def __init__(self, detector_def: DetectorDefinition):
        self.detector_def = detector_def

    def get_move_offsets(self):
        moves = []

        for i_submodule in range(self.detector_def.n_submodules_total):
            # Offset of submodule in raw RB before assembly.
            submodule_offset_in_source = i_submodule * self.detector_def.submodule_data_n_bytes

            (y, x) = self._get_submodule_coordinates_in_image(i_submodule)

            n_lines_per_submodule = self.detector_def.submodule_data_n_bytes // self.detector_def.submodule_line_n_bytes

            submodule_offset_in_target = (n_lines_per_submodule * self.detector_def.image_line_n_bytes * y) + \
                                         (self.detector_def.submodule_line_n_bytes * x)

            # Scan the submodule line by line and calculate target offsets in assembled image.
            for i_submodule_line in range(n_lines_per_submodule):
                # Offset in the raw buffer.
                source_offset = submodule_offset_in_source + \
                                (i_submodule_line * self.detector_def.submodule_line_n_bytes)

                # Offset in the assembled image.
                target_offset = submodule_offset_in_target + (i_submodule_line * self.detector_def.image_line_n_bytes)

                moves.append((source_offset, target_offset))

        return moves

    def _get_submodule_coordinates_in_image(self, i_submodule):
        """
        Calculate the submodule coordinates in the assembled image.
        :return (y, x): Coordinates of the submodule, coordinates origin: TOP LEFT corner.
        """
        y = i_submodule // self.detector_def.geometry[1]
        x = i_submodule % self.detector_def.geometry[1]

        # TODO: Change the numbering of modules in the detector config file.

        return y, x
