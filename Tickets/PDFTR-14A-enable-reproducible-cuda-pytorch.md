# PDFTR-14A — Enable reproducible CUDA PyTorch environment

## Summary

Unblock PDFTR-14 by making the PDFTranslate project environment reproducibly install a
CUDA-enabled PyTorch build on the supported Windows development environment.

This is a corrective infrastructure step inside the existing PDFTR-14 work.

**Do not create a separate long-lived feature branch for PDFTR-14A.**

Continue on the existing branch:

```text
codex/PDFTR-14-performance-memory-cuda-benchmark
```

starting from the current blocker commit:

```text
121332369cccfe8a35c0f0851468a198d588f5af
```

PDFTR-14A should be implemented as follow-up commits on that same branch. After the CUDA gate
passes, continue the original PDFTR-14 implementation on the same branch and merge the complete
PDFTR-14 result once.

Do not merge the blocker-only state into `master`.

## Background

PDFTR-14 correctly stopped at its mandatory CUDA gate.

Observed environment:

```text
GPU: NVIDIA GeForce RTX 4080
GPU VRAM: ~16 GB
NVIDIA driver: detected
Python: 3.12
torch: 2.13.0+cpu
torch.version.cuda: null
torch.cuda.is_available(): false
torch.cuda.device_count(): 0
```

The project currently declares:

```toml
torch>=2.7,<3
```

without pinning PyTorch to an accelerator-specific package index.

The active Windows environment therefore resolved a CPU-only PyTorch distribution.

The blocker is the project dependency resolution, not missing NVIDIA hardware.

## Goal

Make the CUDA-enabled PyTorch environment reproducible through the repository configuration and
`uv.lock`.

After a clean environment synchronization, the project must be able to execute real CUDA work on
the RTX 4080 without manual `pip install` commands or local-only modifications.

The result must be reproducible from the repository itself.

## Primary requirements

1. Select an official PyTorch CUDA build compatible with:
   - Windows;
   - Python 3.12;
   - the project's supported Torch version range;
   - the installed NVIDIA driver;
   - RTX 4080.

2. Configure `uv` so Windows resolves `torch` from the selected official PyTorch CUDA index.

3. Commit the dependency configuration and updated `uv.lock`.

4. Recreate/synchronize the project environment from the lockfile.

5. Prove that PyTorch sees and executes CUDA on the RTX 4080.

6. Preserve Linux CI compatibility.

7. After the CUDA gate passes, resume the original PDFTR-14 benchmark implementation on this same
   branch.

## Source of truth

Use only current official documentation when selecting the CUDA build/index:

- official PyTorch installation/download indexes;
- official `uv` PyTorch integration documentation.

Do not guess a CUDA index from memory.

Do not choose an index merely because its CUDA version matches the value printed by `nvidia-smi`.
The NVIDIA driver can support CUDA runtimes older than its maximum reported capability.

Verify the actual PyTorch wheel availability for Windows + Python 3.12.

## Preferred dependency design

Use project-level `uv` configuration rather than manual environment installation.

Preferred mechanism:

```toml
[tool.uv.sources]
torch = [
    { index = "<official-pytorch-cuda-index>", marker = "sys_platform == 'win32'" }
]

[[tool.uv.index]]
name = "<official-pytorch-cuda-index>"
url = "https://download.pytorch.org/whl/<verified-cuda-build>"
explicit = true
```

This is illustrative only.

Codex must replace the placeholders with a currently supported official PyTorch index verified
during implementation.

`explicit = true` is preferred so unrelated dependencies continue to resolve from the normal
package index.

If the project needs a different source policy for Linux CI, use environment markers so Windows
gets the CUDA wheel while Linux CI remains reproducible and does not require a GPU.

Do not force CUDA packages onto macOS or unsupported platforms.

## Important compatibility requirement

GitHub Actions currently runs on:

```text
ubuntu-latest
windows-latest
```

CI runners do not need a physical GPU.

Dependency resolution must therefore be designed so that normal CI can still:

```text
uv sync --frozen --all-groups
```

and run the complete model-free test suite without requiring CUDA hardware.

Installing a CUDA-capable Torch wheel does not mean tests should execute CUDA.

Normal tests must remain GPU-independent unless explicitly marked as local/integration benchmarks.

## Do not use this as the final solution

Do not solve PDFTR-14A only by running commands such as:

```powershell
uv pip install torch --torch-backend=auto
pip install torch --index-url ...
```

Such commands may be used temporarily for investigation, but they are not an acceptable final
project configuration because they do not by themselves make `uv.lock` reproducible.

Likewise, do not depend on a developer-specific environment variable such as:

```text
UV_TORCH_BACKEND=auto
```

for the normal project setup.

The repository configuration must describe the intended dependency source.

## Investigation

Before changing dependencies:

1. Confirm the current branch and HEAD:

   ```text
   codex/PDFTR-14-performance-memory-cuda-benchmark
   1213323...
   ```

2. Confirm the working tree is clean.

3. Read:
   - `pyproject.toml`;
   - `uv.lock`;
   - `scripts/bootstrap.ps1`;
   - GitHub Actions workflow;
   - NLLB backend;
   - PDFTR-14 blocker report;
   - `AGENTS.md`;
   - `.codex/PRE_TICKET_WORKFLOW.md`.

4. Inspect current official PyTorch wheel indexes.

5. Determine which CUDA build is currently appropriate for:
   - Windows;
   - CPython 3.12;
   - Torch version selected by the project.

6. Record why that build was chosen.

7. Confirm the selected wheel exists before modifying the lockfile.

## Dependency policy decision

Prefer the smallest dependency change.

Do not add `torchvision` or `torchaudio`; PDFTranslate does not currently need them.

Do not install the full NVIDIA CUDA Toolkit merely to make PyTorch CUDA wheels work unless official
PyTorch requirements demonstrate it is necessary.

PyTorch CUDA wheels normally carry the runtime components they require; the system NVIDIA driver
is the critical external dependency.

Do not change the application's Python version.

Do not change the NLLB model.

## Lockfile requirements

After updating `pyproject.toml`:

```powershell
uv lock
```

Then verify the lock contains the expected CUDA-enabled Windows Torch distribution/source.

The lockfile must not continue resolving the Windows environment to:

```text
torch ... +cpu
```

when installed according to the new project policy.

Record:

- selected Torch version;
- selected CUDA wheel/index;
- relevant platform marker;
- relevant lockfile source.

## Clean-environment reproducibility test

A successful test against the already-mutated `.venv` is insufficient.

Prove reproducibility from project metadata.

Preferred validation:

1. record the current environment if needed;
2. remove/recreate `.venv` or otherwise use a clean uv-managed environment;
3. execute:

   ```powershell
   uv sync --frozen --all-groups
   ```

4. then execute the CUDA gate through:

   ```powershell
   uv run python ...
   ```

Do not repair `.venv` manually after `uv sync`.

If deleting `.venv` is unsafe in the current workflow, use an equivalent clean reproducibility
procedure and document it precisely.

## Mandatory CUDA gate

The following must all pass in the `uv` project environment.

### Metadata

Record:

```python
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.device_count())
print(torch.cuda.get_device_name(0))
print(torch.cuda.get_device_capability(0))
```

Acceptance:

```text
torch.cuda.is_available() == True
torch.cuda.device_count() >= 1
effective GPU == NVIDIA GeForce RTX 4080
torch.version.cuda != None
```

### Real allocation

Execute a real GPU allocation:

```python
x = torch.randn((2048, 2048), device="cuda")
```

### Real computation

Execute GPU matrix multiplication:

```python
y = x @ x
```

### Synchronization

Execute:

```python
torch.cuda.synchronize()
```

### Result transfer

Transfer a small result back to CPU and validate it is finite.

For example:

```python
result = y[0, 0].item()
```

Verify no CUDA exception occurred.

### Memory counters

Verify these calls work:

```python
torch.cuda.reset_peak_memory_stats()
torch.cuda.memory_allocated()
torch.cuda.memory_reserved()
torch.cuda.max_memory_allocated()
torch.cuda.max_memory_reserved()
```

This is required because PDFTR-14 depends on these counters.

## NLLB CUDA smoke test

After the raw PyTorch gate passes, run a small production NLLB CUDA smoke test using the existing
local model cache.

Requirements:

- strict offline mode if the model is already cached;
- `device=cuda`;
- one or a few short EN → RU sentences;
- no CPU fallback;
- actual effective device reported as CUDA;
- non-empty Russian output;
- model load succeeds;
- inference succeeds.

Do not run the full PDFTR-14 benchmark yet if the smoke test fails.

A raw tensor CUDA success is not sufficient if `NllbTranslator` cannot load/run on CUDA.

## CPU behavior

CUDA enablement must not break explicit CPU mode.

After installing the CUDA-capable wheel, verify:

```text
--device cpu
```

still constructs and runs NLLB on CPU.

A CUDA-capable PyTorch wheel must support CPU execution too.

Do not maintain two different `.venv` environments merely for CPU vs CUDA benchmarking unless
technically required and explicitly justified.

PDFTR-14 must compare CPU and CUDA using the same project dependency state wherever possible.

## CUDA fallback safety

For this gate, an explicit:

```text
device=cuda
```

must never silently run on CPU.

Verify the production translator reports:

```text
effective_device = cuda
```

If it reports `cpu`, treat the gate as failed.

`device=auto` behavior is not sufficient proof.

## CI validation

After changing dependency resolution:

1. run local focused tests;
2. run full:

   ```powershell
   .\scripts\check.ps1
   ```

3. push the same PDFTR-14 branch;
4. verify GitHub Actions on both:
   - Windows;
   - Ubuntu.

The CI runners do not need to pass the local CUDA hardware gate.

They only need to prove that dependency synchronization and normal model-free tests remain valid.

Do not add a CI CUDA benchmark requiring GPU hardware.

## Graphify / CRG

This is primarily an environment/dependency correction.

Use the repository workflow to determine the required level.

At minimum source-verify dependency impacts on:

```text
pyproject.toml
uv.lock
bootstrap/setup
CI
NllbTranslator
PDFTR-14 benchmark assumptions
```

Do not perform unrelated production refactoring.

## Documentation

Update the PDFTR-14 implementation plan/report rather than presenting PDFTR-14A as a separate
finished product.

Add a clearly labeled section:

```text
PDFTR-14A — CUDA environment unblock
```

Record:

- original blocker;
- selected official PyTorch CUDA index;
- selected Torch build;
- why it was selected;
- lockfile change;
- clean `uv sync` result;
- raw CUDA gate;
- NLLB CUDA smoke test;
- CPU smoke test;
- CI result.

Update README only if normal developer setup instructions genuinely need to change.

Update CHANGELOG if repository policy requires dependency/environment corrections to be listed.

## Git strategy

**Use the existing PDFTR-14 branch.**

Required branch:

```text
codex/PDFTR-14-performance-memory-cuda-benchmark
```

Required starting point:

```text
121332369cccfe8a35c0f0851468a198d588f5af
```

Do not create:

```text
codex/PDFTR-14A-...
```

Do not create a separate PR for PDFTR-14A.

Changes need normal Git commits so they can be pushed, reviewed and eventually merged. The
important constraint is that those commits stay on the existing PDFTR-14 branch.

Desired history:

```text
master
  \
   PDFTR-14 blocker commit 1213323
       ↓
   PDFTR-14A CUDA dependency fix
       ↓
   PDFTR-14 implementation
       ↓
   PDFTR-14 review/fixes
       ↓
   one final PR → master
```

Do not merge the blocker commit separately.

## Resume PDFTR-14 automatically

Once all PDFTR-14A acceptance criteria are satisfied, do not stop and wait for a new ticket.

Continue the existing PDFTR-14 implementation immediately on the same branch.

Run the original PDFTR-14 workflow:

```text
Graphify/CRG preflight
→ benchmark implementation
→ synthetic benchmark
→ real CPU NLLB benchmark
→ real CUDA NLLB benchmark
→ batch-size matrix
→ RAM/VRAM measurement
→ full validation
→ review
→ PR
```

The final implementation report must contain both:

```text
CUDA environment unblock evidence
```

and:

```text
completed PDFTR-14 performance benchmark evidence
```

## Acceptance criteria — PDFTR-14A

- [ ] Work continues on the existing PDFTR-14 branch.
- [ ] No separate PDFTR-14A branch is created.
- [ ] Official PyTorch documentation/index is used.
- [ ] Appropriate Windows + Python 3.12 CUDA wheel is verified.
- [ ] `pyproject.toml` reproducibly selects the intended PyTorch source.
- [ ] `uv.lock` is updated.
- [ ] Clean `uv sync --frozen --all-groups` succeeds.
- [ ] Installed Torch is CUDA-enabled.
- [ ] `torch.version.cuda` is non-null.
- [ ] `torch.cuda.is_available()` is true.
- [ ] RTX 4080 is visible through PyTorch.
- [ ] CUDA allocation succeeds.
- [ ] CUDA matrix multiplication succeeds.
- [ ] CUDA synchronization succeeds.
- [ ] CUDA result transfer succeeds.
- [ ] CUDA peak-memory counters succeed.
- [ ] Production NLLB CUDA smoke test succeeds.
- [ ] Explicit CUDA mode remains CUDA; no silent CPU fallback.
- [ ] Explicit CPU NLLB smoke test still succeeds.
- [ ] Local full quality gate succeeds after dependency change.
- [ ] Windows GitHub Actions succeeds.
- [ ] Ubuntu GitHub Actions succeeds.
- [ ] No CUDA hardware requirement is added to CI.
- [ ] PDFTR-14 blocker report is updated with successful unblock evidence.
- [ ] Original PDFTR-14 work resumes on the same branch.

## Failure policy

If an official compatible CUDA-enabled PyTorch wheel cannot be locked for the supported project
configuration, do not improvise with an unsupported binary.

Record:

- indexes checked;
- versions checked;
- exact resolver/install error;
- official compatibility information;
- next required dependency-policy decision.

If clean `uv sync` produces CPU-only Torch again, PDFTR-14A fails.

If raw CUDA works but production NLLB fails on CUDA, PDFTR-14A is not complete.

If local CUDA succeeds but normal Windows/Linux CI dependency synchronization breaks, PDFTR-14A is
not complete.

## Completion evidence

When the CUDA environment is fixed, append the following to the existing PDFTR-14 implementation
report:

```markdown
## PDFTR-14A — CUDA environment unblock

### Original blocker
- Torch:
- torch.version.cuda:
- CUDA available:
- GPU visibility:

### Selected dependency
- Official index:
- Torch version:
- CUDA wheel/runtime:
- Platform marker:
- Reason for selection:

### Reproducibility
- Clean environment procedure:
- uv sync command:
- uv.lock verification:
- Installed torch:

### CUDA gate
- torch.cuda.is_available:
- device count:
- GPU name:
- capability:
- allocation:
- matmul:
- synchronize:
- result transfer:
- peak allocated:
- peak reserved:

### NLLB smoke
- model:
- offline:
- requested device:
- effective device:
- translation result:
- CPU smoke result:

### CI
- Local check.ps1:
- Windows job:
- Ubuntu job:

### Status
- CUDA gate: PASS / FAIL
- PDFTR-14 resumed: YES / NO
```

## Final instruction

Do not treat PDFTR-14A as the final deliverable.

Its purpose is to remove the environment blocker and immediately enable completion of PDFTR-14 on
the same branch.

Only the final completed PDFTR-14 branch should be proposed for merge into `master`.
