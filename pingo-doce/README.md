# Pingo Doce Plus

Solução unificada para Home Assistant composta por:

- **add-on Pingo Doce Plus**, que mantém um Chromium e o perfil de autenticação persistentes;
- **custom integration Pingo Doce Plus**, instalada automaticamente pelo add-on em `/config/custom_components/pingo_doce_plus`;
- comunicação local através de `/config/pingo_doce_plus`, sem copiar cookies manualmente.

## Instalação

1. Adicione este repositório à Loja de Add-ons:
   `https://github.com/BrunoCunha1983-creator/ha-plugins`
2. Atualize a Loja de Add-ons e instale **Pingo Doce Plus**.
3. Inicie o add-on uma vez. Isto instala/atualiza a custom integration automaticamente.
4. Reinicie o Home Assistant.
5. Vá a **Definições → Dispositivos e serviços → Adicionar integração** e procure **Pingo Doce Plus**.
6. Abra a interface Web do add-on e faça o login no Pingo Doce.

## Reinícios

O perfil Chromium é guardado em `/data/chromium-profile`, que é persistente. Depois de um reinício do Home Assistant, do add-on ou do equipamento, a sessão é restaurada automaticamente sempre que o Pingo Doce ainda a considerar válida.

Só será necessário repetir o login quando o próprio Pingo Doce invalidar a sessão ou voltar a exigir autenticação.

## Entidades

A integração disponibiliza o estado da sessão, pontos, saldo, saldo a expirar, validade, mensagem de expiração, última atualização e disponibilidade da cookie.

Também disponibiliza botões para atualizar, abrir o login, reiniciar o Chromium, exportar cookies e mostrar a cookie numa notificação copiável.

## Segurança

Os valores das cookies não são publicados como estados de entidades. São guardados localmente com permissões restritas e apenas apresentados quando é usada a ação específica para obter a cookie.
