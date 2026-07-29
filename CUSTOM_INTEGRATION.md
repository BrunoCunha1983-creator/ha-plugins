# Pingo Doce Session — Custom Integration

Esta integração funciona em conjunto com o add-on `pingo_doce_session` versão 1.1.0 ou superior.

## Instalação manual

Copie:

```text
custom_components/pingo_doce_session
```

para:

```text
/config/custom_components/pingo_doce_session
```

Reinicie o Home Assistant e adicione **Pingo Doce Session** em **Definições → Dispositivos e serviços**.

A pasta predefinida é:

```text
/config/pingo_doce_session
```

## Copiar a cookie

- Prima o botão **Pingo Doce — Copiar cookie**; ou
- execute a ação `pingo_doce_session.get_cookie` com `show_notification: true`.

A nova integração lê automaticamente a sessão mantida pelo add-on. Não precisa de receber a cookie manualmente.
