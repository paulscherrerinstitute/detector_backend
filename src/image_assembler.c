#include <string.h>
#include <unistd.h>
#include <inttypes.h>

void assemble_image (
        char* source_root, 
        char* destination_root, 
        size_t* dest_move_offsets,
        uint32_t n_moves,
        size_t n_bytes_per_move)
{

  char* source = source_root;
  for (uint32_t i_move=0; i_move<n_moves; i_move++) {
    char* destination = destination_root + dest_move_offsets[i_move];
    memcpy(destination, source, n_bytes_per_move); 
    source += n_bytes_per_move; 
  }

}
