#include "detectors.h"

// 6 bytes + 48 bytes + 8192 bytes = 8246 bytes
#pragma pack(push)
#pragma pack(2)
typedef struct _jungfrau_packet{
  char emptyheader[6];
  detector_common_packet metadata;
  char data[8192];
} jungfrau_packet;
#pragma pack(pop)

barebone_packet interpret_udp_packet_jungfrau(const char* udp_packet, const int received_packet_len) {
  const jungfrau_packet* packet = (const jungfrau_packet*) udp_packet;

  barebone_packet bpacket;
  bpacket.data_len = received_data_len;
  bpacket.framenum = packet.metadata.framenum;
  bpacket.packetnum = packet.metadata.packetnum;
  bpacket.bunchid = packet.metadata.bunchid;
  bpacket.debug = packet.metadata.debug;

  return bpacket;
}

void copy_data_jungfrau(detector det, int line_number, int n_lines_per_packet, void * p1, void * data, int bit_depth){
  
  int reverse = -1;
  int reverse_factor = det.submodule_size[0] - 1;

  int submodule_line_data_len = (8 * det.submodule_size[1]) / bit_depth;

  int int_line = 0;
  for (int i=line_number + n_lines_per_packet - 1; i >= line_number; i--) {

    long destination_offset = (8 * (reverse_factor + reverse * i) * det.detector_size[1]) / bit_depth;
    long source_offset = (8 * int_line * det.submodule_size[1]) / bit_depth;
    
    //FIXME: would it make sense to do this? Performances issues?
    /*p1 + i * det.detector_size[1],*/
    memcpy((char*)p1 + destination_offset, (char*)data + source_offset, submodule_line_data_len);
                
    int_line++;
  }
}

detector_definition jungfrau_definition = {
  .interpret_udp_packet = interpret_udp_packet_jungfrau,
  .copy_data = copy_data_jungfrau
};