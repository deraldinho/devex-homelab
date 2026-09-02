# UML — Simulação Docker na x99

Issue: #14

## Component Diagram

```mermaid
flowchart LR
    X[x99 / Docker Desktop]
    R[Working Copy\nDevEx-HomeLab]
    P[sim-pentium\nhomelab.control]
    C[sim-core\nhomelab.compute]
    PV[(pentium-state)]
    CV[(core-state)]

    X --> P
    X --> C
    R -. read-only .-> P
    R -. read-only .-> C
    P -->|TCP 19090| C
    P --> PV
    C --> CV
```

## Deployment Diagram

```mermaid
flowchart TB
    subgraph X99[x99]
      subgraph Docker[Docker Desktop / WSL2]
        NET[devex-homelab-sim-net]
        P[sim-pentium\nUbuntu 26.04\nUID 1000]
        C[sim-core\nUbuntu 26.04\nUID 1000]
        NET --- P
        NET --- C
      end
    end
```
## Certification Sequence

```mermaid
sequenceDiagram
    participant V as verify.sh
    participant D as Docker Compose
    participant P as sim-pentium
    participant C as sim-core

    V->>D: config + build
    V->>D: up --wait
    D->>C: start + healthcheck
    D->>P: start after Core healthy
    V->>C: validate role/mount/state
    V->>P: validate role/mount/state
    V->>P: probe sim-core:19090
    P->>C: TCP request
    C-->>P: DEVEX_SIM_CORE_OK
    V->>D: down -v --remove-orphans
    V->>D: assert zero leftovers
```

A simulação representa somente contratos lógicos; hardware e serviços de host permanecem fora deste deployment.