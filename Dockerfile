# syntax=docker/dockerfile:1
FROM nvidia/cuda:13.0.2-cudnn-runtime-ubuntu24.04@sha256:14d94b039cb94bbd5da559f303b46bc4b0d5d6c24ab1a9d7b186e566ed3400dc

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    COMFY_LOG_LEVEL=INFO \
    GIT_TERMINAL_PROMPT=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl ffmpeg git libgl1 libglib2.0-0t64 libtcmalloc-minimal4 \
    openssh-server python3.12 python3.12-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3.12 -m venv /opt/venv

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu130 \
    torch==2.11.0+cu130 torchvision==0.26.0+cu130 torchaudio==2.11.0+cu130

# Match the ComfyUI commit shipped by huchukato/comfyui-base:cu130.
ARG COMFYUI_REV=10cdd12609eb17e8a90f2a2dd811b1c82f6107e7
RUN git init /comfyui \
    && git -C /comfyui fetch --depth=1 https://github.com/Comfy-Org/ComfyUI.git "$COMFYUI_REV" \
    && git -C /comfyui checkout --detach FETCH_HEAD \
    && pip install --no-cache-dir -r /comfyui/requirements.txt 'transformers>=4.50.3,<5' \
    && rm -rf /comfyui/.git

COPY custom-nodes.lock install-custom-nodes.sh verify_comfy_nodes.py /opt/runner/
RUN bash /opt/runner/install-custom-nodes.sh \
    && pip install --no-cache-dir runpod==1.9.1 websocket-client==1.9.0 \
    && pip check \
    && python -c 'import torch; assert torch.version.cuda == "13.0", torch.version.cuda' \
    && cd /comfyui && PYTHONPATH=/comfyui timeout 180 python /opt/runner/verify_comfy_nodes.py --cpu

# Official worker-comfyui 5.10.0 startup, job lifecycle, and storage adapter.
ARG WORKER_REV=724802bf26597b12255dfa8a5bfb4e6fe86bbedd
RUN set -eu; upstream="https://raw.githubusercontent.com/runpod-workers/worker-comfyui/$WORKER_REV"; \
    curl --fail --silent --show-error --retry 3 "$upstream/handler.py" -o /worker_comfyui.py; \
    curl --fail --silent --show-error --retry 3 "$upstream/src/network_volume.py" -o /network_volume.py; \
    curl --fail --silent --show-error --retry 3 "$upstream/src/start.sh" -o /start.sh; \
    curl --fail --silent --show-error --retry 3 "$upstream/scripts/comfy-manager-set-mode.sh" -o /usr/local/bin/comfy-manager-set-mode; \
    curl --fail --silent --show-error --retry 3 "$upstream/LICENSE" -o /opt/runner/worker-comfyui.LICENSE; \
    chmod +x /start.sh /usr/local/bin/comfy-manager-set-mode

COPY handler.py /handler.py
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

WORKDIR /
CMD ["/start.sh"]
