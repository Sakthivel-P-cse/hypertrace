const sdk = require("@opentelemetry/sdk-node");
const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node");
const { OTLPTraceExporter } = require("@opentelemetry/exporter-trace-otlp-grpc");
const { ConsoleSpanExporter, SimpleSpanProcessor, BatchSpanProcessor } = require("@opentelemetry/sdk-trace-base");
const { Resource } = require("@opentelemetry/resources");
const { SemanticResourceAttributes } = require("@opentelemetry/semantic-conventions");

// Configure the OTLP gRPC exporter
const otlpExporter = new OTLPTraceExporter({
    url: "http://localhost:4317",
});

const sdkWrapper = new sdk.NodeSDK({
    resource: new Resource({
        [SemanticResourceAttributes.SERVICE_NAME]: "my-website-backend",
    }),
    // Use spanProcessors (plural) to have multiple processors
    spanProcessors: [
        new BatchSpanProcessor(otlpExporter),
        new SimpleSpanProcessor(new ConsoleSpanExporter()),
    ],
    instrumentations: [
        getNodeAutoInstrumentations({
            // Disable fs instrumentation to reduce noise
            "@opentelemetry/instrumentation-fs": {
                enabled: false,
            },
        }),
    ],
});

// Initialize the SDK and register with the OpenTelemetry API
sdkWrapper.start();

// Gracefully shut down the SDK on process exit
process.on("SIGTERM", () => {
    sdkWrapper
        .shutdown()
        .then(() => console.log("SDK shut down successfully"))
        .catch((error) => console.log("Error shutting down SDK", error))
        .finally(() => process.exit(0));
});
