from detector_backend.detector.base import BaseDetector


class EigerDetector(BaseDetector):

    def __init__(self,
                 name,
                 detector_size):

        super(EigerDetector, self).__init__(
            name=name,
            detector_size=detector_size,
            module_size=[512, 1024],
            submodule_size=[256, 512],
            n_submodules=4,
            gap_px_chips=[2, 2],
            gap_px_modules=[36, 8]
        )
