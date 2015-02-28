import redis
import logging

redis = redis.StrictRedis( host='net-amqp01.slac.stanford.edu', db=0 )
pipe = redis.pipeline()    

logging.info('fetching...')
for i in redis.keys( 'pt:cap:*' ):
    logging.info( "%s" % (i,))
    pipe.delete( i )

logging.info("deleting...")    
pipe.execute()
