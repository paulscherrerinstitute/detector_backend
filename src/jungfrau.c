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
