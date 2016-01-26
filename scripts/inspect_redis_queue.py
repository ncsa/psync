import os
import redis
import pprint

urlfilepath = os.environ[ 'PSYNCREDISURLFILE' ]
urlfilename = os.path.basename( urlfilepath )
modulename =  os.path.splitext( urlfilename )[0]
mod = __import__( modulename )

conn = redis.from_url( mod.BROKER_URL )
for k in conn.scan_iter():
    pprint.pprint( k )
