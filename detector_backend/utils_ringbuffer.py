import ctypes
import logging
import subprocess

import numpy as np

from detector_backend import config

_logger = logging.getLogger("utils_ringbuffer")


def create_rb_files(n_slots,
                    n_header_slot_bytes,
                    n_raw_data_slot_bytes,
                    n_assembled_data_slot_bytes,
                    image_head_file=config.DEFAULT_RB_IMAGE_HEAD_FILE,
                    raw_image_data_file=config.DEFAULT_RB_RAW_IMAGE_DATA_FILE,
                    assembled_image_data_file=config.DEFAULT_RB_ASSEMBLED_IMAGE_DATA_FILE):

    def create_file(output_file, block_size, n_blocks):
        _logger.debug("Creating file %s with block_size %d and n_blocks %n",
                      output_file, block_size, n_blocks)

        cmd = ["dd", "if=/dev/zero", "of=%s" % output_file, "bs=%d" % block_size, "count=%d" % n_blocks]

        process = subprocess.Popen(cmd)
        state = process.wait()

        if state != 0:
            raise RuntimeError("Could not create file %s with block_size %d and n_blocks %d" %
                               (output_file, block_size, n_blocks))

    create_file(image_head_file, n_header_slot_bytes, n_slots)
    create_file(raw_image_data_file, n_raw_data_slot_bytes, n_slots)
    create_file(assembled_image_data_file, n_assembled_data_slot_bytes, n_slots)

    _logger.info("Ringbuffer files %s, %s and %s created.",
                 image_head_file, raw_image_data_file, assembled_image_data_file)


class CRingBufferImageHeaderData(ctypes.Structure):
    _fields_ = [("framemetadata", ctypes.c_uint64 * 8), ]


def get_frame_metadata(metadata_pointer, n_submodules):
    rb_image_header_pointer = CRingBufferImageHeaderData * n_submodules

    metadata_struct = ctypes.cast(metadata_pointer, ctypes.POINTER(rb_image_header_pointer))

    metadata = {
        "framenums": [x.framemetadata[0] for x in metadata_struct.contents],
        "missing_packets_1": [x.framemetadata[2] for x in metadata_struct.contents],
        "missing_packets_2": [x.framemetadata[3] for x in metadata_struct.contents],
        "pulse_ids": [x.framemetadata[4] for x in metadata_struct.contents],
        "daq_recs": [x.framemetadata[5] for x in metadata_struct.contents],
        "module_number": [x.framemetadata[6] for x in metadata_struct.contents],
        "module_enabled": [x.framemetadata[7] for x in metadata_struct.contents],
    }

    metadata["frame"] = metadata["framenums"][0]
    metadata["daq_rec"] = metadata["daq_recs"][0]
    metadata["pulse_id"] = metadata["pulse_ids"][0]

    missing_packets = sum([metadata_struct.contents[i].framemetadata[1] for i in range(n_submodules)])

    metadata["is_good_frame"] = int(len(set(metadata["framenums"])) == 1 and missing_packets == 0)
    metadata["pulse_id_diff"] = [metadata["pulse_id"] - i for i in metadata["pulse_ids"]]
    metadata["framenum_diff"] = [metadata["frame"] - i for i in metadata["framenums"]]

    return metadata


def get_frame_data(data_pointer, frame_size):
    data = np.ctypeslib.as_array(data_pointer, shape=frame_size)
    return data
