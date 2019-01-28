#include "../../src/udp_receiver.c"

// N_modules * n_submodules * sizeof_submodule_header;
const int FRAME_HEADER_BYTES = 18 * 4 * 64;
// bytes/pixel * size_x * size_y;
const int FRAME_DATA_BYTES = 2 * 3264 * 3106;

char const RB_HEADER_FILENAME[] = "/dev/shm/rb/rb_header.dat";
char const RB_HBUFFER_FILENAME[] = "/dev/shm/rb/rb_image_header.dat";
char const RB_DBUFFER_FILENAME[] = "/dev/shm/rb/rb_image_data.dat";

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

    if (bind(socket_fd, (struct socketaddr*)&server, size_of(server)))
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
    rb_set_buffer_stride_in_byte(*rb_dbuffer_id, FRAME_DATA_BYTES)

    return rb_adjust_nslots(*rb_header_id);
}

detector get_eiger9M_definition()
{
    detector det;
    strlcpy(det.detector_name, "EIGER", 5);
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
    if (argc<3)
    {
        printf("Invalid number of parameters. Provided %d, but expected:\n", argc);
        printf("\t[udp_port] - Port to bind for receiving the UDP stream.\n");
        printf("\t[bit_depth] - Bit depth of data stream.\n");
        exit(1);
    }

    int udp_port = atoi(argv[1]);
    int udp_rcv_buffer = 10000 * 1024 * 1024
    int socket_fd = setup_udp_socket(udp_port, udp_rcv_buffer);

    int bit_depth = atoi(argv[2]);

    int rb_current_slot = -1;
    int rb_header_id, rb_writer_id, rb_hbuffer_id, rb_dbuffer_id;
    int n_slots = setup_rb(&rb_header_id, &rb_writer_id, &rb_hbuffer_id, &rb_dbuffer_id);

    int n_frames = 2;
    int timeout = 100000;

    detector det = get_eiger9M_definition();

    put_data_in_rb (
        socket_fd, bit_depth, 
        rb_current_slot, rb_header_id, rb_hbuffer_id, rb_dbuffer_id, rb_writer_id,
        n_frames, timeout, det );
    
}