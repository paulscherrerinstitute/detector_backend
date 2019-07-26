from detector_backend.starter import start_standard_setup
from detector_backend.detectors import DetectorDefinition, EIGER

eiger9m = DetectorDefinition(
    detector_name="cSAXS Eiger 9m",
    detector_model=EIGER,
    geometry=[6, 3],
    bit_depth=32
)

start_standard_setup(eiger9m, "test.conf")
