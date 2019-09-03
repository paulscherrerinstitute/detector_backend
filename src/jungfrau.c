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
