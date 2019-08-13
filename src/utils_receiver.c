#include "detectors.h"

inline int get_udp_packet (int socket_fd, char* buffer, size_t buffer_len) 
{
  return recv(socket_fd, buffer, buffer_len, 0);
}

inline bool is_rb_slot_ready_for_packet (uint64_t frame_number, counter *counters)
{
  return counters->current_frame == frame_number;
}

inline bool is_frame_complete (int n_packets_per_frame, counter* counters)
{   
  return counters->current_frame_recv_packets == n_packets_per_frame;
}

inline void initialize_counters_for_new_frame (
  counter* counters, uint64_t frame_number )
{
  counters->current_frame = frame_number;
  counters->current_frame_recv_packets = 0;
}

inline bool is_timeout_expired (double timeout, struct timeval timeout_start_time)
{
  struct timeval current_time;
  gettimeofday(&current_time, NULL);

  double timeout_i = (double)(current_time.tv_usec - timeout_start_time.tv_usec) / 1e6
    + (double)(current_time.tv_sec - timeout_start_time.tv_sec);

  return timeout_i > timeout;
}