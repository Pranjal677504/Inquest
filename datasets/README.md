# Frozen incident sets

The files in [`smoke-v1/`](smoke-v1/manifest.json) are the canonical inputs for initial development and evaluation. Load these files rather than regenerating cases from seeds: generator output is not guaranteed to remain identical across Python versions or generator revisions.

## Suite: `inquest-smoke-v1`

120 synthetic incidents, approximately 10 MB of uncompressed JSONL. Every case includes eight services and 120 minutes of metrics, with logs, change events, health, sampled traces, and construction labels. Each line is one complete incident bundle.

| Split | Easy | Medium | Hard | Intended use |
|---|---|---|---|---|
| Development | [8 cases](smoke-v1/dev-easy.jsonl) | [8 cases](smoke-v1/dev-medium.jsonl) | [8 cases](smoke-v1/dev-hard.jsonl) | Initial debugging and smoke checks |
| Test | [16 cases](smoke-v1/test-easy.jsonl) | [16 cases](smoke-v1/test-medium.jsonl) | [16 cases](smoke-v1/test-hard.jsonl) | Small initial policy comparisons |
| Alternate wording (`ood`) | [16 cases](smoke-v1/ood-easy.jsonl) | [16 cases](smoke-v1/ood-medium.jsonl) | [16 cases](smoke-v1/ood-hard.jsonl) | Initial robustness checks under paraphrased signal logs |

Each development set contains one case per fault category; each test/alternate-wording set contains two. These sets do not exhaust the feasible service/fault pairs. The development set is too small for a reliable likelihood fit; larger versioned training and evaluation sets will accompany later evaluation work.

## Verify and load

After installing the package from the checkout, run:

```bash
python examples/load_frozen_set.py
```

Or load a named set through Python:

```python
from inquest.frozen import load_frozen_set

cases = load_frozen_set("datasets/smoke-v1", "test-hard")
assert len(cases) == 16
```

The loader checks the manifest's SHA-256, then the selected data file's SHA-256, byte count, record count, identities, order, split, and difficulty. It validates every scenario through the JSON loader before returning the set. It does not call the generator. These checks were verified on Python 3.14; interpreter compatibility remains subject to the planned test matrix.

To verify all published files on macOS or Linux with `shasum` installed:

```bash
cd datasets/smoke-v1
shasum -a 256 -c SHA256SUMS
```

The [checksum catalog](smoke-v1/SHA256SUMS) covers all nine JSONL files and the [manifest](smoke-v1/manifest.json). The manifest records generation runtime, generator Git revision, source-file hashes, byte counts, ordered case IDs, seed ranges, and fault counts.

Manifest SHA-256 for this version:

```text
1564fdcdb8590d375b95312544a1d85885e5daec476cc76b47cee8ab5a5e2003
```

Checksums detect changed bytes; they are not signatures. Pin the repository commit containing this suite and retain its checksum catalog when recording an experiment. JSONL files use UTF-8 and LF line endings, enforced by the repository's text attributes. Data lives in the checkout and is not bundled into the Python distribution.

## Evaluation boundary

- Bundles contain `root_service`, `fault_type`, the expected fix, and other construction metadata. They are evaluator inputs, not agent observations.
- Seeds and scenario IDs can reveal the generator's fault-selection rule. The implemented [tool environment](../docs/TOOLS.md) excludes them, labels, and gold metadata from observations; a future agent harness must also prevent direct access to construction bundles.
- Tune on development cases; use test and alternate-wording cases only for assessment. These public cases are not a secret held-out dataset.
- The `ood` split changes signal-log wording within the same authored generator. It is not independent operational data or a held-out topology.
- No agent scores are included. One or two examples per category are smoke coverage, not strong evidence of model performance.

## Version policy

Published suite files and their manifest are immutable evaluation inputs. Changes to incident contents, construction rules, or case selection require a new suite directory and version. Experiment records should include suite ID, set name, data-file SHA-256, and repository revision. Seeds document provenance; reproducing an evaluation means loading the recorded file bytes.

The manifest format is version 1. Individual scenario records do not yet have schema migrations. Future readers must retain compatibility or provide an explicit migration into a separately versioned suite.
