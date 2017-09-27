#!/bin/bash

N=$1
sharing=$2
cmd="perf stat -e instructions,faults,cycles,cache-references,cache-misses,branches,branch-misses,branch-instructions,migrations taskset"

PIDS=()
let N1=N-1
for i in `seq 0 ${N1}`; do
    if [ $sharing == 1 ]; then 
	$cmd -c $i ./test_cache $i 1  &>> ${N}_${sharing}.log &
    else
	$cmd -c $i ./test_cache $i $i &>> ${N}_${sharing}.log &
    fi
    PIDS[i]=$!
done

for pid in ${PIDS[@]}; do
###for i in `seq 1 9`; do
    echo $pid
    while [ -d /proc/$pid ]; do
	sleep 0.01
    done
done



