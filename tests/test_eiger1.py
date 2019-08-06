from detector_backend.starter import start_standard_setup
from detector_backend.detectors import DetectorDefinition, EIGER

eiger1m = DetectorDefinition(
    detector_name="cSAXS Eiger 9m",
    detector_model=EIGER,
    geometry=[1, 1],
    bit_depth=16
)

udp_ip_and_port = [("127.0.0.1", 12000),
                   ("127.0.0.1", 12001),
                   ("127.0.0.1", 12002),
                   ("127.0.0.1", 12003)]

start_standard_setup(eiger1m, udp_ip_and_port)
