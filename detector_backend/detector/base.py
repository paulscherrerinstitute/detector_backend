class BaseDetector(object):

    def __init__(self,
                 name,
                 module_size,
                 submodule_size,
                 n_submodules_per_module,
                 gap_px_chips,
                 gap_px_modules
                 ):
        self.name = name
        self.module_size = module_size
        self.submodule_size = submodule_size
        self.n_submodules = n_submodules_per_module
        self.gap_px_chips = gap_px_chips
        self.gap_px_modules = gap_px_modules


EIGER = BaseDetector(
    name="Eiger",
    module_size=[512, 1024],
    submodule_size=[256, 512],
    n_submodules_per_module=4,
    gap_px_chips=[2, 2],
    gap_px_modules=[36, 8]
)


class DetectorConfig(object):

    def __init__(self,
                 detector,
                 name,
                 geometry,
                 ignored_modules=None):

        self.detector = detector
        self.name = name
        self.geometry = geometry
        self.ignored_modules = [] if ignored_modules is None else ignored_modules
        self.detector_size = self.get_detector_size()

    def get_detector_size(self):

        module_size_wgaps = [self.module_size[0] + self.gap_chips[0],
                             self.module_size[1] + (self.gap_chips[1] * 3)]

        # Detector size including chip gaps.
        detector_size = [module_size_wgaps[0] * self.geometry[0],
                         module_size_wgaps[1] * self.geometry[1]]

        # Detector size including module gaps.
        detector_size = [(self.geometry[0] - 1) * self.gap_px_modules[0] + detector_size[0],
                         (self.geometry[1] - 1) * self.gap_px_modules[1] + detector_size[1]]

        return detector_size

    def get_receiver_ranks(self, offset=1):

        n_active_submodules = self.geometry[0] * self.geometry[1] * self.detector.n_submodules_per_module
        n_active_submodules -= len(self.ignored_modules)

        return [x+offset for x in range(n_active_submodules)]
