import redis

class Redis_Queue( object ):
    """ Simplified access to a single Redis list
    """

    def __init__( self, queue_name=None, **k ):
        """ 
        :param queue_name: name of list in the redis queue

        Remaining args same as for redis.Redis() with the
        following exception:

        Passing url= is equivalent to redis.Redis.from_url(...)
        """
        if 'url' in k:
            self.conn = redis.Redis.from_url( k[ 'url' ] )
        else:
            self.conn = redis.Redis( **k )
        self.qname = queue_name


    @classmethod
    def from_url( cls, url, queue_name=None ):
        return cls( url=url, queue_name=queue_name )


    def set_queue_name( self, newname ):
        self.qname = newname


    def get_queue_name( self ):
        return self.qname


    def qlist( self ):
        qlen = self.conn.llen( self.qname )
        return self.conn.lrange( self.qname, 0, qlen - 1 )


    def qlen( self ):
        return self.conn.llen( self.qname )


    def qpop( self, popcount=1 ):
        element_list = self.conn.lrange( self.qname, 0, popcount - 1 )
        self.conn.ltrim( self.qname, popcount, -1 )
        return element_list


    def qpop_all( self ):
        size = self.qlen()
        return self.qpop( size )


    def qpush( self, msglist ):
        self.conn.rpush( self.qname, *msglist )


if __name__ == '__main__':
    raise UserWarning( 'Command line not supported' )
