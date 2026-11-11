# QA em dispositivo físico (celular)

**Estado: NÃO EXECUTADO. Bloqueio externo: não há aparelho acessível a quem preparou este documento.** Em 11/11/2026 foi verificado, na máquina de desenvolvimento, que não há
`adb` instalado, nem ferramentas de dispositivo do Xcode, nem aparelho Android ou iOS conectado por USB. Os testes de navegador do projeto **emulam** tela e toque no
Chromium; eles **não** substituem o teste físico (GPU, sensores, Safari, rede móvel, teclado virtual, barra de endereço e áreas seguras reais).

Este roteiro permite que outra pessoa execute o teste e registre o resultado. **Enquanto a tabela da seção 6 estiver vazia, o MVP deve ser descrito como funcionalmente
concluído em ambiente automatizado, com validação física pendente.**

## 1. Pré-requisitos (nos dois sistemas)

- O computador com o repositório, o ambiente Python do servidor e a tabela de ruas `data/processed/rede_poa.parquet` (ver `docs/demonstracao.md`).
- Celular e computador na **mesma rede Wi‑Fi**, ou um cabo USB (Android).
- Usar **somente a demonstração** (`make demo`): ela tem dados sintéticos declarados e não guarda nada em disco. Não conecte o celular a um servidor com dados reais.
- Anotar antes: modelo do aparelho, sistema e versão, navegador e versão, data, quem testa.

## 2. Por que HTTPS importa

A localização do navegador e o service worker (instalação e uso offline do PWA) exigem **contexto seguro**: HTTPS, ou `localhost`. Em HTTP por IP da rede local:

- o **mapa, as rotas, os cartões, o painel inferior e os formulários funcionam** (testam layout e toque);
- a **localização** e o **service worker** podem ser bloqueados. Registre isso como limitação do método, não como defeito do produto.

## 3. Android (Chrome)

**Opção A, recomendada (dá contexto seguro): USB com `adb reverse`.**

1. No celular: ativar as Opções do desenvolvedor e a Depuração USB; conectar o cabo e autorizar o computador.
2. No computador: instalar o Android Platform Tools (que traz o `adb`) e conferir `adb devices` (o aparelho deve aparecer como `device`).
3. Subir a demonstração: `make demo`.
4. Encaminhar a porta: `adb reverse tcp:8766 tcp:8766`.
5. No Chrome do celular, abrir `http://localhost:8766/pwa/` (o `localhost` conta como contexto seguro).
6. Opcional: no computador, abrir `chrome://inspect` para ver o console e a rede do aparelho.

**Opção B, sem cabo (só layout): Wi‑Fi.**

1. `DEMO_HOST=0.0.0.0 make demo` (o servidor passa a aceitar a rede local; **pare-o ao terminar**).
2. Descobrir o IP do computador (macOS: `ipconfig getifaddr en0`) e liberar a porta 8766 no firewall, se necessário.
3. No celular, abrir `http://<IP>:8766/pwa/`. Sem HTTPS, localização e instalação podem falhar.

**Instalar o PWA:** menu do Chrome → "Instalar app" ou "Adicionar à tela inicial", e abrir pelo ícone (modo tela cheia).

## 4. iPhone / iPad (Safari)

O Safari exige HTTPS para localização e service worker, e o `adb reverse` não existe no iOS. Escolha uma opção:

- **Opção A, só layout, sem nada externo:** `DEMO_HOST=0.0.0.0 make demo` e abrir `http://<IP>:8766/pwa/` no Safari. Testa layout, áreas seguras, mapa, painel inferior e formulários. **Não** testa localização, service worker nem instalação completa.
- **Opção B, com HTTPS, por túnel temporário:** um serviço de túnel HTTPS (por exemplo, o `cloudflared` em modo rápido, `cloudflared tunnel --url http://localhost:8766`) gera uma URL pública temporária para o servidor local. **Isso envia o tráfego por um terceiro e abre o servidor à internet enquanto o túnel durar.** Faça só com a demonstração (dados sintéticos), pare o túnel ao terminar, e não use esse caminho com dados reais.
- **Opção C, HTTPS de uma hospedagem:** exige publicar o serviço, o que **não foi autorizado**. Só depois de uma decisão separada (ver `docs/render.md`).

**Instalar o PWA:** Safari → Compartilhar → "Adicionar à Tela de Início"; abrir pelo ícone.
**Depurar:** em um Mac, ative o Inspetor Web no iPhone (Ajustes → Safari → Avançado) e use o menu Desenvolver do Safari do Mac, com cabo.

## 5. Roteiro de verificação

Execute com o servidor da demonstração. Em **cada** item, registre Aprovado, Falhou ou Não aplicável, com uma observação e uma captura de tela quando houver problema.

| # | Verificação | Como fazer | Critério |
|---|---|---|---|
| 1 | Abrir | abrir `/pwa/` no navegador do aparelho | a tela carrega; o aviso "DEMONSTRAÇÃO · dados sintéticos" aparece no cartão superior |
| 2 | Instalação | adicionar à tela inicial e abrir pelo ícone | abre em tela cheia, com o ícone do app |
| 3 | Áreas seguras | observar com o notch/ilha dinâmica e a barra inferior | o cartão superior e a barra de abas não ficam sob o notch ou a barra do sistema |
| 4 | Mapa | arrastar e dar zoom com pinça | movimento fluido; os controles flutuantes não cobrem o essencial |
| 5 | Origem e destino | Planejar → Origem → "Escolher no mapa", tocar; repetir para o destino | o painel recolhe para tocar e reabre; os pontos O e D aparecem |
| 6 | Rotas | escolher Carro, "Analisar deslocamento"; repetir com "A pé" | rota, tempo, distância, chegada e alternativas aparecem para os dois modais |
| 7 | Painel inferior | tocar em "Ver detalhes" e recolher | expande e recolhe por toque, sem depender de arrastar; o texto é legível |
| 8 | Alternativas | tocar em outra rota nos cartões deslizantes | a rota selecionada fica em destaque no mapa |
| 9 | Controles flutuantes | tocar em "Rota", em "Mapa" (camadas e legenda) e em "Relatar" | cada um responde; a legenda explica os símbolos |
| 10 | Localização | tocar em "Eu" e permitir; depois negar e tentar de novo | com permissão, marca a posição (uma leitura); negada, mostra a mensagem e o app segue por mapa |
| 11 | Ocorrência | Relatar → marcar um ponto na rota → escrever → enviar | mensagem de relato recebido; o relato **não** interdita a rota |
| 12 | Interdição | no painel do computador, entrar como operador e confirmar o relato com impacto de interdição; no celular, "Editar trajeto" e analisar de novo | o cartão mostra mais trechos evitados e o traçado muda |
| 13 | Formulários | digitar no campo de relato | o teclado virtual não cobre o campo ativo |
| 14 | Rede indisponível | ativar o modo avião e recarregar o app | o app abre sem fingir dados atuais; avisa que o servidor está sem conexão |
| 15 | Orientação | girar o aparelho (retrato e paisagem) | sem corte nem sobreposição que impeça o uso |
| 16 | Atualização | recarregar após reiniciar o servidor | não permanece uma versão antiga e incompatível |

## 6. Registro dos resultados

Preencher ao executar. **Hoje: não executado.**

| Campo | Valor |
|---|---|
| Modelo do aparelho | |
| Sistema operacional e versão | |
| Navegador e versão | |
| Data do teste | |
| Quem executou | |
| Método de acesso (USB reverse, Wi‑Fi HTTP, túnel HTTPS) | |
| Instalou como PWA? | |

| # | Resultado (Aprovado / Falhou / N.A.) | Observação | Evidência (arquivo) |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | | | |
| 10 | | | |
| 11 | | | |
| 12 | | | |
| 13 | | | |
| 14 | | | |
| 15 | | | |
| 16 | | | |

Problemas encontrados (descrição, passo, captura, gravidade): _a preencher_.

## 7. Como encerrar

Parar o servidor (Ctrl+C) e, se houver, o túnel; desfazer `adb reverse` (`adb reverse --remove-all`); remover o app de teste da tela inicial. Atualizar a seção 5 de `docs/qa_relatorio_final.md` (Teste físico) com o resultado e anexar as evidências.
