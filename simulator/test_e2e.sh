#!/bin/bash
set -e

echo "Starting end-to-end tests..."

# Step 0: Create dedicated Docker network
docker network create e2e-network || true

# Step 1: Build Docker images
docker build -t hospital-engine ../
docker build -t simulator-image .

# Step 2: Start simulator container (it will auto-send messages)
docker run -d --name simulator  -t --network e2e-network simulator-image

SIM_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' simulator)

while ! nc -z $SIM_IP 8440; do
    sleep 5
    echo "Waiting"
done

echo "Now starting app"
# docker logs -f simulator &
# # Step 3: Start app container
docker run -d --name app --network e2e-network -e MLLP_ADDRESS=simulator:8440 -e PAGER_ADDRESS=simulator:8441 hospital-engine

# # Step 4: Wait for app to be ready
# echo "Waiting for app to process incoming messages..."
sleep 20


# Step 6: Cleanup
docker stop simulator app || true


if docker logs app 2>&1 | grep -q "AKI DETECTED"; then
    echo "Test verification successful."
else
    echo "Test verification unsuccessful."
fi

docker rm simulator app || true
docker network rm e2e-network || true

echo "End-to-end tests completed successfully!"
