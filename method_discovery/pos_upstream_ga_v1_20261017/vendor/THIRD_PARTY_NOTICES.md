# Third-party notices

The root [MIT License](LICENSE) applies to PoS-owned code and documentation. Included benchmark components retain their original notices and licenses; benchmark data access and redistribution terms are separate from the PoS license.

## LOCA-Bench and GEM

- Upstream: [hkust-nlp/LOCA-bench](https://github.com/hkust-nlp/LOCA-bench).
- Included source revision: `8b6fac49d9edd92922593e703b74ea255357c3ec`.
- Location: `benchmarks/LOCA-Bench/`.
- LOCA-bench's MIT license and copyright notice are retained in [LICENSE](benchmarks/LOCA-Bench/LICENSE).
- GEM source files retain their Apache-2.0 headers, including the AxonRL Team notices. The Apache license text is retained in [LICENSE-APACHE-2.0](benchmarks/LOCA-Bench/LICENSE-APACHE-2.0).

Local adaptations use the active Python interpreter for MCP servers and Python execution, select installed terminal/PDF executables, and make one helper's f-string quoting compatible with Python 3.11. Task generation and evaluator logic are unchanged by these adaptations. See the [included benchmark README](benchmarks/LOCA-Bench/README.md).

## ALFWorld

[ALFWorld](https://github.com/alfworld/alfworld) is installed as a dependency. The preparation script obtains the valid-unseen text games from upstream release archives and copies the matching logic from the installed package. Raw games are not included in the Git repository. ALFWorld, TextWorld, and their downloaded assets retain upstream terms and notices.

## RCA-100

The adapter prepares observation files from the benchmark's [public RCA100 v1.1 data endpoint](https://aiops-benchmark.oss-cn-hongkong.aliyuncs.com/rca/rca100/v1.1/). Evaluator labels and taxonomy are included under `benchmarks/RCA100/answer_key/`; the existing release's [data setup notes](docs/data.md#rca100) record confirmed redistribution authorization for those labels. Original third-party content is retained. This notice does not assign the PoS MIT license to benchmark data.

The observation dataset is downloaded separately, and evaluator labels are kept outside the agent-visible tools. Case order is specified by `benchmarks/RCA100/manifest.txt`.

## ClinDiag

- Upstream: [geteff1/ClinDiag](https://github.com/geteff1/ClinDiag).
- The official data archive must be obtained under its upstream terms; it is not included here.
- The preparation scripts create the fixed 604-case subset and separate observations from final-diagnosis labels.
- The Emergency subset is excluded from the manuscript evaluation because it was unavailable under the study's data-access setting.

See [ClinDiag data setup](docs/data.md#clindiag) for the retained rare cases, deterministic challenging-case sample, and manifest checks.

## Installed dependencies

Python packages, Node/MCP tools, and other runtime dependencies retain their respective upstream licenses. Installing them does not change their license terms. Core and benchmark-specific dependency lists are in `requirements.txt` and `requirements/`.
