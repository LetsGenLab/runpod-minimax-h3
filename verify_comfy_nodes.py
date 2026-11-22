"""Check that the image registers the built-in nodes for H3 inference."""

import main
import nodes


REQUIRED_NODES = {
    "BasicGuider", "BasicScheduler", "BlockSparseAttention", "CLIPLoader",
    "ComfyMathExpression", "CreateVideo", "KSamplerSelect", "LoadAudio",
    "LoadImage", "LoraLoaderModelOnly", "MiniMaxH3ReferenceToVideo",
    "MiniMaxH3SigmaShift", "ModelAttentionBackend", "PrimitiveFloat",
    "PrimitiveStringMultiline", "RandomNoise", "ResolutionSelector",
    "SamplerCustomAdvanced", "SaveVideo", "UNETLoader", "VAEDecode",
    "VAEDecodeAudio", "VAELoader",
}


if __name__ == "__main__":
    loop, _, _ = main.start_comfyui()
    loop.close()
    missing = REQUIRED_NODES.difference(nodes.NODE_CLASS_MAPPINGS)
    if missing:
        raise SystemExit(f"Missing ComfyUI node registrations: {', '.join(sorted(missing))}")
    print(f"Verified {len(REQUIRED_NODES)} ComfyUI node registrations")
