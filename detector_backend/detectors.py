class DetectorModel(object):

    def __init__(self,
                 model_name,
                 module_size,
                 submodule_size,
                 n_submodules_per_module,
                 gap_px_chips,
                 gap_px_modules
                 ):
        self.model_name = model_name
        self.module_size = module_size
        self.submodule_size = submodule_size
        self.n_submodules_per_module = n_submodules_per_module
        self.gap_px_chips = gap_px_chips
        self.gap_px_modules = gap_px_modules


EIGER = DetectorModel(
    model_name="Eiger PSI",
    module_size=[512, 1024],
    submodule_size=[256, 512],
    n_submodules_per_module=4,
    gap_px_chips=[2, 2],
    gap_px_modules=[36, 8]
)


class DetectorDefinition(object):

    def __init__(self, detector_name, detector_model, geometry, bit_depth, ignored_modules=None):

        self.detector_model = detector_model
        self.detector_name = detector_name

        self.geometry = geometry
        self.bit_depth = bit_depth

        self.ignored_modules = [] if ignored_modules is None else ignored_modules

        module_size_wgaps = [detector_model.module_size[0] + detector_model.gap_px_chips[0],
                             detector_model.module_size[1] + (detector_model.gap_px_chips[1] * 3)]

        # Detector size including chip gaps.
        self.detector_size = [module_size_wgaps[0] * self.geometry[0],
                              module_size_wgaps[1] * self.geometry[1]]

        # Detector size including module gaps.
        self.detector_size = [(self.geometry[0] - 1) * detector_model.gap_px_modules[0] + self.detector_size[0],
                              (self.geometry[1] - 1) * detector_model.gap_px_modules[1] + self.detector_size[1]]

        self.n_submodules_total = self.geometry[0] * self.geometry[1] * detector_model.n_submodules_per_module
