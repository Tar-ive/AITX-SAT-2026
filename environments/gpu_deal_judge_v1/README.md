# GPU Deal Judge v1

Prime/Verifiers v1 taskset for measuring PC-purchase decisions across GPUs,
MacBooks, and RAM.

```bash
uv run --with verifiers --with ./environments/gpu_deal_judge_v1 \
  eval gpu-deal-judge-v1 -n 3 -r 1 --rich false -v
```

The full evaluation convention is 15 tasks with 3 rollouts per task.
