#!/bin/bash

DST=/dev/shm/rb/
COUNT=20000
SIZE=3145728 # 6 modules, historical value

if [ "$#" -gt 0 ]
then
  COUNT=$1
fi

if [ "$#" -ge 2 ]
then
  DST=$2
fi

if [ "$#" -ge 3 ]
then
  SIZE=$3
fi

mkdir -p $DST
dd if=/dev/zero of=${DST}/rb_image_header.dat bs=64      count=${COUNT}
dd if=/dev/zero of=${DST}/rb_image_data.dat   bs=${SIZE} count=${COUNT}
