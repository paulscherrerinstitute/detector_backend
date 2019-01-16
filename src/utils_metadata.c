#include "detectors.h"

inline uint32_t get_current_module_offset_in_pixels (detector det)
{
  // Origin of the module within the detector, (0, 0) is bottom left
  uint32_t mod_origin = det.detector_size[1] * det.module_idx[0] * det.module_size[0] + det.module_idx[1] * det.module_size[1];
  mod_origin += det.module_idx[1] * ((det.submodule_n - 1) * det.gap_px_chips[1] + det.gap_px_modules[1]); // inter_chip gaps plus inter_module gap
  mod_origin += det.module_idx[0] * (det.gap_px_chips[0] + det.gap_px_modules[0])* det.detector_size[1] ; // inter_chip gaps plus inter_module gap

  // Origin of the submodule within the detector, relative to module origin
  mod_origin += det.detector_size[1] * det.submodule_idx[0] * det.submodule_size[0] + det.submodule_idx[1] * det.submodule_size[1];
  
  if(det.submodule_idx[1] != 0)
  {
    // 2* because there is the inter-quartermodule chip gap
    mod_origin += 2 * det.gap_px_chips[1];   
  }

  // the last takes into account extra space for chip gap within quarter module
  if(det.submodule_idx[0] != 0)
  {
    mod_origin += det.submodule_idx[0] * det.detector_size[1] * det.gap_px_chips[0];
  }

  return mod_origin;
}

inline int get_current_module_index (detector det)
{
  //numbering inside the detctor, growing over the x-axiss
  int mod_number = det.submodule_idx[0] * 2 + det.submodule_idx[1] + 
    det.submodule_n * (det.module_idx[1] + det.module_idx[0] * det.detector_size[1] / det.module_size[1]); 

  return mod_number;
}

inline int get_n_lines_per_packet (detector det, size_t data_bytes_per_packet, int bit_depth)
{
  int bytes_in_line = (det.submodule_size[1] * bit_depth) / 8;
  return data_bytes_per_packet / bytes_in_line;
}

inline int get_n_packets_per_frame (detector det, size_t data_bytes_per_packet, int bit_depth)
{
  int n_pixels_in_frame = (det.submodule_size[0] * det.submodule_size[1]);
  // data_bytes_per_packet / (bit_depth/8)
  int n_pixels_in_packet = (data_bytes_per_packet * 8) / bit_depth;

  return n_pixels_in_frame / n_pixels_in_packet;
}

inline rb_metadata get_ringbuffer_metadata (
  int rb_writer_id, int rb_header_id, int rb_hbuffer_id, int rb_dbuffer_id, int rb_current_slot,  
  detector det, size_t data_bytes_per_packet, int bit_depth )
{
  rb_metadata metadata;

  metadata.rb_writer_id = rb_writer_id;
  metadata.rb_header_id = rb_header_id;

  metadata.rb_hbuffer_id = rb_hbuffer_id;
  metadata.rb_dbuffer_id = rb_dbuffer_id;
  
  // Is this right? Should we calculate this?
  metadata.rb_current_slot = rb_current_slot;
  
  metadata.mod_origin = get_current_module_offset_in_pixels(det);
  metadata.mod_number = get_current_module_index(det);
  metadata.n_lines_per_packet = get_n_lines_per_packet(det, data_bytes_per_packet, bit_depth);
  metadata.n_packets_per_frame = get_n_packets_per_frame(det, data_bytes_per_packet, bit_depth);
  metadata.bit_depth = bit_depth;

  metadata.data_slot_origin = NULL;
  metadata.header_slot_origin = NULL;

  return metadata;
}
