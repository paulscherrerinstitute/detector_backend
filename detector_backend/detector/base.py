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


