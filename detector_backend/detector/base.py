class BaseDetector(object):

    def __init__(self,
                 name,
                 module_size,
                 submodule_size,
                 n_submodules,
                 gap_px_chips,
                 gap_px_modules
                 ):
        self.name = name
        self.module_size = module_size
        self.submodule_size = submodule_size
        self.n_submodules = n_submodules
        self.gap_px_chips = gap_px_chips
        self.gap_px_modules = gap_px_modules

EIGER = BaseDetector(
    name="Eiger",
    module_size=[512, 1024],
    submodule_size=[256, 512],
    n_submodules=4,
    gap_px_chips=[2, 2],
    gap_px_modules=[36, 8]
)


class DetectorConfiguration(object):

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
        pass



