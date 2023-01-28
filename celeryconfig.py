import os

# If we are running the application in kubernetes, we must connect to the
# stateful set of the rabbitmq broker.
broker_host_url = os.environ.get('BROKER_HOST_URL', 'localhost')

broker_url = 'amqp://{}:{}@{}:{}//'.format(
    os.environ.get('RABBITMQ_USERNAME', 'guest'),
    os.environ.get('RABBITMQ_PASSWORD', 'guest'),
    broker_host_url,
    os.environ.get('RABBITMQ_SERVICE_PORT_AMQP', 5672)
)
broker_connection_max_retries = 6  # Num of times workers attempt to connect
imports = "tasks"
result_backend = 'rpc://'  # The backend service used to track tasks
result_persistent = True  # Stores state of tasks even after service restart
task_track_started = True  # Updates task status when started to STARTED
task_soft_time_limit = 60  # How long a task will be attempted
worker_concurrency = 1  # Number of workers should match number of CPUs
