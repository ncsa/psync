# psync
Parallel Synchronization For Locally Mounted File Systems

Psync is a python library that makes use of Celery for distributing work to
many nodes and processes to achieve the goal of rapid synchronization through
parallelization.

# Requirements
* Python 2.7.10
* [ Redis 3.0.6 ] ( http://redis.io/ )
* [ RabbitMQ ] ( http://www.rabbitmq.com/ )
* [ Python Virtual Env ] ( http://docs.python-guide.org/en/latest/dev/virtualenvs/ )
* [ pylut ] ( https://github.com/ncsa/pylut ) (See note #2)
* (Additional requirements are all python libraries and will be installed below)

# Notes
1. All commands in this readme are assumed to be run as root unless otherwise 
specified.
2.  This version depends on [ pylut ] ( https://github.com/ncsa/pylut ), thus it
is specific to Lustre.  Psync can be made more generic by replacing the
dependency on Pylut with any other library that provides generic file copy
operations.  It should be possible to dynamically check the filesystem type of
both source and target and load the appropriate module.  As such, the Pylut
module should only be loaded if both source and target are of type Lustre.
Otherwise, a generic (non-Lustre-stripe-aware) copy module would be loaded.
Also, additional modules could be written that are specific to other filesystem
types (to take advantage of filesystem specific optimizations) and thus these
could be loaded if the source and target filesystems are both of the specific
type.


# Installation
* Install rabbitmq
  * Must be accessible to the node that will run the rabbitmq service.  While
    this may seem obvious, take note that the rabbitmq service does not
    required a dedicated host, it can run from any node. A useful setup is to
    install rabbitmq to a location on a shared filesystem, which will allow any 
    node to run the rabbitmq service.
* Install redis
  * Same as for rabbitmq, installing to a shared filesystem will allow any node 
    to run the redis service, or a dedicated machine can have it installed locally.
* Install Python virtualenv
  * `pip install virtualenv`
* Choose install location.
  * Note: psync should be installed where it will be accessible to all worker
    nodes (such as on a shared filesystem).
  * Note: The location is not required to be in any pre-determined python
    accessible place (this will be addressed in the psync config).
  * This example assumes `$HOME` is sufficient (where the current user is a 
    regular user, **not root**)
  * `cd ~`  *non-root*
* Get pylut (required for psync)
  * `git clone https://github.com/ncsa/pylut.git` *non-root*
* Get psync
  * `git clone https://github.com/ncsa/psync.git` *non-root*
* Create a virtualenv for psync
  * `cd psync` *non-root*
  * `virtualenv venv` *non-root*
  * `source venv/bin/activate` *non-root*
* Install the additional python required libraries
  * `pip install -r requirements.txt` *non-root*
* Edit the config file for your environment
  * `cp config/bashrc.template config/bashrc` *non-root*
  * `vim config/bashrc` *non-root*
* Set root permissions on psync config (necessary when celery is run as root)
  * `chown root:root config/psync_service.config`
  * `chmod 400 config/psync_service.config`

# Running Psync
There are three major parts of psync that each need to be running before
starting a sync:

1. Message Broker (implements a task queue)
2. Logging Service (centralized logging)
3. Worker Nodes (retrieve tasks from the task queue and execute them)

Each of these services can run on different systems or the same system or any
combination thereof.  
The only requirements are that all nodes share a common network and that all
worker nodes mount the necessary filesystems (ie: source, target, and any other
paths configured in the bashrc config file).
The rest of this readme will assume that each service will run on a separate node.
It is also assumed that psync is running on a cluster.

1. Start the rabbitmq message broker (task queue)
  1. Login to the machine that will run rabbitmq
  2. `/path/to/psync/bin/rabbitmq_psync start`
  3. `/path/to/psync/bin/rabbitmq_psync status`
  4. If this is the very first time rabbitmq has been run on this node:
    1. `/path/to/psync/bin/rabbitmq_user_setup.sh`
      * This sets up a virtual host and creates a user that can access the
        vhost with the given password.  All these settings are defined in the
        bashrc config file.
2. Start the redis server (centralized logging)
  1. Login to the machine that will run redis
  2. `/path/to/psync/bin/redis_psync start`
  3. `/path/to/psync/bin/redis_psync status`
3. Start psyncd on the worker nodes
  1. On each worker node: `/path/to/psync/bin/psyncd start`
    1. `/path/to/psync/bin/psyncd start`
    2. `/path/to/psync/bin/psyncd status`
4. Start a sync
  1. On a single worker node:
    1. `/path/to/psync/bin/start_psync [OPTIONS] /src/dir tgt/dir
      * Note: Specify the **-h** option for a help message.
5. Collect logs from the redis server
  1. `/path/to/psync/bin/get_psync_logs.sh -i 1 /path/to/logfile_basename`
    * The logs will be split into separate files based on severity (ie:
      logfile_basename.INFO, logfile_basename.WARNING, etc.)
    * Change the argument to -i for multiple iterations.
    * Add a -p argument to specify pause length betwee iterations (pause length
      is specified as number of seconds).

## Monitoring Progress
* Check status of all workers
  * `/path/to/psync/bin/workers_status`
  * `/path/to/psync/bin/workers_status -i`
* Check all psync logs, redis logs, rabbitmq logs, worker logs for errors
  * `path/to/psync/test/progress_report.sh`

## Interrupting A Sync In Progress
* Graceful (allow running processes to finish)
  * `/path/to/psync/bin/workers_pause -r -w`
* Force (kill active processes)
  * `/path/to/psync/bin/workers_pause -r -w -k`

## Determining When A Psync Has Finished
A psync is finished when all of the following are true:

1. `workers_status -i` shows no more tasks are running
2. `get_psync_logs.sh` returns 0 logs for multiple iterations.

## Shutting Down
1. Stop psyncd services (on workers)
  1. `/path/to/psync/bin/workers_shutdown`
  * Note: can also use `/path/to/psync/bin/psyncd stop` on each worker node, 
    but using `workers_shutdown` is usually easier and faster.
2. Stop redis service
  1. Login to the machine that is running redis
  2. `/path/to/psync/bin/redis_psync stop`
3. Stop rabbitmq service
  1. Login to the machine that is running rabbitmq
  2. `/path/to/psync/bin/rabbitmq_psync stop`

## Other useful commands
* Check/Change number of procs per worker
  * `/path/to/psync/bin/set_pool_size -h`
  * Note: It is best to set the pool size before starting psync.  Once the
    workers are busy, reducing pool size will likely timeout waiting for
    a worker process to become idle. On the other hand, growing the pool size 
    is easy.

* To keep logs from separate psync runs organized, use the following command
  to rename all logs from a given run by adding the start timestamp as
  a filename prefix:
  * `/path/to/psync/test/rename_log_files.sh /path/to/log_file.INFO`

# Sample Setup
In the `sample` directory, there are some files that may understand the
workflow.  On a large cluster, 102 nodes were reserved for file migration (one
for rmq, one for redis, and 100 for workers).  From the login node,
the root user can ssh to any cluster in the node and can also use the `pcmd`
command to run remote commands on any node (or nodes) in the cluster.
Rabbitmq, redis, pylut, and psync (and dependencies) have all been installed to
user **aloftus**'s home directory on a shared filesystem mounted cluster-wide.
In the `sample` directory, the `hostlist` files contain lists of nodes and
the `pcmd.rc` file maps environment variable names to filenames for use by the
`pcmd` command.

A sample run might look something like this:
* Login to the login node as root.
* `source ~aloftus/psync/config/bashrc`
* `source $PSYNCBASEDIR/sample/pcmd.rc`
* Start rabbitmq
  * `pcmd -f $WCOLLRMQ "$PSYNCBASEDIR/bin/rabbitmq_psync start"`
  * First time only
    * `pcmd -f $WCOLLRMQ "$PSYNCBASEDIR/bin/rabbitmq_user_setup"`
* Start redis
  * `pcmd -f $WCOLLREDIS "$PSYNCBASEDIR/bin/redis_psync start"`
* Start workers
  * `pcmd -f $WCOLL "$PSYNCBASEDIR/bin/psyncd start"`
* Check that all workers started
  * `pcmd -f $WCOLLREDIS "$PSYNCBASEDIR/bin/workers_status"`
* (Optional) Limit the number of processes per worker
  * `pcmd -f $WCOLLREDIS "$PSYNCBASEDIR/bin/set_pool_size -s 4"`
  * Check that all workers now have only 4 processes each
    * `pcmd -f $WCOLLREDIS "$PSYNCBASEDIR/bin/workers_status"`
* Start a sync
  * `pcmd -f $WCOLLREDIS "$PSYNCBASEDIR/bin/start_psync -tpog -m 3600 /mnt/a
    /mnt/b/a.working"`
* Collect logs and monitor progress
  * Repeat until all workers are idle AND no more logs
  * Collect logs
    * `watch -n 60 "pcmd -f $WCOLLREDIS '$PSYNCBASEDIR/bin/get_psync_logs.sh -i
    1 $PSYNCLOGDIR/psync_mnt_a' "`
    * __OR__
    * `ssh $WCOLLREDIS "$PSYNCBASEDIR/bin/get_psync_logs.sh -i 100 -p 60
    $PSYNCLOGDIR/psync_mnt_a"`
  * Monitor progress
    * `cd $PSYNCLOGDIR`
    * `$PSYNCBASEDIR/test/progress_report.sh`
* Shutdown all services
  * `pcmd -f $WCOLLREDIS "$PSYNCBASEDIR/bin/workers_shutdown"`
  * `pcmd -f $WCOLLREDIS "$PSYNCBASEDIR/bin/redis_psync stop"`
  * `pcmd -f $WCOLLRMQ "$PSYNCBASEDIR/bin/rabbitmq_psync stop"`
* Rename log files for this run
  * `$PSYNCBASEDIR/test/rename_log_files.sh $PSYNCLOGDIR/psync_mnt_a.INFO`
