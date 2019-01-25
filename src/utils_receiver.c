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

inline bool is_slot_ready_for_frame (uint64_t frame_number, counter *counters)
{
  return counters->current_frame == frame_number;
}

inline bool is_frame_complete (int n_packets_per_frame, counter* counters)
{   
  return counters->current_frame_recv_packets == n_packets_per_frame;
}

inline void print_statistics (counter* counters, struct timeval* last_stats_print_time)
{
  struct timeval current_time;
  gettimeofday(&current_time, NULL);

  double elapsed_seconds = (current_time.tv_sec - last_stats_print_time->tv_sec) + 
    ((long)(current_time.tv_usec) - (long)(last_stats_print_time->tv_usec)) / 1e6;

  double frame_rate = (double) PRINT_STATS_N_FRAMES_MODULO / elapsed_seconds;

  float percentage_lost_packets = 100. * (float)counters->total_lost_packets / 
    (float)(counters->total_recv_packets);

  // CPU | pid | framenum | frame_rate | tot_lost_packets | % lost packets |
  printf(
    "| %d | %d | %"PRIu64" | %.2f | %"PRIu64" | %.1f |\n", 
    sched_getcpu(), getpid(), counters->total_recv_frames, frame_rate, 
    counters->total_lost_packets, percentage_lost_packets
  );

  gettimeofday(last_stats_print_time, NULL);
}

int inline get_packet_line_number(rb_metadata* rb_meta, uint32_t packet_number)
{
  // assuming packetnum sequence is 0..N-1
  return rb_meta->n_lines_per_packet * 
    (rb_meta->n_packets_per_frame - packet_number - 1);
}

inline bool is_acquisition_completed(int16_t n_frames, counter* counters)
{
  uint64_t total_frames = counters->total_recv_frames + counters->total_lost_frames;
  return (n_frames != -1) && total_frames >= n_frames;
}

inline void initialize_counters_for_new_frame (
  counter* counters, uint64_t frame_number )
{
  counters->current_frame = frame_number;
  counters->current_frame_recv_packets = 0;
}
