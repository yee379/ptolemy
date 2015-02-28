#!/bin/sh

#/usr/sbin/rabbitmqctl stop_app
#/usr/sbin/rabbitmqctl reset
#/usr/sbin/rabbitmqctl start_app

/usr/sbin/rabbitmqctl  delete_vhost /ptolemy
/usr/sbin/rabbitmqctl  add_vhost /ptolemy
/usr/sbin/rabbitmqctl  add_user ptolemy ptolemy
/usr/sbin/rabbitmqctl  set_permissions -p /ptolemy ptolemy ".*" ".*" ".*"

