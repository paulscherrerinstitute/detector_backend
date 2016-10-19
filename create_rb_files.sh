#DST=/dev/shm/eiger/

#mkdir $DST
DST=.
dd if=/dev/zero of=${DST}/rb_image_header.dat bs=64 count=100
dd if=/dev/zero of=${DST}/rb_image_data.dat bs=262144 count=200
