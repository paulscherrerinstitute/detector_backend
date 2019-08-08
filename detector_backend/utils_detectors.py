from numpy import array
from detector_backend.detectors import DetectorDefinition


def get_current_module_offset_in_pixels(detector_def: DetectorDefinition, module_id, submodule_id):

    detector_size = detector_def.detector_size

    module_size = detector_def.detector_model.module_size
    module_idx = get_module_coordinates(detector_def, module_id)

    submodule_size = detector_def.detector_model.submodule_size
    submodule_idx = get_submodule_coordinates(submodule_id)
    submodule_n = detector_def.detector_model.n_submodules_per_module

    gap_px_chips = detector_def.detector_model.gap_px_chips
    gap_px_modules = detector_def.detector_model.gap_px_modules

    # Origin of the module within the detector, (0, 0) is bottom left
    mod_origin = detector_size[1] * module_idx[0] * module_size[0] + module_idx[1] * module_size[1]
    # Inter chip gaps plus inter module gap
    mod_origin += module_idx[1] * ((submodule_n - 1) * gap_px_chips[1] + gap_px_modules[1])
    # Inter chip gaps plus inter module gap
    mod_origin += module_idx[0] * (gap_px_chips[0] + gap_px_modules[0]) * detector_size[1]

    # Origin of the submodule within the detector, relative to module origin
    mod_origin += detector_size[1] * submodule_idx[0] * submodule_size[0] + submodule_idx[1] * submodule_size[1]

    if submodule_idx[1] != 0:
        # 2* because there is the inter-quartermodule chip gap
        mod_origin += 2 * gap_px_chips[1]

    # the last takes into account extra space for chip gap within quarter module
    if submodule_idx[0] != 0:
        mod_origin += submodule_idx[0] * detector_size[1] * gap_px_chips[0]

    return mod_origin


def get_current_module_index(detector_def: DetectorDefinition, module_id, submodule_id):

    submodule_n = detector_def.detector_model.n_submodules_per_module
    module_idx = get_module_coordinates(detector_def, module_id)
    detector_size = detector_def.detector_size
    module_size = detector_def.detector_model.module_size

    # numbering inside the detector, growing over the x-axis
    mod_number = submodule_id + submodule_n * (module_idx[1] + module_idx[0] * detector_size[1] / module_size[1])

    return mod_number


def get_module_coordinates(detector_def: DetectorDefinition, module_id):

    # Column-first numeration
    if detector_def.detector_model.column_first_indexing:
        mod_indexes = array([module_id % detector_def.geometry[0],
                             int(module_id / detector_def.geometry[0])], dtype="int32", order='C')
    # Row-first numeration
    else:
        mod_indexes = array([int(module_id / detector_def.geometry[1]),
                             module_id % detector_def.geometry[1]], dtype="int32", order='C')

    return mod_indexes


def get_submodule_coordinates(submodule_id):
    return [int(submodule_id / 2), submodule_id % 2]


def get_n_lines_per_packet(detector_def:DetectorDefinition):
    bytes_in_line = (detector_def.detector_model.submodule_size[1] *
                     detector_def.bit_depth) // 8

    return detector_def.detector_model.bytes_data_per_packet // bytes_in_line


def get_n_packets_per_frame(detector_def: DetectorDefinition):
    n_pixels_in_frame = detector_def.detector_model.submodule_size[0] * \
                        detector_def.detector_model.submodule_size[1]

    # data_bytes_per_packet / (bit_depth/8)
    n_pixels_in_packet = (detector_def.detector_model.bytes_data_per_packet * 8) // \
                          detector_def.bit_depth

    return n_pixels_in_frame // n_pixels_in_packet


def get_n_bytes_per_frame_line(detector_def: DetectorDefinition):
    n_bytes = (detector_def.detector_size[1] * detector_def.bit_depth) // 8
    return n_bytes


def get_n_bytes_per_submodule_line(detector_def: DetectorDefinition):
    n_bytes = (detector_def.detector_model.submodule_size[1] * detector_def.bit_depth) // 8
    return n_bytes
