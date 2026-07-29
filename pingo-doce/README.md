# Pingo Doce Plus

Projeto conjunto para Home Assistant composto por:

- **Add-on `pingo_doce_plus`**: abre o Pingo Doce num Chromium persistente, guarda o perfil completo e mantém a sessão ativa.
- **Custom integration `pingo_doce_plus`**: transforma os dados do add-on em entidades, botões e eventos do Home Assistant.

## Objetivo

O login é feito uma única vez na interface Web do add-on. O perfil Chromium fica em `/data`, por isso reinícios do Home Assistant, Supervisor, add-on ou servidor não apagam a sessão.

Só é necessário repetir o login quando o próprio Pingo Doce invalidar a sessão.

## Instalação

### Add-on

Adicione este repositório à Loja de Add-ons:

```text
https://github.com/BrunoCunha1983-creator/ha-plugins
```

Instale **Pingo Doce Plus**, inicie-o, abra a interface Web e faça login.

### Integração

Copie `custom_components/pingo_doce_plus` para `/config/custom_components/` ou adicione o repositório ao HACS como repositório personalizado do tipo **Integração**. Reinicie o Home Assistant e adicione **Pingo Doce Plus** em Dispositivos e Serviços.

## Entidades principais

- sessão autenticada e navegador ativo;
- pontos, saldo e saldo a expirar;
- encomenda atual, estado, janela e progresso;
- última encomenda, total e histórico;
- cupões, quando a página os disponibiliza;
- deteção de alterações e palavras de estado;
- botões para atualizar, abrir o login e reiniciar o navegador.

## Eventos

- `pingo_doce_plus_order_changed`
- `pingo_doce_plus_website_changed`
- `pingo_doce_plus_login_required`
