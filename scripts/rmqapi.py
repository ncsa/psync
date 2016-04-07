import sys
import requests
import pprint

URLBASE='http://localhost:15672/api/'
USER='guest'
PASS='guest'


def do_json_req( url ):
    r = requests.get( url, auth=( USER, PASS ) )
    r.raise_for_status()
    data = r.json()
    pprint.pprint( data )
    

if __name__ == '__main__':
    arglist = sys.argv[1:]
    if len( sys.argv ) < 2:
        arglist = [ 'overview' ]
    for a in arglist:
        do_json_req( URLBASE + a )

