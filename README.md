# Annotation Pipeline (APL)

## Installation

### Via Docker
Running the annotation pipeline will require Docker to be installed on your computer.
Docker is a flexible piece of software that can quickly deploy complex applications
in a reproducible manner.  You will need to install Docker and Docker-Compose.
Instructions for this can be readily found on Google for your operating system. Once
Docker and Docker-Compose are installed you can execute the following command on the
CLI

    docker-compose up

### For Development Server
Running a development server for APL is more involved, and you will need Redis installed
on your machine before you attempt to run these instructions:

    cd source
    pip install -r requirements.txt
    redis-server &
    python development.py

## Usage
