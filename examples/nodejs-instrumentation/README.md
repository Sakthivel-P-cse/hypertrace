# Node.js Instrumentation Example for Hypertrace

This example demonstrates how to instrument a simple Express.js application to send traces to the Hypertrace platform.

## Prerequisites

1.  **Hypertrace Stack:** Ensure the Hypertrace platform is running. You can start it from the root of this repository:
    ```bash
    cd docker
    docker-compose up -d
    ```
2.  **Node.js:** Installed on your local machine.

## Setup

1.  Navigate to this directory:
    ```bash
    cd examples/nodejs-instrumentation
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```

## Running the Application

Start the application using the pre-configured start script:
```bash
npm start
```
This script runs `node -r ./tracing.js server.js`, which loads the instrumentation before your application code.

## Monitoring

1.  Generate some traffic by visiting:
    *   Main page: [http://localhost:3000/](http://localhost:3000/)
    *   Login simulation: [http://localhost:3000/login](http://localhost:3000/login)
    *   Error simulation: [http://localhost:3000/error](http://localhost:3000/error)
2.  Open the Hypertrace UI: [http://localhost:2020](http://localhost:2020)
3.  Go to the **Traces** page to see your requests appearing in real-time.
