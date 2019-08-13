#ifndef DETECTORS_H
#define DETECTORS_H

#include <inttypes.h>
#include <stdbool.h>

#define PRINT_STATS_N_FRAMES_MODULO 100
#define NO_CURRENT_FRAME 0

typedef struct Counter{
  uint64_t current_frame;
  uint64_t current_frame_recv_packets;

  uint64_t total_recv_packets;
  uint64_t total_lost_packets;

  uint64_t total_recv_frames;
  uint64_t total_lost_frames;
} counter;

typedef struct _detector{
    uint8_t submodule_n;
    int32_t detector_size[2]; 
    int32_t module_size[2]; 
    int32_t submodule_size[2]; 
    int32_t module_idx[2]; 
    int32_t submodule_idx[2];
    uint16_t gap_px_chips[2];
    uint16_t gap_px_modules[2];
    uint32_t bytes_per_packet;
    uint32_t bytes_data_per_packet;
} detector;

typedef struct _detector_submodule{
    uint16_t submodule_index;
    uint16_t n_packets_per_frame;

    uint32_t bytes_per_packet;
    uint32_t bytes_data_per_packet;

    uint64_t submodule_data_slot_offset;

} detector_submodule;

typedef struct _rb_header{
  // Field 0: frame number
  // Field 1: packets lost
  // Field 2: packets counter 0-63
  // Field 3: packets counter 64-127
  // Field 4: pulse id
  // Field 5: debug (daq_rec) - gain flag
  // Field 6: module number
  // Field 7: module enabled

  uint64_t framemetadata[8];
} rb_header;

// 48 bytes.
typedef struct _detector_common_packet{
  uint64_t framenum;
  uint32_t exptime;
  uint32_t packetnum;

  double bunchid;
  uint64_t timestamp;

  uint16_t moduleID;
  uint16_t xCoord;
  uint16_t yCoord;
  uint16_t zCoord;

  uint32_t debug;
  uint16_t roundRobin;
  uint8_t detectortype;
  uint8_t headerVersion;
} detector_common_packet;

// the essential info needed for a packet
typedef struct _barebone_packet {
  char* data;
  int data_len;
  uint32_t packetnum;
  uint64_t framenum;
  double bunchid;
  uint32_t debug;
  bool is_valid;
} barebone_packet;

typedef struct _rb_metadata {
  int rb_writer_id;
  int rb_header_id;

  int rb_hbuffer_id;
  int rb_dbuffer_id;
} rb_metadata;

typedef struct _rb_state {
  int rb_current_slot;
  char* data_slot_origin;
  rb_header* header_slot_origin;
} rb_state;

// Signature: detector det, int line_number, int n_lines_per_packet, void * p1, void * data, int bit_depth
typedef barebone_packet (*interpret_udp_packet_function)(const char*, const int);

// Signature: detector* det, rb_metadata* rb_meta, void* packet_data, int line_number
typedef void (*copy_data_function)(detector, rb_metadata, void*, int);

#endif
