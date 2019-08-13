import logging
import subprocess

from detector_backend import config

_logger = logging.getLogger("utils_ringbuffer")


def create_rb_files(n_slots,
                    n_header_slot_bytes,
                    n_data_slot_bytes,
                    image_head_file=config.DEFAULT_RB_IMAGE_HEAD_FILE,
                    image_data_file=config.DEFAULT_RB_IMAGE_DATA_FILE):

    def create_file(output_file, block_size, n_blocks):
        _logger.debug("Creating file %s with block_size %d and n_blocks %n",
                      output_file, block_size, n_blocks)

        # TODO: Check if file of correct size already exists.s

        cmd = ["dd", "if=/dev/zero", "of=%s" % output_file, "bs=%d" % block_size, "count=%d" % n_blocks]

        process = subprocess.Popen(cmd)
        state = process.wait()

        if state != 0:
            raise RuntimeError("Could not create file %s with block_size %d and n_blocks %d" %
                               (output_file, block_size, n_blocks))

    create_file(image_head_file, n_header_slot_bytes, n_slots)
    create_file(image_data_file, n_data_slot_bytes, n_slots)

    _logger.info("Ringbuffer files %s and %s created.", image_head_file, image_data_file)
