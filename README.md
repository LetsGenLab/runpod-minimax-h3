# Runpod ComfyUI Worker

A Runpod Queue Serverless worker for ComfyUI API workflows. It runs ComfyUI v0.46.2 on CUDA 13.0, uses the upstream `worker-comfyui` job handler, and supports native image, video, and audio output. Model weights are provisioned separately on a Runpod Global Volume. Callers supply their own workflows and select models by filename. [ComfyUI v0.46.2](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.46.2) · [Upstream worker](https://github.com/runpod-workers/worker-comfyui/tree/5.10.0)

## Deploy from GitHub

1. Push the repository to GitHub. In Runpod **Settings → Connections → GitHub**, grant access to that repository.
2. In **Serverless → New Endpoint**, choose **Deploy from a GitHub repository**, select your branch, and use `Dockerfile` at the repository root.
3. Select **Queue** and **GPU**. In **Advanced settings → Global volume**, select the volume containing your models. You can attach the volume later while the endpoint is idle.
4. Deploy and check the endpoint's **Builds** tab. The build starts ComfyUI on CPU and checks that the built-in H3 nodes register. GPU execution still needs a runtime test. For subsequent deployments, create a GitHub release from the commit you want Runpod to build.

| Endpoint setting | Suggested starting value |
| --- | --- |
| GPU | One 96 GB Blackwell GPU |
| Minimum CUDA version | 13.0 |
| Container disk | 50 GB |
| Active workers | 0 |
| Max workers | 1 |
| Execution timeout | 1,800 seconds |
| Global Volume | Your model volume, mounted at `/runpod-volume` |

The `.runpod/hub.json` and `.runpod/tests.json` in the huchukato repository are metadata and tests for **Runpod Hub publication**. GitHub deployment uses the Dockerfile and the endpoint settings you select. If the managed build hits its 30-minute Docker build limit, build a `linux/amd64` image on a Linux builder, push it to a registry, and deploy from the image. [GitHub deployment](https://docs.runpod.io/serverless/workers/github-integration) · [Hub configuration](https://docs.runpod.io/hub/publishing-guide) · [Global Volume attachment](https://docs.runpod.io/storage/globalvolume/globalvolume-serverless)

## Provision models on a Global Volume

Choose the model files your workflows need. Mount a Global Volume on a temporary Runpod Pod and download the files there. The Pod normally mounts a standalone Global Volume at `/workspace`, and the Serverless endpoint reads it at `/runpod-volume`. A CPU Pod can attach a Global Volume through the Runpod REST API using `mounts.global`. Use one provisioning Pod at a time. [Pod mount paths](https://docs.runpod.io/storage/globalvolume/globalvolume-pods#mount-paths) · [Runpod REST API](https://docs.runpod.io/api-reference-v2/pods/create-a-pod)

Check your account's remaining capacity and the Pod's temporary disk before downloading. The Runpod console lists the first 100 GB as free, with storage above that at $0.09/GB/month. Volume reads and writes are billed separately. Verify each download on the Pod's temporary disk before copying it into the volume. Terminate the provisioning Pod when done, and start fresh inference workers if they already mounted the volume before the update. [Global Volume billing and filesystem limits](https://docs.runpod.io/storage/globalvolume/overview)

### MiniMax H3 Ref2VA model profile

The optional [Ref2VA profile](profiles/minimax-h3-ref2va.json) pins the Singularity INT8 base, the lightx2v 4-step LoRA, the pruned Sol INT8 video VAE, and the audio VAE. The four files total **25.52 GB**. Docker excludes profiles and the provisioning script. To opt in, copy those two files to a temporary Pod with Python 3.9+, `curl`, and at least 22 GB free on its temporary disk. Run these commands after confirming `/workspace` is the mounted Global Volume.

```bash
# From the repository checkout. Only the script and JSON are transferred.
scp -P "$POD_SSH_PORT" populate_models.py profiles/minimax-h3-ref2va.json \
  "root@$POD_SSH_HOST:/tmp/"
```

```bash
# On the provisioning Pod.
python3 /tmp/populate_models.py --profile /tmp/minimax-h3-ref2va.json \
  --models-dir /workspace/models --staging-dir /tmp
```

Use `--only` with a profile's `target` value to provision a subset, or `--check` to verify existing files. The script verifies size and SHA-256 before copying each file. Matching files are reused and mismatched files are left in place for inspection.

Set `UNETLoader.unet_name` to `Minimax-h3_Singularity_ref2va_v2_pruned_int8.safetensors` and `LoraLoaderModelOnly.lora_name` to `minimax_h3_ref2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors`. A complete H3 graph also needs the compatible text encoder and VAEs referenced in its loaders. Keep those files on the volume under `models/text_encoders/` and `models/vae/`. [Base model](https://huggingface.co/WarmBloodAban/Minimax-h3_Singularity/blob/1259cf16cd0b655ba691a32fb46a409142762972/Minimax-h3_Singularity_ref2va_v2_pruned_int8.safetensors) · [Turbo LoRA](https://huggingface.co/lightx2v/Minimax-h3-Turbo/blob/c2bf13b837e33bd851b370285fc7db99482d2ab2/minimax_h3_ref2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors)

## Request an additional model

Open a repository issue with the Hugging Face repository and commit, the exact source path, where the file belongs under `models/`, and the workflow or loader that needs it. Include size, SHA-256, and access requirements when known.

A maintainer verifies the source and available capacity. For public files, use a separate profile and the same provisioning command, then select the new filenames in the API workflow. You can also use `hf download REPO FILE --revision COMMIT --local-dir STAGING_DIR`, verify the approved SHA-256, and copy the file to the appropriate category under the volume's `models/` directory. For gated files, authenticate the Hugging Face CLI on the provisioning Pod. Model additions take effect through the mounted volume and require no image rebuild when the runtime already supports the model. [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli)

### Hugging Face links and file browsing

Built-in ComfyUI model loaders use filenames from configured model directories. A Hugging Face URL belongs in the provisioning request. After the file is on the volume, select its filename in the workflow. ComfyUI Manager has separate model installation features and is optional for an interactive provisioning environment. [ComfyUI loader source](https://github.com/Comfy-Org/ComfyUI/blob/v0.46.2/nodes.py) · [ComfyUI Manager](https://github.com/Comfy-Org/ComfyUI-Manager)

For a visual file browser, you can use an authenticated JupyterLab or file browser on the temporary Pod. Keep its runtime and configuration on the Pod's local disk and point it at the mounted Global Volume for browsing or uploads. The Serverless worker keeps ComfyUI on `127.0.0.1:8188`. Global Volume does not expose an S3 API, so file transfers go through a Pod with the volume mounted. [Global Volume access](https://docs.runpod.io/storage/globalvolume/overview#access-your-files)

## Submit a workflow

Export your workflow in **API format** and send it under `input.workflow`. Model loaders should reference the filenames available on the worker. For input images, use `input.images` with `name` and base64 `image`, and reference those filenames in the corresponding nodes. Supply the completion callback as the top-level `webhook` field.

```bash
jq -n --slurpfile workflow workflow-api.json --arg webhook "$CALLBACK_URL" \
  '{input: {workflow: $workflow[0]}, webhook: $webhook}' |
  curl --fail-with-body -sS "https://api.runpod.ai/v2/$ENDPOINT_ID/run" \
    -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -H 'Content-Type: application/json' --data-binary @-
```

Record the returned job ID and handle completion webhooks idempotently. Saved files, including video, use the upstream `output.images` array. Each entry contains `filename`, `type`, and `data`. To verify the worker and webhook without loading model weights, submit [`examples/smoke.json`](examples/smoke.json) with your callback URL. Expect a 64×64 green PNG. This still starts a Runpod GPU worker. [Runpod webhook notifications](https://docs.runpod.io/serverless/endpoints/send-requests#webhook-notifications)

Output defaults to base64. For larger media, configure an existing S3-compatible output bucket with `BUCKET_NAME`, `BUCKET_ENDPOINT_URL`, `BUCKET_ACCESS_KEY_ID`, and `BUCKET_SECRET_ACCESS_KEY`. Set `BUCKET_REGION` if needed. It defaults to `us-east-1`, or use `auto` for Cloudflare R2. The callback returns presigned download URLs valid for one hour.

## Maintain custom nodes

The image loads the built-in ComfyUI nodes by default. For experiments that need a different ComfyUI version, custom nodes, or system dependencies, pin the changes in the Dockerfile or `custom-nodes.lock` and build a separate image tag. Test it on a separate endpoint and reuse the Global Volume when the model formats are compatible. Keep the Runpod API key and workflow submission access on a trusted server.
