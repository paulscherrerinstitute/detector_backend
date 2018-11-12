import socket
import sys

from time import time

def test_module(ip, port):
    print(ip, port)

    receiver = socket.socket(socket.AF_INET,  socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, str(10000 * 1024 * 1024))
    receiver.bind((ip, port))

    n_bytes = 0

    # Wait until next frame.
    while n_bytes != 40:
        n_bytes = len(receiver.recv(10000))
        
    # Skip packets in between.    
    for x in range(61):
        n_bytes = len(receiver.recv(10000))

    start_time = time()

    for x in range(8):
        n_bytes = len(receiver.recv(10000))
        print(time(), n_bytes)

    print("Time between frames: %f seconds" % (time() - start_time))

import logging
_logger = logging.getLogger(__name__)

def process_detector_config_file(filename):
    
    with file(sys.argv[1]) as input_file:
        file_lines = input_file.readlines()

    per_module_config = {}
    detector_config = {}

    for config_line in file_lines:
        config_string = config_line.strip()

        if len(config_string) == 0:
            continue

        if config_string[0] == "#":
            _logger.info("Skipping comment line: %s", config_string)
            continue

        # All module specific configs are in format: "module_number:property_name property_value"
        if config_string[0].isdigit():
            index_module_number_end = config_string.index(":")
            module_number = int(config_string[0:index_module_number_end])
            
            index_variable_name_end = config_string.index(" ")
            property_name = config_string[index_module_number_end+1:index_variable_name_end]
            property_value = config_string[index_variable_name_end+1:]

            if module_number not in per_module_config:
                per_module_config[module_number] = {}

            per_module_config[module_number][property_name] = property_value
            _logger.debug("Adding module %d property %s=%s", module_number, property_name, property_value)

        # All non module specific configs are in format: "property_name property_value"
        else:
            index_variable_name_end = config_string.index(" ")
            property_name = config_string[index_variable_name_end+1:index_variable_name_end]
            property_value = config_string[index_variable_name_end+1:]

            detector_config[property_name] = property_value
            _logger.debug("Adding detector property %s=%s", property_name, property_value)

    return detector_config, per_module_config

detector_config, per_module_config = process_detector_config_file(sys.argv[1])

ignore_module_index = [30, 31]

for module_index in per_module_config.keys():
    if module_index in ignore_module_index:
        continue

    ip = per_module_config[module_index]["rx_udpip"]
    udp_port_1 = int(per_module_config[module_index]["rx_udpport"])
    udp_port_2 = int(per_module_config[module_index]["rx_udpport2"])
    
    print ("----- module index %d -----" % module_index)
    test_module(ip, udp_port_1)
    test_module(ip, udp_port_2)
