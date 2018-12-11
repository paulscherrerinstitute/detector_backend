#include <string.h>
#include "detectors.h"

#define EIGER_BYTES_PER_PACKET 4144
#define EIGER_DATA_BYTES_PER_PACKET 4096

// 48 bytes + 4096 bytes = 4144 bytes.
typedef struct _eiger_packet {
  detector_common_packet metadata;
  char data[EIGER_DATA_BYTES_PER_PACKET];
} eiger_packet;

barebone_packet interpret_udp_packet_eiger (
  const char* udp_packet, 
  const int received_packet_len ) 
{
  eiger_packet* packet = (eiger_packet*) udp_packet;

  barebone_packet bpacket;
  bpacket.data_len = received_packet_len;
  bpacket.framenum = packet->metadata.framenum;
  bpacket.packetnum = packet->metadata.packetnum;

  return bpacket;
}

void copy_data_eiger (
  detector det, 
  int line_number, 
  int n_lines_per_packet, 
  void * p1, 
  void * data, 
  int bit_depth )
{  
  int reverse;
  int reverse_factor;

  // Top submodule row.
  if (det.submodule_idx[0] == 0) {
      reverse = 1;
      reverse_factor = 0;
  // Bottom submodule row.
  } else {
      reverse = -1;
      reverse_factor = det.submodule_size[0] - 1;
  }

  int submodule_line_data_len = (8 * det.submodule_size[1]) / bit_depth;

  int int_line = 0;
  for(int i=line_number + n_lines_per_packet - 1; i >= line_number; i--){

    long destination_offset = (8 * (reverse_factor + reverse * i) * det.detector_size[1]) / bit_depth;
    long source_offset = (8 * int_line * det.submodule_size[1]) / bit_depth;

    memcpy((char*) p1 + destination_offset, (char*) data + source_offset, submodule_line_data_len/2);

    long destination_gap_offset = 8 * (det.gap_px_chips[1] + det.submodule_size[1] / 2) / bit_depth;
    long source_gap_offset = 8 * (det.submodule_size[1] / 2) / bit_depth;

    memcpy((char*)p1 + destination_offset + destination_gap_offset,
      (char *)data + source_offset + source_gap_offset, submodule_line_data_len/2);

    int_line ++;
  }
}

detector_definition eiger_definition = {
  .interpret_udp_packet = (interpret_udp_packet_function*) interpret_udp_packet_eiger,
  .copy_data = (copy_data_function*) copy_data_eiger,
  .udp_packet_bytes = sizeof(eiger_packet),
  .data_bytes_per_packet = EIGER_DATA_BYTES_PER_PACKET
};

