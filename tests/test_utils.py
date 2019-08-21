import os
import unittest

from detector_backend import config
from detector_backend.utils_ringbuffer import create_rb_files
from tests.utils import cleanup_rb_files


class UtilsTests(unittest.TestCase):

    def setUp(self):
        cleanup_rb_files()

    def tearDown(self):
        cleanup_rb_files()

    def test_create_rb_files(self):
        self.assertFalse(os.path.isfile(config.DEFAULT_RB_IMAGE_HEAD_FILE))
        self.assertFalse(os.path.isfile(config.DEFAULT_RB_RAW_IMAGE_DATA_FILE))
        self.assertFalse(os.path.isfile(config.DEFAULT_RB_ASSEMBLED_IMAGE_DATA_FILE))

        n_slots = 10
        n_head_slot_bytes = 64
        n_raw_data_slot_bytes = 4096
        n_assembled_data_slot_bytes = 5000

        create_rb_files(n_slots, n_head_slot_bytes, n_raw_data_slot_bytes, n_assembled_data_slot_bytes)

        self.assertTrue(os.path.isfile(config.DEFAULT_RB_IMAGE_HEAD_FILE))
        self.assertTrue(os.path.isfile(config.DEFAULT_RB_RAW_IMAGE_DATA_FILE))
        self.assertTrue(os.path.isfile(config.DEFAULT_RB_ASSEMBLED_IMAGE_DATA_FILE))

        head_file_size = os.path.getsize(config.DEFAULT_RB_IMAGE_HEAD_FILE)
        self.assertEqual(head_file_size, n_slots*n_head_slot_bytes)

        raw_data_file_size = os.path.getsize(config.DEFAULT_RB_RAW_IMAGE_DATA_FILE)
        self.assertEqual(raw_data_file_size, n_slots*n_raw_data_slot_bytes)

        assembled_data_file_size = os.path.getsize(config.DEFAULT_RB_ASSEMBLED_IMAGE_DATA_FILE)
        self.assertEqual(assembled_data_file_size, n_slots * n_assembled_data_slot_bytes)

    def test_exception(self):
        n_slots = -1
        n_head_slot_bytes = 64
        n_raw_data_slot_bytes = 4096
        n_assembled_data_slot_bytes = 4096

        with self.assertRaisesRegex(RuntimeError, "Could not create file"):
            create_rb_files(n_slots, n_head_slot_bytes, n_raw_data_slot_bytes, n_assembled_data_slot_bytes)

    def test_overwrite(self):
        n_slots = 10
        n_head_slot_bytes = 64
        n_raw_data_slot_bytes = 4096
        n_assembled_data_slot_bytes = 5000

        create_rb_files(n_slots, n_head_slot_bytes, n_raw_data_slot_bytes, n_assembled_data_slot_bytes)

        self.assertEqual(os.path.getsize(config.DEFAULT_RB_IMAGE_HEAD_FILE), n_slots * n_head_slot_bytes)
        self.assertEqual(os.path.getsize(config.DEFAULT_RB_RAW_IMAGE_DATA_FILE), n_slots * n_raw_data_slot_bytes)
        self.assertEqual(os.path.getsize(config.DEFAULT_RB_ASSEMBLED_IMAGE_DATA_FILE),
                         n_slots * n_assembled_data_slot_bytes)

        n_slots = 5
        create_rb_files(n_slots, n_head_slot_bytes, n_raw_data_slot_bytes, n_assembled_data_slot_bytes)

        self.assertEqual(os.path.getsize(config.DEFAULT_RB_IMAGE_HEAD_FILE), n_slots * n_head_slot_bytes)
        self.assertEqual(os.path.getsize(config.DEFAULT_RB_RAW_IMAGE_DATA_FILE), n_slots * n_raw_data_slot_bytes)
        self.assertEqual(os.path.getsize(config.DEFAULT_RB_ASSEMBLED_IMAGE_DATA_FILE),
                         n_slots * n_assembled_data_slot_bytes)
