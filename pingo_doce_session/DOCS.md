# Pingo Doce — Sessão Persistente

Este add-on mantém o site do Pingo Doce aberto num Chromium persistente.

## Utilização

1. Inicie o add-on.
2. Abra a interface Web.
3. Faça login no Pingo Doce.
4. Instale a custom integration **Pingo Doce Session** incluída no mesmo repositório.
5. Em **Definições → Dispositivos e serviços**, adicione **Pingo Doce Session**.

A integração lê automaticamente os dados em `/config/pingo_doce_session`. Não é necessário colar cookies.

## Cookie para outra integração

A custom integration disponibiliza:

- botão **Copiar cookie**;
- ação `pingo_doce_session.get_cookie`, que devolve a cookie completa e os cookies em JSON.

A cookie é mantida fora dos estados e do histórico do Home Assistant.
