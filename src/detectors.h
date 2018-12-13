#ifndef DETECTORS_H
#define DETECTORS_H

// header struct for RB - to be updated to include the framenums of all modules
#include <inttypes.h>

typedef struct Counter{
  /*
  int total_packets;
  uint64_t framenum_last;
  int total_frames;
  */
  int recv_packets;
  uint64_t current_frame;
  int recv_frames;
  int lost_frames;
} counter;

typedef struct _detector{
    char detector_name[10];
    uint8_t submodule_n;
    int32_t detector_size[2]; 
    int32_t module_size[2]; 
    int32_t submodule_size[2]; 
    int32_t module_idx[2]; 
    int32_t submodule_idx[2];
    uint16_t gap_px_chips[2];
    uint16_t gap_px_modules[2];
} detector;

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
typedef struct _barebone_packet{
  char* data;
  int data_len;
  uint32_t packetnum;
  uint64_t framenum;
  double bunchid;
  uint32_t debug;
} barebone_packet;

// Signature: detector det, int line_number, int n_lines_per_packet, void * p1, void * data, int bit_depth
typedef barebone_packet (*interpret_udp_packet_function)(const char*, const int);

// Signature: const char* udp_packet, const int received_packet_len
typedef barebone_packet (*copy_data_function)(detector, int, int, void*, void*, int);

typedef struct _detector_definition{
  interpret_udp_packet_function interpret_udp_packet;
  copy_data_function copy_data;
  size_t udp_packet_bytes;
  size_t data_bytes_per_packet;
} detector_definition;

#endif
