# Data acquisition backend

# UDP receiver logic

File **src/udp\_receiver.c**

```
  Logic:
    recv_packets ++
    if got_pkg == pred_pkg && last_frame == packet.frame:
      //this is the last packet of the frame
      tot_frames++
      recv_packets = 0
      last_frame = 0 // this will cause getting a new slot afterwards
      commit_flag = true // for committing the slot later

    else if last_frame != packet frame:
      // this means a new frame arrived
      if last_frame == 0:
        // this means prev frame was ok, and no dangling slot exists
        
      else:
        // this means we lost some packets before
        commit dangling slot
        do_stats with recv_packets -1
        recv_packets = 1

      last_frame = packet_frame
      get new slot
    move p1, ph accordingly
    copy to memory
    update counters 

    if commit_flag:
      // this commits the slot when the frame has been succesfully received

      commit slot
      commit_flag = false
commit_flag
  Cases:
    first packet arrives:
      recv_packets ++
      last_frame is 0, it is updated
      new slot is allocated
      data is copied
    last packet arrives, no packets loss:
      recv_packets ++
      tot_frames++
      counters resetted
      last_frame to 0
      data is copied
      slot is committed
    last packet arrives, packets lost:
      case 2: previous slot is committed, stats updated
      last frame updated
      new slot allocated
      data is copied
```

# Development

## Running the tests

Before each major commit, please run the unittest suite. In order to do so, you do need the ``detector_replay`` package, that can be retrieved here: https://git.psi.ch/HPDI/detector_replay

Then:
```
cd tests
python -m unittest test_reconstruction
```

This should that 1-2 minutes on a laptop.
