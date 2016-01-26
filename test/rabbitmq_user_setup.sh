source ~aloftus/psync/config/bashrc

set -x
RMQCTL=$RABBITMQ_HOME/sbin/rabbitmqctl

erlbinpath=$( dirname $( readlink -e $PATHTOERL ) )

vhost="$PSYNCRMQVHOST/"

PATH=$PATH:$erlbinpath
HOME=~aloftus/var/rabbitmq_psync

$RMQCTL add_user $PSYNCRMQUSER $PSYNCRMQPASS

$RMQCTL add_vhost $vhost

$RMQCTL set_permissions -p $vhost $PSYNCRMQUSER ".*" ".*" ".*"

set +x
