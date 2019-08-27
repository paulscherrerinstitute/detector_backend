from detector_backend import config


class DetectorModel(object):

    def __init__(self,
                 model_name,
                 module_size,
                 submodule_size,
                 n_submodules_per_module,
                 bytes_per_packet,
                 bytes_data_per_packet,
                 gap_px_chips,
                 gap_px_modules
                 ):
        self.model_name = model_name

        self.module_size = module_size
        self.submodule_size = submodule_size

        self.n_submodules_per_module = n_submodules_per_module

        self.bytes_per_packet = bytes_per_packet
        self.bytes_data_per_packet = bytes_data_per_packet

        self.gap_px_chips = gap_px_chips
        self.gap_px_modules = gap_px_modules


EIGER = DetectorModel(
    model_name="Eiger PSI",
    module_size=[512, 1024],
    submodule_size=[256, 512],
    n_submodules_per_module=4,
    bytes_per_packet=4144,
    bytes_data_per_packet=4096,
    gap_px_chips=[2, 2],
    gap_px_modules=[36, 8]
)


JUNGFRAU = DetectorModel(
    model_name="Jungfrau",
    module_size=[512, 1024],
    submodule_size=[512, 1024],
    n_submodules_per_module=1,
    bytes_per_packet=8246,
    bytes_data_per_packet=8192,
    gap_px_chips=[0, 0],
    gap_px_modules=[0, 0]
)


class DetectorDefinition(object):

    def __init__(self, detector_name, detector_model: DetectorModel, geometry, bit_depth, ignored_modules=None):

        self.detector_model = detector_model
        self.detector_name = detector_name
        self.geometry = geometry
        self.bit_depth = bit_depth
        self.ignored_modules = [] if ignored_modules is None else ignored_modules

        # Detector size without gaps.
        self.detector_size_raw = [detector_model.module_size[0] * self.geometry[0],
                                  detector_model.module_size[1] * self.geometry[1]]

        # Detector size including chip gaps.
        module_size_wgaps = [detector_model.module_size[0] + detector_model.gap_px_chips[0],
                             detector_model.module_size[1] + (detector_model.gap_px_chips[1] * 3)]

        self.detector_size = [module_size_wgaps[0] * self.geometry[0],
                              module_size_wgaps[1] * self.geometry[1]]

        # Detector size including module gaps.
        self.detector_size = [(self.geometry[0] - 1) * detector_model.gap_px_modules[0] + self.detector_size[0],
                              (self.geometry[1] - 1) * detector_model.gap_px_modules[1] + self.detector_size[1]]

        self.n_submodules_total = self.geometry[0] * self.geometry[1] * detector_model.n_submodules_per_module

        self.image_header_n_bytes = config.IMAGE_HEADER_SUBMODULE_SIZE_BYTES * self.n_submodules_total
        self.raw_image_data_n_bytes = (self.detector_size_raw[0] * self.detector_size_raw[1] * self.bit_depth) // 8
        self.image_data_n_bytes = (self.detector_size[0] * self.detector_size[1] * self.bit_depth) // 8
        self.submodule_data_n_bytes = (self.detector_model.submodule_size[0] *
                                       self.detector_model.submodule_size[1] * self.bit_depth) // 8

        self.submodule_line_n_bytes = (self.detector_model.submodule_size[1] * self.bit_depth) // 8
        self.image_line_n_bytes = (self.detector_size[1] * self.bit_depth) // 8
