# Ring buffer files and folders.
DEFAULT_RB_FOLDER = ""
RB_HEAD_FILE = "rb_header.dat"
RB_IMAGE_HEAD_FILE = "rb_image_header.dat"
RB_RAW_IMAGE_DATA_FILE = "rb_raw_image_data.dat"
RB_ASSEMBLED_IMAGE_DATA_FILE = "rb_assembled_image_data.dat"

# 64 bytes per submodule = 8 * uint64_t values == 8 * (64bit/8bit)
IMAGE_HEADER_SUBMODULE_SIZE_BYTES = 64

# Delay between chacks to know if MPI has a next message.
MPI_COMM_DELAY = 0.10
RB_RETRY_DELAY = 0.01
