# SQL Dialect Converter

A small Flask application that converts a SQL query between Oracle, MySQL, and
PostgreSQL using [sqlglot](https://github.com/tobymao/sqlglot).

## Run locally

1. Install Python 3.10 or newer. Check it with:

   ```bash
   python3 --version
   ```

2. From this project directory, create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows PowerShell, activate it with:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   If this reports that `ensurepip` is unavailable on Debian or Ubuntu, install
   the matching `python3-venv` package first (for example,
   `sudo apt install python3.12-venv`), then repeat this step.

3. Install the application dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

4. Start the development server:

   ```bash
   python3 app.py
   ```

5. Open <http://127.0.0.1:5000> in a browser. Enter the source SQL, select
   its dialect and the target dialect, then select **Convert SQL**.

6. Stop the server with `Ctrl+C` when finished. To use the application later,
   activate `.venv` again and repeat step 4.

## Run tests

After installing the dependencies, run:

```bash
python3 -m unittest discover -s tests
```

## JSON API

The browser UI remains available at `/`. Applications and scripts can convert
SQL through `POST /api/convert` with a JSON request body:

```bash
curl -X POST http://127.0.0.1:5000/api/convert \
  -H 'Content-Type: application/json' \
  -d '{
    "source_sql": "SELECT NVL(name, '\''unknown'\'') FROM employees",
    "source_dialect": "oracle",
    "target_dialect": "mysql"
  }'
```

A successful request returns HTTP `200` and JSON containing `converted_sql`,
`source_dialect`, and `target_dialect`. Invalid or incomplete request data
returns HTTP `400`; SQL that cannot be parsed or converted returns HTTP `422`.

After changing the API for Minikube, rebuild and load the image, then restart
the Deployment:

```bash
docker build -t sql-dialect-converter:latest .
minikube image load sql-dialect-converter:latest
kubectl rollout restart deployment/sql-dialect-converter
kubectl rollout status deployment/sql-dialect-converter
```

## Run with Docker in WSL

1. Confirm that the Docker daemon is available:

   ```bash
   docker version
   ```

2. Build the image from the project directory:

   ```bash
   docker build -t sql-dialect-converter .
   ```

3. Start a container and publish its port 5000 to your computer:

   ```bash
   docker run --rm -p 5000:5000 sql-dialect-converter
   ```

4. Open <http://localhost:5000> in a browser. Press `Ctrl+C` in the terminal
   to stop the container. The `--rm` option removes the stopped container
   automatically.

To run it in the background instead, give the container a name:

```bash
docker run -d --name sql-dialect-converter -p 5000:5000 sql-dialect-converter
```

View its logs with `docker logs sql-dialect-converter`, stop it with
`docker stop sql-dialect-converter`, and remove it with
`docker rm sql-dialect-converter`.

## Run with Kubernetes and Minikube

This deployment uses a local Minikube cluster with the Docker driver and a
NodePort service. Confirm that both Docker and Minikube can run in your WSL
terminal before continuing.

1. Start Minikube (the command is safe to repeat if it is already running):

   ```bash
   minikube start --driver=docker
   ```

2. Build the local application image:

   ```bash
   docker build -t sql-dialect-converter:latest .
   ```

3. Load that image into Minikube's container runtime. This avoids requiring a
   remote container registry:

   ```bash
   minikube image load sql-dialect-converter:latest
   ```

4. Create the Deployment and Service:

   ```bash
   kubectl apply -f k8s/sql-dialect-converter.yaml
   kubectl rollout status deployment/sql-dialect-converter
   ```

5. Open the application in a browser:

   ```bash
   minikube service sql-dialect-converter
   ```

   To print the address without opening a browser, use:

   ```bash
   minikube service sql-dialect-converter --url
   ```

Useful Kubernetes commands:

```bash
kubectl get pods
kubectl get services
kubectl logs deployment/sql-dialect-converter
kubectl delete -f k8s/sql-dialect-converter.yaml
```
