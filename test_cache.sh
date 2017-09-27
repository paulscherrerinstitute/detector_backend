#!/bin/bash


for i in `seq 1 9`; do
    taskset -c 1 ./test_cache $i 0 &
done
time taskset -c 1 ./test_cache 10 0 &


