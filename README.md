# AKI Prediction Service

This project implements a real-time Acute Kidney Injury (AKI) prediction service.
It ingests HL7 messages, maintains patient state, performs ML-based inference, and
notifies an external pager service when AKI is detected.

## Overview

The service is designed to operate as a hospital-side backend component that
processes incoming laboratory and patient administration data in real time.
Incoming HL7 messages are parsed, persisted, and evaluated by a machine learning
model to determine whether a patient is at risk of AKI. When AKI is detected,
an external pager/alerting service is notified.

## Architecture

The system is implemented as a single containerized service with a clear separation
of concerns across:

- Transport and message ingestion (MLLP over TCP)
- HL7 parsing and validation
- Persistence and patient state management
- ML-based inference
- External alerting integrations

A separate simulator is provided for end-to-end testing.

## Project Structure

root/
* app/
    * controller/ 
        - Centralized orchestration layer responsible for database operations, inference execution, and pager notifications.
    * data/ 
        - Stores patient history used for prediction and pre-trained model weights.
    * db/
        - Database initialization scripts and database manager responsible for data persistence and transactions.
    * hl7/
        - HL7 message parsing and processing logic.
    * inference/
        - Inference engine for generating AKI predictions based on patient history and current creatinine results.
    * logs/
        - Application error log
    * receiver/
        - Establishes connections to LIMS and PAS systems, receives MLLP messages over TCP, and forwards parsed HL7 messages to the HL7 handler.
    * tests/
        - Unit and integration tests for application modules.
    * config.py
        - Logging configuration.
    * main.py
        - Application entry point used by Docker.
* simulator/
    - Contains a hospital simulator used for end-to-end testing.
      This component is built as a separate Docker image and has its own `Dockerfile`.

* Dockerfile
    - Dockerfile for the `hospital-engine` application.
      Only the code in `app/` is included in this image.
* README.md
    - Project documentation.
* requirements.txt
    - Python dependencies for the `hospital-engine` Docker image.


## Requirements

- Python 3.x
- Docker (optional, for containerized deployment)
- numpy
- lightgbm
- requests


## Building and Running

### Building using Docker
The project can be built using the DockerFile in the root/ directory. 
```bash
docker build -t hospital-engine .
```

### Running using Docker
The project can be run as a docker container after the docker image has been built
```bash
docker run -it --network host hospital-engine
```

`-it` allows for live terminal output and `--network host` allows the container to access ports open on the host machine for network capabilties. (This only works on unix systems)

### Running locally
Alternatively, this project can be run locally not using Docker. The project can be run from from the app/ directory as such:
```bash
python3 -m ./main.py
```


## Testing
### Unit and Integration testing

The `app/tests/` directory contains its own `README_tests.md` explaining how to run tests.

### End to End testing

An End to End test can be run with `bash test_e2e.sh` from the simulator/ directory. This script will build both the app and the simulator as docker images and run them using a custom test file with only 10 MLLP messages. Some of these are malformed and some contain invalid data. The script shows that the app will not crash even when presented with bad mllp messages.
