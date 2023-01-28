#!/bin/bash
set -e

# This Script will start up everything needed locally to test changes to Chronopigeon
# 0. Ensure python environment is initialized
# 1. Start RabbitMQ via a docker container
# 3. Start the Celery Worker to process message requests
# 4. Start the Chronopigeon GRPC server

printf "\n ######## Running in $OSTYPE OS Type ######## \n\n"
docker="docker"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  docker="sudo docker"
fi

version=$(python3 -V 2>&1 | cut -d ' ' -f 2 )
if [[ -z "$version" ]]; then 
  printf "\n Python not detected. Python version 3.8+ is required to run Chronopigeon, please install and make available at Python3 \n\n";
  exit
fi

majversion=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:1])))')
minversion=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[1:2])))')

if [ "$majversion" -ne 3 ] || [ "$minversion" -lt 2 ]; then
  printf "\n Python version $version detected. Python version 3.2+ is required to run Chronopigeon, please install and make available at Python3 \n\n";
  exit
fi

function cleanup {
  printf "\n ######## Cleaning up containers ######## \n\n"
  for name in $($docker ps --format "{{.Names}}"); do
    eval "$docker kill \"$name\" &";
  done
  kill $(ps aux | grep '[s]erver.py' | awk '{print $2}')
}

trap cleanup EXIT

printf "\n ######## Initialize local python environment: ######## \n\n"
python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install --upgrade pip && pip install -r requirements.txt

../../scripts/ruby/gen-pbs-python.rb

printf "\n ######## RabbitMQ with port 5672 exposed and backgrounded: ######## \n\n"
$docker run --rm -d --hostname rabbit --name rabbit -p 127.0.0.1:5672:5672 rabbitmq

# add tails of the container logs to the output:
for name in $($docker ps --format "{{.Names}}"); do
  eval "$docker logs -f --tail=5 \"$name\" | sed -e \"s/^/[-- $name --] /\" &";
done

# sleep to allow Rabbit to fully start up
sleep 10

printf "\n ######## Celery worker running from the installed module and backgrounded: ######## \n\n"
python3 -m celery worker --loglevel=INFO &
sleep 1

printf "\n ######## Chronopigeon running in the background: ######## \n\n"
python3 server.py &

wait
