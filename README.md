# Annotation Pipeline (APL)

## Installation

### For Development Server
Running a development server for APL is not difficult, but you will need Redis installed
on your machine before you attempt to run these instructions:

    cd source
    pip install -r requirements.txt
    redis-server &
    python development.py

### Via Docker
#### Configuration
Since this will be how you will run a production server, you'll need to configure the
app properly for a production environment.

    touch prod_config.py

Then enter the prod_config.py file with a text editor and add the following information:

    REDIS = {
        'host': 'apl-redis',
        'port': 6379,
        'db': 0,
    }
    SECRET_KEY = 'XXX'

`SECRET_KEY` should be changed to whatever you deem appropriate however.

#### Finalize
Running the annotation pipeline will require Docker to be installed on your computer.
Docker is a flexible piece of software that can quickly deploy complex applications
in a reproducible manner.  You will need to install Docker and Docker-Compose.
Instructions for this can be readily found on Google for your operating system. Once
Docker and Docker-Compose are installed you can execute the following command on the
CLI

    docker-compose up

## Usage
