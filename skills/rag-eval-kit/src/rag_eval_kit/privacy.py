"""Configure local-only DeepEval operation before importing the framework."""

import os


def configure_local_runtime() -> None:
    for key, value in {
        "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
        "DEEPEVAL_TELEMETRY_ENABLED": "0",
        "DEEPEVAL_DISABLE_DOTENV": "1",
        "DEEPEVAL_DISABLE_LEGACY_KEYFILE": "1",
        "DEEPEVAL_AUTO_TRACE": "0",
        "OTEL_SDK_DISABLED": "true",
    }.items():
        os.environ[key] = value
    # This tool never publishes datasets, traces or evaluations to Confident AI.
    os.environ.pop("CONFIDENT_API_KEY", None)
