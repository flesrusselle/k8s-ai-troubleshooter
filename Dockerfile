# syntax=docker/dockerfile:1.7
# Build with current, reviewed values for KUBECTL_VERSION and HELM_VERSION.
# Pin the base image to a digest in release builds, e.g.:
#   docker build --build-arg PYTHON_IMAGE=python:3.14-alpine@sha256:<digest> .
ARG PYTHON_IMAGE=python:3.14-alpine
FROM ${PYTHON_IMAGE} AS runtime

# kubectl: https://kubernetes.io/releases/
ARG KUBECTL_VERSION=v1.37.0
# helm: https://github.com/helm/helm/releases  (Helm 4 — Helm 3 EOL Feb 2027)
ARG HELM_VERSION=v4.2.4
# Target CPU architecture — supports linux/amd64 and linux/arm64
ARG TARGETARCH=amd64

RUN apk update && apk upgrade --no-cache \
    && apk add --no-cache ca-certificates curl tar \
    && KUBECTL_ARCH="${TARGETARCH}" \
    && curl --fail --silent --show-error --location \
       "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${KUBECTL_ARCH}/kubectl" \
       --output /usr/local/bin/kubectl \
    && curl --fail --silent --show-error --location \
       "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${KUBECTL_ARCH}/kubectl.sha256" \
       --output /tmp/kubectl.sha256 \
    && echo "$(cat /tmp/kubectl.sha256)  /usr/local/bin/kubectl" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/kubectl \
    && HELM_ARCH="${TARGETARCH}" \
    && curl --fail --silent --show-error --location \
       "https://get.helm.sh/helm-${HELM_VERSION}-linux-${HELM_ARCH}.tar.gz" \
       --output /tmp/helm.tar.gz \
    && curl --fail --silent --show-error --location \
       "https://get.helm.sh/helm-${HELM_VERSION}-linux-${HELM_ARCH}.tar.gz.sha256sum" \
       --output /tmp/helm.sha256sum \
   && expected_helm_sha="$(awk "\$2 == \"helm-${HELM_VERSION}-linux-${HELM_ARCH}.tar.gz\" {print \$1}" /tmp/helm.sha256sum)" \
   && test -n "${expected_helm_sha}" \
   && echo "${expected_helm_sha}  /tmp/helm.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/helm.tar.gz -C /tmp \
    && install -m 0755 /tmp/linux-${HELM_ARCH}/helm /usr/local/bin/helm \
    && rm -rf /tmp/helm.tar.gz /tmp/helm.sha256sum /tmp/linux-${HELM_ARCH} \
              /tmp/kubectl.sha256 \
    && apk del curl tar

WORKDIR /app
COPY requirements.txt ./
RUN python3 -m pip install --no-cache-dir --upgrade pip "setuptools>=78.1.1" \
    && python3 -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
COPY . .

RUN addgroup -S -g 65532 app \
    && adduser -S -D -H -u 65532 -G app app \
    && mkdir -p /evidence /tmp \
    && chown -R 65532:65532 /app /evidence /tmp

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp
USER 65532:65532

ENTRYPOINT ["python3", "scripts/container_entrypoint.py"]
CMD ["--help"]
