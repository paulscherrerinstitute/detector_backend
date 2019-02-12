#include "../../src/udp_receiver.c"

// N_modules * n_submodules * sizeof_submodule_header;
const int FRAME_HEADER_BYTES = 18 * 4 * 64;
// bytes/pixel * size_x * size_y;
const int FRAME_DATA_BYTES = 2 * 3264 * 3106;

char const RB_HEADER_FILENAME[] = "/dev/shm/rb/rb_header.dat";
char const RB_HBUFFER_FILENAME[] = "/dev/shm/rb/rb_image_header.dat";
char const RB_DBUFFER_FILENAME[] = "/dev/shm/rb/rb_image_data.dat";


// udp_receiver.c
extern inline bool receive_packet (int sock, char* udp_packet, size_t udp_packet_bytes, 
  barebone_packet* bpacket, detector_definition* det_definition );
extern inline void save_packet (
  barebone_packet* bpacket, rb_metadata* rb_meta, counter* counters, detector* det, rb_header* header);
extern int put_data_in_rb(
  int sock, int bit_depth, int rb_current_slot, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_writer_id, 
  uint32_t n_frames, float timeout, detector det);

// utils_metadata.c
extern inline uint32_t get_current_module_offset_in_pixels (detector det);
extern int get_current_module_index (detector det);
extern int get_n_lines_per_packet (detector det, size_t data_bytes_per_packet, int bit_depth);
extern inline int get_n_packets_per_frame (detector det, size_t data_bytes_per_packet, int bit_depth);
extern inline rb_metadata get_ringbuffer_metadata (
  int rb_writer_id, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_current_slot,  
    detector det, size_t data_bytes_per_packet, int bit_depth );
extern inline uint32_t get_n_bytes_per_frame_line(detector det, int bit_depth);
extern uint32_t get_n_bytes_per_submodule_line(detector det, int bit_depth);

// utils_receiver.c
extern inline bool is_timeout_expired (double timeout, struct timeval timeout_start_time);
extern inline int get_udp_packet (int socket_fd, char* buffer, size_t buffer_len);
extern inline bool is_slot_ready_for_frame (uint64_t frame_number, counter *counters);
extern inline bool is_frame_complete (int n_packets_per_frame, counter* counters);
extern inline void print_statistics (counter* counters, struct timeval* last_stats_print_time);
extern inline int get_packet_line_number(rb_metadata* rb_meta, uint32_t packet_number);
extern inline bool is_acquisition_completed(uint32_t n_frames, counter* counters);
extern inline void initialize_counters_for_new_frame (counter* counters, uint64_t frame_number);

// utils_ringbuffer.c
extern inline bool commit_slot (int rb_writer_id, int rb_current_slot);
extern inline void commit_if_slot_dangling (counter* counters, rb_metadata* rb_meta, rb_header* header);
extern inline void claim_next_slot(rb_metadata* rb_meta);
extern inline void initialize_rb_header (rb_header* header, rb_metadata* rb_meta, barebone_packet* bpacket);
extern inline void update_rb_header (rb_header* header, barebone_packet* bpacket);
extern inline uint64_t copy_rb_header(rb_header* header, rb_metadata* rb_meta, counter *counters);

int setup_udp_socket(int udp_port, int rcv_buffer)
{
    int socket_fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (socket_fd < 0)
    {
        printf("Cannot open socket. Return value: %d\n", socket_fd);
        exit(1);
    }

    struct sockaddr_in server;
    memset(&server, 0, sizeof(server));
    server.sin_family = AF_INET;
    server.sin_addr.s_addr = INADDR_ANY;
    server.sin_port = htons(udp_port);

    setsockopt(socket_fd, SOL_SOCKET, SO_RCVBUF, &rcv_buffer, sizeof(int));

    if (bind(socket_fd, &server, sizeof(server)))
    {
        printf("Cannot bind to socket.\n");
        exit(1);
    }

    return socket_fd;
}

int setup_rb(int* rb_header_id, int* rb_writer_id, int* rb_hbuffer_id, int* rb_dbuffer_id)
{
    rb_reset();

    *rb_header_id = rb_open_header_file(RB_HEADER_FILENAME);
    *rb_writer_id = rb_create_writer(*rb_header_id, 0, 0, NULL);

    *rb_hbuffer_id = rb_attach_buffer_to_header(RB_HBUFFER_FILENAME, *rb_header_id, 0);
    rb_set_buffer_stride_in_byte(*rb_hbuffer_id, FRAME_HEADER_BYTES);

    *rb_dbuffer_id = rb_attach_buffer_to_header(RB_DBUFFER_FILENAME, *rb_header_id, 0);
    rb_set_buffer_stride_in_byte(*rb_dbuffer_id, FRAME_DATA_BYTES);

    return rb_adjust_nslots(*rb_header_id);
}

detector get_eiger9M_definition()
{
    detector det;
    strcpy(det.detector_name, "EIGER");
    det.submodule_n = 4;

    det.detector_size[0] = 3264;
    det.detector_size[1] = 3106;

    det.module_size[0] = 512;
    det.module_size[1] = 1024;

    det.submodule_size[0] = 256;
    det.submodule_size[1] = 512;

    // Module in origin.
    det.module_idx[0] = 0;
    det.module_idx[1] = 0;

    // Submodule in origin.
    det.submodule_idx[0] = 0;
    det.submodule_idx[1] = 0;

    det.gap_px_chips[0] = 2;
    det.gap_px_chips[1] = 2;

    det.gap_px_modules[0] = 36;
    det.gap_px_modules[1] = 8;

    return det;
}

int main(int argc, char *argv[])
{
    if (argc-1!=3)
    {
        printf("Invalid number of parameters. Provided %d, but expected:\n", argc-1);
        printf("\t[udp_port] - Port to bind for receiving the UDP stream.\n");
        printf("\t[bit_depth] - Bit depth of data stream.\n");
        printf("\t[n_frames] - Number of frames to acquire (uint32_t).\n");
        exit(1);
    }

    int udp_port = atoi(argv[1]);
    int udp_rcv_buffer = 1000 * 1024 * 1024;
    int socket_fd = setup_udp_socket(udp_port, udp_rcv_buffer);

    int bit_depth = atoi(argv[2]);

    int rb_current_slot = -1;
    int rb_header_id, rb_writer_id, rb_hbuffer_id, rb_dbuffer_id;
    setup_rb(&rb_header_id, &rb_writer_id, &rb_hbuffer_id, &rb_dbuffer_id);

    uint32_t n_frames = (uint32_t)atol(argv[3]);
    float timeout = 100000;

    detector det = get_eiger9M_definition();

    printf("Starting acquisition with udp_port=%d bit_depth=%d n_frames=%"PRIu32" timeout=%.2f\n",
      udp_port, bit_depth, n_frames, timeout);

    put_data_in_rb (
        socket_fd, bit_depth, 
        rb_current_slot, rb_header_id, rb_hbuffer_id, rb_dbuffer_id, rb_writer_id,
        n_frames, timeout, det );
    exit(0);
}
