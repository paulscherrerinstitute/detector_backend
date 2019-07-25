#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include "../../src/eiger.c"

int setup_udp_socket(int udp_port, int snd_buffer)
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
    server.sin_addr.s_addr = inet_addr("127.0.0.1");
    server.sin_port = htons(udp_port);

    setsockopt(socket_fd, SOL_SOCKET, SO_SNDBUF, &snd_buffer, sizeof(int));

    if (connect(socket_fd, (const struct sockaddr *) &server, sizeof(server)))
    {
        printf("Cannot connect to socket.\n");
        exit(1);
    }

    return socket_fd;
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
    int udp_snd_buffer = 1000 * 1024 * 1024;
    int socket_fd = setup_udp_socket(udp_port, udp_snd_buffer);

    int bit_depth = atoi(argv[2]);
    uint32_t n_packets_per_frame = (bit_depth / 8) * (256 * 512) / EIGER_DATA_BYTES_PER_PACKET;
    
    unsigned int sleep_time = 1000;

    uint32_t n_frames = (uint32_t)atol(argv[3]);

    printf("Generating packets on udp_port=%d bit_depth=%d n_frames=%"PRIu32" sleep_time=%"PRIu32" us\n",
      udp_port, bit_depth, n_frames, sleep_time);

    eiger_packet packet;
    memset(&packet, 0, sizeof(packet));

    packet.metadata.exptime = 1;
    packet.metadata.bunchid = 2.0;
    packet.metadata.timestamp = 3;
    packet.metadata.moduleID = 4;
    packet.metadata.xCoord = 5;
    packet.metadata.yCoord = 6;
    packet.metadata.zCoord = 7;
    packet.metadata.debug = 8;
    packet.metadata.roundRobin = 9;
    packet.metadata.detectortype = 10;
    packet.metadata.headerVersion = 11;

    for(uint32_t frame_index=0; frame_index<n_frames; frame_index++)
    {
        packet.metadata.framenum = (uint64_t) frame_index;

        for(uint32_t packet_index=0; packet_index<n_packets_per_frame; packet_index++)
        {
            packet.metadata.packetnum = packet_index;
            memset(packet.data, packet_index, sizeof(packet.data));

            send(socket_fd, (char*) &packet, sizeof(packet), 0);
        }

        if (frame_index%100 == 0)
        {
            printf("Sent %d frames.", frame_index);
        }
        
        usleep(sleep_time);
    }

    exit(0);
}
