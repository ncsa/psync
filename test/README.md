# Psync functional tests 

Psync functional tests are designed using pytest (https://pytest.org).

## To run functional tests:

1. Create/Edit config file
     $PSYNCHOME/config/bashrc
2. Start services
   1. Start RabbitMQ
   2. Start Redis
   3. Start (one or more) Psyncd Celery workers
2. Run tests
     cd $PSYNCHOME/
     test/runtest
