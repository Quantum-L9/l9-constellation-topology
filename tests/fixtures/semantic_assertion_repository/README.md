> **DEPRECATED.** Do not use this repository as an org bootstrap template.
>
> **SSOT replacement:** [Quantum-L9/l9-assertion-successor](https://github.com/Quantum-L9/l9-assertion-successor)
>
> This fixture retains a FastAPI/engine layout and Poetry packaging on purpose.

# Semantic Assertion Fixture

> The reference implementation for repository-model assertion coverage.

This tree exists to be *observed*. It is the input a real
`l9-meta-injector` run reads to emit the checked-in repository-model 1.1.0
packet under `tests/fixtures/repository_model_packets/l9-assertion-sample/`.
Nothing here is imported or executed by the topology compiler: the compiler's
only ingress is the packet, never this source.

Each file below is shaped to evidence one part of the predicate registry, so a
change in what the producer extracts shows up as a fixture diff rather than as
a silently narrower test.
