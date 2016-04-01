#!/bin/env python

import fileinput
import collections

#    'connection_closed_abruptly',
#    "broker forced connection closure with reason 'shutdown'",
ignore_ok = [ 
    'Starting RabbitMQ',
    'node           : rabbit@',
    'Memory limit set to',
    'Disk free limit set to',
    'Limiting to approx',
    'FHC read buffering:  '
    'Priority queues enabled, ',
    'msg_store_transient: ',
    'msg_store_persistent: ',
    'started TCP Listener on ',
    'Server startup complete; ',
    'accepting AMQP connection ',
    'Stopping RabbitMQ',
    'stopped TCP Listener',
    ]


def process_log_record( lines ):
    for l in lines:
        for txt in ignore_ok:
            if txt in l:
                return None
    return ''.join( lines )


def run():
    all_records = dict( INFO = [],
                        WARNING = [],
                        ERROR = [] )

    loglines = [ 'Starting RabbitMQ' ]
    for line in fileinput.input():
        if line.startswith( '=INFO REPORT====' ):
            sig = process_log_record( loglines )
            if sig not None:
                all_records[ 'INFO' ].append( 
            loglines = []
        elif line.startswith( '=WARNING REPORT====' ):
            process_log_record( loglines )
            loglines = []
        elif line.startswith( '=ERROR REPORT====' ):
            process_log_record( loglines )
            loglines = []
        loglines.append( line )


if __name__ == '__main__':
    
