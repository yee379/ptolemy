#!/bin/sh

for i in `ps aux | grep polld | awk '{print $13}' | sort | uniq -dc | awk '{print $2}'`; do echo $i; ps aux | grep $i | awk '{print $2}' | xargs  -n1 sudo kill -9 ; done


# kill ssrl
ps aux | grep polld | grep ssrl | awk '{print $2}' | xargs -t  -n1 sudo kill -9


