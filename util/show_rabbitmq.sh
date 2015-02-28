#!/bin/sh

# [name, durable, auto_delete, 
# arguments, pid, owner_pid, exclusive_consumer_pid, exclusive_consumer_tag, 
# messages_ready, messages_unacknowledged, messages, consumers, memory, 
# slave_pids, synchronised_slave_pids].
echo "queue                                                  dur     del   mem      cns msgs  q  processing"
/usr/sbin/rabbitmqctl  -p /ptolemy list_queues name durable  auto_delete memory consumers messages messages_ready messages_unacknowledged | sort | column -t -x 

