DST=/dev/shm/eiger/

mkdir $DST
#DST=.
dd if=/dev/zero of=${DST}/rb_image_header.dat bs=64 count=10
dd if=/dev/zero of=${DST}/rb_image_data.dat bs=3145728 count=10
