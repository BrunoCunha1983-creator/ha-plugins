# Changelog

## 2.0.1

- Corrige o acesso ao noVNC usando diretamente a porta 7900, sem depender do Ingress.
- Mantém o `slug` histórico `pingo_doce_session` para atualizar a instalação existente e preservar os dados em `/data`.
- Adiciona validação de arranque para Xvfb, x11vnc e websockify.
- Mostra nos registos a causa concreta quando um dos serviços gráficos falha.

## 2.0.0

- Unifica a sessão persistente com a integração Pingo Doce Plus.
- O login é feito apenas na primeira utilização e o perfil Chromium fica em `/data`.
- Recupera automaticamente a sessão depois de reinícios do Home Assistant, Supervisor ou servidor.
- Recolhe saldo, pontos, encomenda atual, progresso, histórico e cupões quando disponíveis.
- Remove a necessidade de copiar cookies manualmente.
