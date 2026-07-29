# Arquitetura

```text
Pingo Doce
    │
    ▼
Chromium persistente no add-on
    │  perfil, cookies e armazenamento em /data
    ▼
/homeassistant/pingo_doce_plus/state.json
    │
    ▼
Custom integration Pingo Doce Plus
    │
    ├─ sensores e binary_sensors
    ├─ botões e serviços
    └─ eventos de alteração
```

A integração nunca recebe credenciais nem exige que o utilizador copie cookies. A comunicação local usa ficheiros atómicos na configuração do Home Assistant.
