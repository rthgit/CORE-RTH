"""
Build SOUL Golden config and SOUL<->SIGMA bridge config from real checkpoints.

Outputs:
- storage/models/soul_golden_config.json
- storage/models/soul_sigma_bridge.json
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Dict, Iterable, Optional, Tuple


DTYPE_BYTES = {
    "torch.float16": 2,
    "torch.bfloat16": 2,
    "torch.float32": 4,
    "torch.float64": 8,
    "torch.int8": 1,
    "torch.uint8": 1,
    "torch.int16": 2,
    "torch.int32": 4,
    "torch.int64": 8,
    "torch.bool": 1,
}


def _sha256_head(path: Path, head_bytes: int = 8 * 1024 * 1024) -> str:
    import hashlib as _hashlib

    h = _hashlib.sha256()
    with path.open("rb") as f:
        chunk = f.read(head_bytes)
        h.update(chunk)
    return h.hexdigest()


def _load_state_dict(pt_path: Path) -> Tuple[Dict[str, Any], str]:
    import torch

    obj = torch.load(pt_path, map_location="meta")
    if isinstance(obj, dict):
        for key in ("state_dict", "model_state_dict", "model"):
            nested = obj.get(key)
            if isinstance(nested, dict) and nested:
                return nested, key
        if obj and all(hasattr(v, "shape") for v in obj.values()):
            return obj, "root"
    raise RuntimeError("Unsupported checkpoint format: expected a tensor state dict")


def _pick_tensor(state_dict: Dict[str, Any], names: Iterable[str]) -> Optional[Any]:
    for name in names:
        t = state_dict.get(name)
        if t is not None and hasattr(t, "shape"):
            return t
    return None


def _human_gb(nbytes: int) -> float:
    return round(float(nbytes) / (1024 ** 3), 3)


def _infer_soul_config(pt_path: Path) -> Dict[str, Any]:
    state_dict, source_key = _load_state_dict(pt_path)
    keys = list(state_dict.keys())

    layer_ids = []
    for k in keys:
        m = re.match(r"h\.(\d+)\.", k)
        if m:
            layer_ids.append(int(m.group(1)))
    n_layer = (max(layer_ids) + 1) if layer_ids else None

    wte = _pick_tensor(state_dict, ["wte.weight", "transformer.wte.weight", "embed.weight"])
    wpe = _pick_tensor(state_dict, ["wpe.weight", "transformer.wpe.weight"])
    lm_head = _pick_tensor(state_dict, ["lm_head.weight", "head.weight"])

    vocab_size = int(wte.shape[0]) if wte is not None else None
    n_embd = int(wte.shape[1]) if (wte is not None and len(wte.shape) >= 2) else None
    n_positions = int(wpe.shape[0]) if wpe is not None else None

    dtype_counts: Counter[str] = Counter()
    total_numel = 0
    total_bytes_est = 0
    largest = []
    for name, tensor in state_dict.items():
        if not hasattr(tensor, "numel"):
            continue
        n = int(tensor.numel())
        total_numel += n
        dtype_name = str(getattr(tensor, "dtype", "unknown"))
        dtype_counts[dtype_name] += 1
        bytes_per_elem = DTYPE_BYTES.get(dtype_name, 0)
        total_bytes_est += n * bytes_per_elem
        largest.append(
            {
                "name": name,
                "shape": list(getattr(tensor, "shape", [])),
                "dtype": dtype_name,
                "numel": n,
                "bytes_est": n * bytes_per_elem,
            }
        )
    largest.sort(key=lambda x: x["numel"], reverse=True)

    has_echo_qk = any(".attn.c_qk.weight" in k for k in keys)
    has_mirror_bias_out = any(".mlp.bias_out" in k for k in keys)
    has_standard_attn = any(".attn.c_attn.weight" in k for k in keys)

    model_signature = "|".join(sorted(keys[:200]))
    signature_sha = hashlib.sha256(model_signature.encode("utf-8")).hexdigest()

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "checkpoint": {
            "path": str(pt_path),
            "exists": pt_path.exists(),
            "size_bytes": pt_path.stat().st_size if pt_path.exists() else None,
            "size_gb": _human_gb(pt_path.stat().st_size) if pt_path.exists() else None,
            "sha256_head_8mb": _sha256_head(pt_path) if pt_path.exists() else None,
        },
        "loader": {
            "source_key": source_key,
            "tensor_count": len(state_dict),
        },
        "architecture": {
            "family": "echo_gpt2_mirror" if has_echo_qk and has_mirror_bias_out else "gpt_like_custom",
            "attention_mode": "shared_qk" if has_echo_qk else ("standard_c_attn" if has_standard_attn else "unknown"),
            "mlp_mode": "mirror_bias_out" if has_mirror_bias_out else "standard_or_unknown",
            "n_layer": n_layer,
            "n_embd": n_embd,
            "vocab_size": vocab_size,
            "n_positions": n_positions,
            "weight_tying_lm_head": bool(wte is not None and lm_head is not None and tuple(wte.shape) == tuple(lm_head.shape)),
            "required_custom_modules": [
                "EchoAttention(c_qk + c_v + c_proj)" if has_echo_qk else "StandardAttention",
                "MirrorFFN(bias_out + mirrored up-proj)" if has_mirror_bias_out else "StandardFFN",
            ],
        },
        "params": {
            "total_numel": total_numel,
            "total_numel_billion": round(total_numel / 1_000_000_000, 3),
            "dtype_counts": dict(dtype_counts),
            "weights_bytes_est": total_bytes_est,
            "weights_gb_est": _human_gb(total_bytes_est),
        },
        "largest_tensors_top12": largest[:12],
        "state_signature_sha256": signature_sha,
        "inference_recommendation": {
            "device_preference": ["cuda", "cpu"],
            "dtype_runtime": "float16_or_bfloat16",
            "note": "Checkpoint uses custom keys (c_qk/bias_out): load with custom Echo/Mirror class, not vanilla GPT2LMHeadModel.",
        },
    }


def _infer_sigma_info(sigma_dir: Path) -> Dict[str, Any]:
    cfg_path = sigma_dir / "config.json"
    cfg = {}
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}

    required = [
        "config.json",
        "tokenizer_config.json",
        "vocab.json",
        "merges.txt",
        "special_tokens_map.json",
        "generation_config.json",
    ]
    found = {name: (sigma_dir / name).exists() for name in required}
    model_candidates = {
        "model.safetensors": (sigma_dir / "model.safetensors").exists(),
        "pytorch_model.bin": (sigma_dir / "pytorch_model.bin").exists(),
    }

    return {
        "path": str(sigma_dir),
        "exists": sigma_dir.exists(),
        "config": cfg,
        "required_files": found,
        "model_files": model_candidates,
    }


def _build_bridge(soul_cfg: Dict[str, Any], sigma_info: Dict[str, Any]) -> Dict[str, Any]:
    soul_arch = soul_cfg.get("architecture", {})
    soul_vocab = int(soul_arch.get("vocab_size") or 0)
    soul_pos = int(soul_arch.get("n_positions") or 0)

    sigma_cfg = sigma_info.get("config", {}) if isinstance(sigma_info, dict) else {}
    sigma_vocab = int(sigma_cfg.get("vocab_size") or 0)
    sigma_pos = int(sigma_cfg.get("n_positions") or sigma_cfg.get("n_ctx") or 0)

    target_vocab = max(soul_vocab, sigma_vocab)
    target_pos = max(soul_pos, sigma_pos)

    resize_soul = max(0, target_vocab - soul_vocab)
    resize_sigma = max(0, target_vocab - sigma_vocab)

    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "bridge_name": "soul_sigma_council",
        "soul": {
            "checkpoint_path": soul_cfg.get("checkpoint", {}).get("path"),
            "family": soul_arch.get("family"),
            "n_layer": soul_arch.get("n_layer"),
            "n_embd": soul_arch.get("n_embd"),
            "vocab_size": soul_vocab,
            "n_positions": soul_pos,
        },
        "sigma": {
            "path": sigma_info.get("path"),
            "model_type": sigma_cfg.get("model_type"),
            "architectures": sigma_cfg.get("architectures"),
            "n_layer": sigma_cfg.get("n_layer"),
            "n_embd": sigma_cfg.get("n_embd"),
            "vocab_size": sigma_vocab,
            "n_positions": sigma_pos,
            "model_file_available": any(bool(x) for x in sigma_info.get("model_files", {}).values()),
        },
        "tokenizer_bridge": {
            "source": "sigma",
            "required_files_present": sigma_info.get("required_files", {}),
            "target_vocab_size": target_vocab,
            "target_n_positions": target_pos,
            "resize_plan": {
                "soul_additional_tokens": resize_soul,
                "sigma_additional_tokens": resize_sigma,
            },
        },
        "prompt_bridge": {
            "primary_template": "<USER>: {prompt}\\n<ASSISTANT>:",
            "fallback_template": "User: {prompt}\\nAssistant:",
        },
        "routing_policy": {
            "mode": "weighted_council",
            "weights": {"soul": 0.65, "sigma": 0.35},
            "switch_hints": {
                "soul_preferred": ["reasoning", "structured_tasks", "code_planning"],
                "sigma_preferred": ["style_transfer", "creative_language", "short_response_polish"],
            },
        },
        "compatibility": {
            "custom_loader_required_for_soul": True,
            "notes": [
                "SOUL checkpoint uses custom attention/MLP keys (c_qk, bias_out).",
                "Use SIGMA tokenizer as shared lexical layer, then resize embeddings where needed.",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SOUL Golden + SOUL/SIGMA bridge configs")
    parser.add_argument("--soul", default=r"D:\CORE RTH\soul_final_golden.pt", help="Path to SOUL golden .pt checkpoint")
    parser.add_argument("--sigma-dir", default=r"C:\Users\PC\Desktop\Biome\piccolo tridente\Stigmav2", help="Path to SIGMA directory")
    parser.add_argument("--out-dir", default=r"storage\models", help="Output directory for generated configs")
    args = parser.parse_args()

    soul_path = Path(args.soul)
    sigma_dir = Path(args.sigma_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not soul_path.exists():
        raise FileNotFoundError(f"SOUL checkpoint not found: {soul_path}")

    soul_cfg = _infer_soul_config(soul_path)
    sigma_info = _infer_sigma_info(sigma_dir)
    bridge_cfg = _build_bridge(soul_cfg, sigma_info)

    soul_out = out_dir / "soul_golden_config.json"
    bridge_out = out_dir / "soul_sigma_bridge.json"
    try:
        soul_out.write_text(json.dumps(soul_cfg, indent=2), encoding="utf-8")
        bridge_out.write_text(json.dumps(bridge_cfg, indent=2), encoding="utf-8")
    except PermissionError:
        # Fallback for restricted environments.
        import tempfile

        fb = Path(tempfile.gettempdir()) / "rth_core" / "models"
        fb.mkdir(parents=True, exist_ok=True)
        soul_out = fb / "soul_golden_config.json"
        bridge_out = fb / "soul_sigma_bridge.json"
        soul_out.write_text(json.dumps(soul_cfg, indent=2), encoding="utf-8")
        bridge_out.write_text(json.dumps(bridge_cfg, indent=2), encoding="utf-8")

    print(f"written: {soul_out}")
    print(f"written: {bridge_out}")
    print(
        "summary:",
        json.dumps(
            {
                "soul_family": soul_cfg.get("architecture", {}).get("family"),
                "soul_numel_billion": soul_cfg.get("params", {}).get("total_numel_billion"),
                "soul_vocab": soul_cfg.get("architecture", {}).get("vocab_size"),
                "sigma_vocab": bridge_cfg.get("sigma", {}).get("vocab_size"),
                "target_vocab": bridge_cfg.get("tokenizer_bridge", {}).get("target_vocab_size"),
            },
            ensure_ascii=True,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
