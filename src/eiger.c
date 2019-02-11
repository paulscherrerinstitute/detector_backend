#include <string.h>
#include "detectors.h"

#define EIGER_BYTES_PER_PACKET 4144
#define EIGER_DATA_BYTES_PER_PACKET 4096
#define EIGER_MIN_VALID_PACKET_SIZE 41

// 48 bytes + 4096 bytes = 4144 bytes.
typedef struct _eiger_packet {
  detector_common_packet metadata;
  char data[EIGER_DATA_BYTES_PER_PACKET];
} eiger_packet;

barebone_packet interpret_udp_packet (
  const char* udp_packet, const int received_packet_len ) 
{
  eiger_packet* packet = (eiger_packet*) udp_packet;

  barebone_packet bpacket;
  bpacket.data = packet->data;
  bpacket.data_len = received_packet_len;
  bpacket.framenum = packet->metadata.framenum;
  bpacket.packetnum = packet->metadata.packetnum;
  bpacket.is_valid = received_packet_len >= EIGER_MIN_VALID_PACKET_SIZE;

  return bpacket;
}

void copy_data (
  detector* det, rb_metadata* rb_meta, void* ringbuffer_slot_origin, void* packet_data, int line_number)
{  
  int reverse;
  int reverse_factor;

  // Top submodule row.
  if (det->submodule_idx[0] == 0) {
      reverse = 1;
      reverse_factor = 0;
  // Bottom submodule row.
  } else {
      reverse = -1;
      reverse_factor = det->submodule_size[0] - 1;
  }

  // Each packet line is made of 2 chip lines -> [CHIP1]<gap>[CHIP2]
  uint32_t n_bytes_per_chip_line = rb_meta->n_bytes_per_submodule_line / 2;
  uint32_t n_bytes_per_chip_gap = (det->gap_px_chips[1] * rb_meta->bit_depth) / 8;

  uint32_t dest_chip_offset = n_bytes_per_chip_line + n_bytes_per_chip_gap;

  // Packets are stream from the top to the bottom of the module.
  // module_line goes from 255..0
  uint32_t dest_submodule_line = line_number + n_lines_per_packet - 1;
  uint32_t dest_line_offset = (reverse_factor + (reverse * dest_submodule_line)) * rb_meta->n_bytes_per_frame_line;

  uint32_t source_offset = 0;

  for (uint32_t packet_line=0; packet_line<n_lines_per_packet; packet_line++)
  {
    // Copy each chip line individually, to allow a gap of n_bytes_per_chip_gap in the destination memory.
    memcpy (
      (char*)ringbuffer_slot_origin + dest_line_offset, 
      (char*)packet_data + source_offset, 
      n_bytes_per_chip_line
    );

    memcpy (
      (char*)ringbuffer_slot_origin + dest_line_offset + dest_chip_offset,
      (char*)packet_data + source_offset + n_bytes_per_chip_line, 
      n_bytes_per_chip_line
    );

    source_offset += rb_meta->n_bytes_per_submodule_line;
    dest_line_offset -= reverse * rb_meta->n_bytes_per_frame_line;
  }
}

detector_definition det_definition = {
  .udp_packet_bytes = sizeof(eiger_packet),
  .data_bytes_per_packet = EIGER_DATA_BYTES_PER_PACKET
};
