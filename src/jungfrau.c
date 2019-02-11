#include <string.h>
#include "detectors.h"

#define JUNGFRAU_BYTES_PER_PACKET 8246
#define JUNGFRAU_DATA_BYTES_PER_PACKET 8192

// 6 bytes + 48 bytes + 8192 bytes = 8246 bytes
#pragma pack(push)
#pragma pack(2)
typedef struct _jungfrau_packet{
  char emptyheader[6];
  detector_common_packet metadata;
  char data[JUNGFRAU_DATA_BYTES_PER_PACKET];
} jungfrau_packet;
#pragma pack(pop)

barebone_packet interpret_udp_packet (
  const char* udp_packet, const int received_packet_len )
{
  jungfrau_packet* packet = (jungfrau_packet*) udp_packet;

  barebone_packet bpacket;
  bpacket.data = packet->data;
  bpacket.data_len = received_packet_len;
  bpacket.framenum = packet->metadata.framenum;
  bpacket.packetnum = packet->metadata.packetnum;
  bpacket.bunchid = packet->metadata.bunchid;
  bpacket.debug = packet->metadata.debug;
  bpacket.is_valid = received_packet_len > 0;

  return bpacket;
}

void copy_data (
  detector* det, rb_metadata* rb_meta, void* packet_data, int line_number)
{
  // -1 to convert from 1 based submodule height to 0 based array indexing.
  uint32_t submodule_height = det->submodule_size[0] - 1;

  // Packets are stream from the top to the bottom of the module.
  // module_line goes from 255..0
  uint32_t dest_submodule_line = line_number + rb_meta->n_lines_per_packet - 1;

  for (uint32_t packet_line=0; packet_line<rb_meta->n_lines_per_packet; packet_line++)
  {
    long dest_offset = (submodule_height - dest_submodule_line) * rb_meta->n_bytes_per_frame_line;
    long source_offset = packet_line * rb_meta->n_bytes_per_submodule_line;
    
    memcpy(
      (char*)(rb_meta->data_slot_origin) + dest_offset, 
      (char*)data + source_offset, 
      rb_meta->n_bytes_per_submodule_line
    );
                
    dest_submodule_line--;
  }
}

detector_definition det_definition = {
  .udp_packet_bytes = sizeof(jungfrau_packet),
  .data_bytes_per_packet = JUNGFRAU_DATA_BYTES_PER_PACKET
};
