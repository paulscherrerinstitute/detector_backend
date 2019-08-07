DEFAULT_RB_FOLDER = "/dev/shm/rb/"
DEFAULT_RB_HEAD_FILE = "rb_header.dat"
DEFAULT_RB_IMAGE_HEAD_FILE = "rb_image_header.dat"
DEFAULT_RB_IMAGE_DATA_FILE = "rb_image_data.dat"

# 64 bytes per submodule = 8 * uint64_t values == 8 * (64bit/8bit)
IMAGE_HEADER_SUBMODULE_SIZE_BYTES = 64

# Delay between chacks to know if MPI has a next message.
MPI_COMM_DELAY = 0.10
