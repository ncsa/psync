import redis_queue
import time
import functools
import os
import cbor

class Redis_Logger( object ):

    valid_names = ( 'debug', 'info', 'warning', 'error', )

    def __init__( self, *a, **k ):
        """
        Same args as for redis_queue.Redis_Queue()
        """
        self.rq = redis_queue.Redis_Queue( *a, **k )

    def set_log_name( self, newname ):
        self.rq.set_queue_name( newname )

    def __getattr__( self, name ):
        """ Creates dynamic function named for typical logging actions
            using names in self.valid_names (ie: debug, log, warning,
            etc...)
        """
        # TODO - Is this less efficient than just defining each function?
        if name not in self.valid_names:
            raise AttributeError( 
                "'{0}' object has no attribute '{1}'".format( 
                    self.__class__.__name__, name ) )
        return functools.partial( self._log_it, name )

    def _log_it( self, loglvl, *a, **k ):
        ts = int( time.time() )
        hn = os.uname()[1]
        msg = ''.join( a )
#        logstr = '{lvl} {ts} {hn} {msg}'.format( 
#            lvl=loglvl.upper(), ts=ts, msg=msg, hn=hn )
#        self.rq.qpush( [ logstr ] )
        k.update( sev  = loglvl.upper(), 
                  ts   = ts, 
                  host = hn, 
                  msg  = msg )
        logd = cbor.dumps( k )
        self.rq.qpush( [ logd ] )

if __name__ == '__main__':
    raise UserWarning( 'Cmdline not supported' )
