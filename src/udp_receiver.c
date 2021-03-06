#define _GNU_SOURCE
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <inttypes.h>
#include <sys/time.h>
#include <ring_buffer.h>
#include <arpa/inet.h>
#include <sched.h>

#include "detectors.h"
#include "utils_ringbuffer.c"
#include "utils_receiver.c"


#ifdef JUNGFRAU 
  #include "jungfrau.c"
#endif

#ifdef EIGER
  #include "eiger.c"
#endif


bool receive_packet (int sock, char* udp_packet, size_t udp_packet_bytes, 
  barebone_packet* bpacket)
{
  const int received_data_len = get_udp_packet(sock, udp_packet, udp_packet_bytes);

  *bpacket = interpret_udp_packet(udp_packet, received_data_len);

  #ifdef DEBUG
    if(received_data_len > 0){
      printf("[receive_packet][%d] nbytes %d framenum: %"PRIu64" packetnum: %"PRIu32"\n",
        getpid(), bpacket->data_len, bpacket->framenum, bpacket->packetnum);
    }
  #endif

  return bpacket->is_valid;
}

void save_packet (
  barebone_packet* bpacket, rb_metadata* rb_meta, counter* counters,
  uint32_t bytes_data_per_packet, rb_header* header, rb_state* rb_current_state)
{
  counters->current_frame_recv_packets++;
  counters->total_recv_packets++;

  long packet_offset = bpacket->packetnum * bytes_data_per_packet;

  memcpy(
      (char*) rb_current_state->data_slot_origin + packet_offset,
      (char*) bpacket->data,
      bytes_data_per_packet
  );

  update_rb_header(header, bpacket);
}

void put_data_in_rb (int sock, rb_metadata rb_meta, detector_submodule det_submodule, float mpi_timeout)
{

  struct timeval udp_socket_timeout;
  udp_socket_timeout.tv_sec = 0;
  udp_socket_timeout.tv_usec = 100;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, (const char*)&udp_socket_timeout, sizeof(struct timeval));

  struct timeval timeout_start_time;
  gettimeofday(&timeout_start_time, NULL);

  char udp_packet[det_submodule.bytes_per_packet];
  barebone_packet bpacket;
  rb_header header;
  rb_state rb_current_state = {-1, NULL, NULL};
  counter counters = {NO_CURRENT_FRAME, 0, 0, 0, 0, 0};

  while (true)
  {
    bool is_packet_received = receive_packet (
      sock, (char*)&udp_packet, det_submodule.bytes_per_packet, &bpacket
    );

    if (!is_packet_received)
    {
      if (is_timeout_expired(mpi_timeout, timeout_start_time))
      {
        commit_if_slot_dangling(&counters, &rb_meta, &header, &rb_current_state, det_submodule.n_packets_per_frame);
        return;
      }
      continue;
    }

    if (!is_rb_slot_ready_for_packet(bpacket.framenum, &counters))
    {
      // If we lost packets at the end of the frame, it was not committed.
      commit_if_slot_dangling(&counters, &rb_meta, &header, &rb_current_state, det_submodule.n_packets_per_frame);

      if(!claim_next_slot(&rb_meta, &rb_current_state))
      {
        printf("[put_data_in_rb][%"PRIu16"] Cannot get next slot, RB full. Exit.", det_submodule.submodule_index);
        exit(-1);
      }

      // Adjust ringbuffer pointers offset for this submodule.
      rb_current_state.header_slot_origin += det_submodule.submodule_index;
      rb_current_state.data_slot_origin += det_submodule.submodule_data_slot_offset;

      initialize_rb_header(&header, det_submodule.n_packets_per_frame, det_submodule.submodule_index, &bpacket);
      initialize_counters_for_new_frame(&counters, bpacket.framenum);
    }

    save_packet(&bpacket, &rb_meta, &counters, det_submodule.bytes_data_per_packet, &header, &rb_current_state);

    if(is_frame_complete(det_submodule.n_packets_per_frame, &counters))
    {
      #ifdef DEBUG
        printf("[put_data_in_rb][%"PRIu16"] Frame complete,"
               " got packet %"PRIu32" %"PRIu64" of %"PRIu16" frame %"PRIu64" / %"PRIu64"\n",
          det_submodule.submodule_index, bpacket.packetnum, counters.current_frame_recv_packets,
          det_submodule.n_packets_per_frame, bpacket.framenum, counters.current_frame);
      #endif

      copy_rb_header(&header, &rb_current_state, &counters, det_submodule.n_packets_per_frame);

      commit_slot(rb_meta.rb_writer_id, rb_current_state.rb_current_slot);

      counters.current_frame = NO_CURRENT_FRAME;
      counters.total_recv_frames++;
    }

    gettimeofday(&timeout_start_time, NULL);
  }
}
