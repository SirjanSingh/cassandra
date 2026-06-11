#!/bin/bash
# Cloud Run edge serving was gated on the fresh project, so we host the same
# image on a Container-Optimized OS VM with an external IP instead (still GCP).
# Secrets are pulled from Secret Manager at boot via the VM service account
# (needs cloud-platform scope + roles/secretmanager.secretAccessor).
set -e

# COS root filesystem is read-only; Docker/credential-helper must write config
# to a writable location or `configure-docker` fails with EROFS on /root/.docker.
export HOME=/tmp
export DOCKER_CONFIG=/tmp/.docker
mkdir -p "${DOCKER_CONFIG}"

PROJECT="cassandra-498318"
IMG="us-central1-docker.pkg.dev/${PROJECT}/cassandra/app:b623fbe-react"
PHX_URL="https://app.phoenix.arize.com/s/sirjan-singh036"

# NOTE: the Secret Manager REST API pretty-prints its JSON ("data": "..." with a
# space), so strip ALL whitespace before grepping or the match silently fails and
# every secret comes back empty (which is exactly what broke the first boot).
TOKEN=$(curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" \
  | tr -d ' \n\t' | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

get_secret() {
  # Also strip any UTF-8 BOM / CR the secret VALUE may carry (a secret created by
  # piping from PowerShell arrives as "<BOM>value<CR>" and corrupts HTTP headers).
  curl -s -H "Authorization: Bearer ${TOKEN}" \
    "https://secretmanager.googleapis.com/v1/projects/${PROJECT}/secrets/$1/versions/latest:access" \
    | tr -d ' \n\t' | grep -o '"data":"[^"]*' | cut -d'"' -f4 | base64 -d \
    | sed 's/^\xef\xbb\xbf//' | tr -d '\r\n'
}

PHX_KEY=$(get_secret phoenix-api-key)
OAI_KEY=$(get_secret openai-api-key)
REPLAY=$(get_secret replay-shared-secret)
# Fail loudly in the serial console if any secret is empty - an empty
# OPENAI_API_KEY makes the patient fall through to Gemini and 500 on /chat.
echo "secret lengths: phx=${#PHX_KEY} oai=${#OAI_KEY} replay=${#REPLAY}"

# Authenticate Docker to Artifact Registry (COS ships docker-credential-gcr).
docker-credential-gcr configure-docker --registries=us-central1-docker.pkg.dev || true

docker rm -f patient dashboard 2>/dev/null || true

# LLM backend = Vertex AI Gemini (hackathon requires Gemini / Google Cloud AI;
# OpenAI is explicitly disallowed). OPENAI_API_KEY is intentionally NOT passed so
# llm.py falls through to Vertex; the VM service account (roles/aiplatform.user +
# cloud-platform scope) provides ADC. Region must be a real region, not 'global'.
GEMINI_VARS="-e GOOGLE_GENAI_USE_VERTEXAI=true -e GOOGLE_CLOUD_PROJECT=${PROJECT} \
  -e GOOGLE_CLOUD_LOCATION=us-central1 -e GEMINI_MODEL=gemini-2.5-flash-lite"

# Host networking so the dashboard reaches the patient at localhost:8082.
docker run -d --name patient --restart=always --network host \
  -e SERVICE=patient -e PORT=8082 \
  -e PHOENIX_BASE_URL="${PHX_URL}" -e PHOENIX_API_KEY="${PHX_KEY}" \
  -e REPLAY_SHARED_SECRET="${REPLAY}" \
  ${GEMINI_VARS} \
  "${IMG}"

# Dashboard on port 80: the only externally-reachable service (judges' URL).
# Standard port avoids ISP/corporate outbound high-port filtering. The patient
# stays on 8082, reached only internally by the dashboard via localhost.
docker run -d --name dashboard --restart=always --network host -u 0 \
  -e SERVICE=dashboard -e PORT=80 \
  -e PATIENT_ENDPOINT="http://localhost:8082/chat" \
  -e PHOENIX_BASE_URL="${PHX_URL}" -e PHOENIX_API_KEY="${PHX_KEY}" \
  -e PHOENIX_MCP_ARGS="-y,@arizeai/phoenix-mcp@latest,--baseUrl,${PHX_URL},--apiKey,${PHX_KEY}" \
  -e REPLAY_SHARED_SECRET="${REPLAY}" \
  ${GEMINI_VARS} -e STATE_BACKEND=local \
  "${IMG}"
