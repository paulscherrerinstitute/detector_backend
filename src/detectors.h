// header struct for RB - to be updated to include the framenums of all modules
#include <inttypes.h>


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
} detector_common_packet

// 48 bytes + 4096 bytes = 4144 bytes.
typedef struct _eiger_packet {
  struct detector_common_packet metadata;
  char data[4096];
} eiger_packet;



// 6 bytes + 48 bytes + 8192 bytes = 8246 bytes
#pragma pack(push)
#pragma pack(2)
typedef struct _jungfrau_packet{
  char emptyheader[6];
  struct detector_common_packet metadata;
  char data[8192];
} jungfrau_packet;
#pragma pack(pop)

