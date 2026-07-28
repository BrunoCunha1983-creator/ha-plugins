# Instalação e utilização

## Instalar como add-on local

1. Descompacte o ZIP.
2. Copie a pasta `pingo_doce_session` para a pasta `/addons/` do Home Assistant.
3. No Home Assistant, abra **Definições → Add-ons → Loja de add-ons**.
4. No menu superior direito, escolha **Procurar atualizações**.
5. Instale **Pingo Doce — Sessão Persistente**.
6. Inicie o add-on.
7. Prima **Abrir interface Web**.
8. Faça o login normal no site do Pingo Doce dentro da janela Chromium.

Pode depois fechar a interface Web no seu computador. O separador do Pingo Doce permanece aberto dentro do add-on.

## Entidades criadas

- `binary_sensor.pingo_doce_sessao`
- `sensor.pingo_doce_pontos`
- `sensor.pingo_doce_saldo`
- `sensor.pingo_doce_saldo_validade`

As entidades são publicadas diretamente pelo add-on através da API interna do Home Assistant. Não existe uma pasta `custom_components`.

## Persistência

O perfil Chromium e uma cópia do estado da sessão são guardados em `/data`, que faz parte dos dados persistentes e das cópias de segurança do add-on.

Enquanto o add-on estiver em execução:

- o Chromium permanece aberto;
- a página da área pessoal permanece aberta;
- a página é reaberta se for fechada;
- o Chromium é recuperado se falhar;
- a sessão é consultada periodicamente;
- os cookies de sessão são guardados para tentar recuperar o acesso depois de um reinício.

O Pingo Doce pode invalidar a sessão do lado do servidor. Nesse caso, abra novamente a interface Web e repita o login.

## Segurança

A porta 7900 deve ficar acessível apenas na rede local. Pode definir `vnc_password` na configuração do add-on para proteger a janela Chromium com uma palavra-passe adicional.
