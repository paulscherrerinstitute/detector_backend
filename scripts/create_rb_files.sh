DST=/dev/shm/rb/

mkdir -p $DST
dd if=/dev/zero of=${DST}/rb_image_header.dat bs=64 count=$1
dd if=/dev/zero of=${DST}/rb_image_data.dat bs=3145728 count=$1
