SOURCE_DIR = 'tmp/source'
DEST_DIR = 'tmp/dest'
NUM_OBJECTS = 100
MAX_FILE_SIZE = 4*1024
SEED = 1

# Weights for how often each type is created
FILE_WEIGHT     = 3
DIR_WEIGHT      = 1
SYMLINK_WEIGHT  = 1
FIFO_WEIGHT     = 1
SOCKET_WEIGHT   = 1
HARDLINK_WEIGHT = 1

PERMS_USERS  = [ 'aloftus' ]
PERMS_GROUPS = [ 'users' ]

CHMOD_DIR_CHOICES = [0o777,0o775,0o755,0o770,0o750,0o700]
CHMOD_CHOICES     = [0o777,0o775,0o755,0o770,0o750,0o700,
		     0o666,0o664,0o644,0o660,0o640,0o600]

PERMS_ACL_USERS = ['aloftus']
PERMS_ACL_GROUPS = [ 'users' ]
