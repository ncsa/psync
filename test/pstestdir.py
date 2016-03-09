import psconfig as config
import random
import string
import sys
import os
from bisect import bisect
import shutil
import stat
import pwd
import grp
#import posix1e

objects = []
files = []
source = config.SOURCE_DIR
target = config.DEST_DIR
directories = [config.SOURCE_DIR]
uids = [pwd.getpwnam(user).pw_uid for user in config.PERMS_USERS]
gids = [grp.getgrnam(group).gr_gid for group in config.PERMS_GROUPS]

def human_filesize(size):
    if size < 1024:
        return "%dB" % size
    for suffix in ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB']:
        if size < 1024.0:
            return "%3.1f%s" % (size, suffix)
        size /= 1024.0
    return "%.1fYiB" % size

def weighted_choice(choices):
    values, weights = zip(*choices)
    cum_weights = []
    total = 0
    for weight in weights:
        total += weight
        cum_weights.append(total)
    return values[bisect(cum_weights, random.random() * total)]

def rand_filepath():
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    dir = random.choice(directories)
    filepath = os.path.join(dir, ''.join(random.sample(chars, random.randint(1,10))))

    return filepath if not os.path.exists(filepath) \
                else rand_filepath()

def create_file():
    filename = rand_filepath()
    filesize = random.randint(0,config.MAX_FILE_SIZE)
    #objects.append((filename,'f', "%s (%s)" % (filename, human_filesize(filesize))))
    objects.append( ( filename, 'f', filesize ) )
    files.append(filename)
    with open(filename,'wb') as f:
        f.write(os.urandom(filesize))

def create_directory():
    dir = rand_filepath()
    os.makedirs(dir)
    objects.append((dir,'d',dir))
    directories.append(dir)

def create_symlink():
    link = rand_filepath()    
    target = random.choice(objects)[0]
    os.symlink(target,link)
    objects.append( ( link, 'l', target ) )

def create_hardlink():
    link = rand_filepath()    
    target = random.choice(files)
    os.link(target,link)
    files.append(link)
    objects.append( ( link, 'h', target ) )

def perms_chmod(path, type):
    if type is 'd':
        mode = random.choice(config.CHMOD_DIR_CHOICES)
    else:
        mode = random.choice(config.CHMOD_CHOICES)
    if type is not 'l':
        os.chmod(path, mode)

def perms_chown(path):
    os.lchown(path, random.choice(uids), random.choice(gids))

def perms_pass(path):
    pass

def perms_acl(path,type):
    if type is 'd':
        return
    acl_users = random.sample(config.PERMS_ACL_USERS, random.randint(0,len(config.PERMS_ACL_USERS)))
    acl_groups = random.sample(config.PERMS_ACL_GROUPS, random.randint(0,len(config.PERMS_ACL_GROUPS)))
    ac_u = []
    ac_g = []
    ac = []
    for user in acl_users:
        if type is 'd' and user == pwd.getpwuid(os.getuid()).pw_name:
            ac_u.append("u:" + user + ":r" + random.choice(['w','-']) + "x")
        else:
            ac_u.append("u:" + user + ":r" + random.choice(['w','-']) + random.choice(['x','-']))
    
    for group in acl_groups:
        ac_g.append("g:" + random.choice(config.PERMS_ACL_GROUPS) + ":" + random.choice(['r','-']) + random.choice(['w','-']) + random.choice(['x','-']))
    if len(ac_u) > 0:
        ac.append(','.join(ac_u))
    if len(ac_g) > 0:
        ac.append(','.join(ac_g))
    if random.random() < 0.5:
        ac_o = "o::" + random.choice(['r','-']) + random.choice(['w','-']) + random.choice(['x','-'])
        ac.append(ac_o)
    text=','.join(ac)
#    acl = posix1e.ACL(text=text)
#    path2 = os.path.join(os.getcwd(), path)
#    acl.applyto(path2)

def initialize():
    os.makedirs(config.SOURCE_DIR)
    os.makedirs(config.DEST_DIR)
    #create files
    create_file()
    for i in range( config.NUM_OBJECTS - 1 ):
        create = weighted_choice((  ( create_file,       config.FILE_WEIGHT     ),
                                    ( create_directory,  config.DIR_WEIGHT      ),
                                    ( create_symlink,    config.SYMLINK_WEIGHT  ),
                                    ( create_hardlink,   config.HARDLINK_WEIGHT )
                                 ))
        create()
    #chmod
    for path, type, description in objects:
        perms_chmod(path, type)
    #chown
    for path, type, description in objects:
        perms_chown(path)
    #acl
    #for path, type, description in objects:
    #    perms_acl(path, type)
    return ( objects, files )

def reset():
    try:
        shutil.rmtree(config.SOURCE_DIR)
    except ( OSError ) as e:
        if e.errno == 2: # OSError: [Errno 2] No such file or directory:
            pass
        else:
            raise e
    try:
        shutil.rmtree(config.DEST_DIR)
    except ( OSError ) as e:
        if e.errno == 2:
            pass
        else:
            raise e
    initialize()
    

if __name__ == '__main__':
    random.seed(a=config.SEED)
        
    reset()
    for path, type, description in objects:
        mode = oct(stat.S_IMODE(os.lstat(path).st_mode))
        print( '{0}\t{1} ({2})'.format( type, description, mode ) )
        
# vim:set softtabstop=4 shiftwidth=4 tabstop=4 expandtab:
