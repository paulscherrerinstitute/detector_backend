#include "detectors.h"

inline bool is_timeout_expired (double timeout, struct timeval timeout_start_time)
{
  struct timeval current_time;
  gettimeofday(&current_time, NULL);

  double timeout_i = (double)(current_time.tv_usec - timeout_start_time.tv_usec) / 1e6 
    + (double)(current_time.tv_sec - timeout_start_time.tv_sec);

  return timeout_i > timeout;
}

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

inline int get_packet_line_number(rb_metadata* rb_meta, uint32_t packet_number)
{
  // assuming packetnum sequence is 0..N-1
  return rb_meta->n_lines_per_packet * 
    (rb_meta->n_packets_per_frame - packet_number - 1);
}

inline bool is_acquisition_completed(uint32_t n_frames, counter* counters)
{
  uint64_t total_frames = counters->total_recv_frames + counters->total_lost_frames;
  return (n_frames != 0) && total_frames >= n_frames;
}

inline void initialize_counters_for_new_frame (
  counter* counters, uint64_t frame_number )
{
  counters->current_frame = frame_number;
  counters->current_frame_recv_packets = 0;
}
