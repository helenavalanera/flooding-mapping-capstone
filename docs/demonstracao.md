# Demonstração controlada: preparo, roteiro, limpeza e checklists

A demonstração roda **localmente**, sem publicar nada e sem depender de API externa para os fluxos essenciais. Ela usa a rede de ruas real
de Porto Alegre com **dados sintéticos declarados**: uma tempestade inventada e ocorrências de demonstração, tudo em memória. Esses dados
**não são evidência meteorológica nem de eventos reais**, e as telas dizem isso (faixa "DEMONSTRAÇÃO" no painel e na PWA).

## Preparo (uma vez)

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.lock.txt   # ou requirements-servidor.txt
# a tabela de ruas de Porto Alegre precisa existir: data/processed/rede_poa.parquet
.venv/bin/python -m flooding_mapping.rede_poa        # gera a tabela, se faltar
# opcional, para a etapa do assistente com provedor real: GEMINI_API_KEY e GEMINI_MODEL no .env (nunca no Git)
```

Sem chave do provedor, o assistente responde com o **texto padrão** montado a partir dos dados (e diz isso na tela). Isso é um fluxo
legítimo da demonstração; o provedor só reformula.

## Execução

```bash
make demo           # painel em http://127.0.0.1:8766/ e PWA em http://127.0.0.1:8766/pwa/
```

O comando imprime os endereços e a credencial do operador **desta demonstração** (um valor fixo e público, só válido neste servidor de
demonstração). Para ver a PWA no celular, veja "Teste em dispositivo físico" abaixo.

## Limpeza e reinício

Todo o estado vive em memória: **pare (Ctrl+C) e rode `make demo` de novo** para voltar ao cenário inicial (uma ocorrência pendente e uma
interdição confirmada, ambas de demonstração). Nada é escrito em `data/operacional/`.

## Roteiro (cerca de 12 minutos)

Cada etapa diz o que mostrar e o que dizer sobre os limites.

**1. Desktop (painel).** Abra `/`. Mostre a faixa de demonstração. Troque para **Porto Alegre**. Em **Condições e previsão**, mostre a chuva, a fonte e a ressalva de que é uma série regional. Em **Ocorrências**, mostre o relato pendente e a interdição confirmada. Em **Mapa**, ative as camadas e clique em um trecho com risco estimado. Em **Proveniência**, mostre "O que se pode e o que não se pode afirmar" e o confronto com os eventos documentados (4 de 19 detectados): *o risco por trecho é um baseline experimental, sem validação em vias*.

**2. Assistente.** Com um trecho selecionado, abra **Assistente** e pergunte "Por que este trecho está em atenção?". Mostre a origem declarada da resposta (texto padrão ou reformulado). Faça uma pergunta sem contexto ("O vento amanhã?"): o assistente diz que não há dado.

**3. PWA.** Abra `/pwa/` num celular ou na janela estreita. Toque em **Origem → Escolher no mapa**, marque a origem, depois o destino; escolha **Carro** (e repita com **A pé**). Toque em **Analisar deslocamento**. Mostre o cartão de orientação, o painel inferior (tempo, distância, chegada, indicador de exposição), as rotas alternativas e **Ver detalhes** (condições, trade-offs, trechos, explicação).

**4. Ocorrência.** Na PWA, toque em **Relatar**, marque um ponto **sobre a rota**, escreva "Rua alagada (demonstração, sintético)" e envie. Mostre que o relato **não interdita**: a rota é a mesma. No painel, **Ocorrências**, entre como operador com a credencial impressa, clique em **Revisar** no relato, escolha **Confirmar**, impacto **interdição**, escreva a evidência ("Confirmado em vistoria de demonstração, sintético") e registre.

**5. Recalcular.** Na PWA, toque em **Editar trajeto** e **Analisar** de novo. Mostre que o cartão agora informa mais trechos evitados e que o **traçado da rota mudou**; explique o trade-off de tempo e distância. O teste automatizado `tests/e2e/jornada.js` verifica essa mudança.

**6. Experiência mobile.** Com a rota na tela, mostre o painel inferior em modo compacto e expandido (botão, sem arrastar), os controles flutuantes (**Eu**, **Rota**, **Mapa** com camadas e legenda, **Relatar**), e que um relato pendente aparece como "!" e uma interdição como "✕", com texto, não só cor.

**Se algo falhar ao vivo:** pare e reinicie (`make demo`); o estado volta ao início. Nenhuma etapa depende de internet, exceto os mapas-base (tiles do OpenStreetMap) e, opcionalmente, o provedor de linguagem.

## Teste em dispositivo físico (checklist; **não executado** até haver aparelho e registro)

Nenhum teste em aparelho real foi executado neste repositório. Os testes de navegador emulam tela, toque e tamanhos, e **não** substituem GPU, sensores, rede e Safari reais. Preencha a tabela abaixo ao executar.

**Como acessar do celular.** Geolocalização e service worker exigem contexto seguro (HTTPS ou `localhost`). Opções:
- **Android + Chrome:** conecte por USB, ative a depuração e rode `adb reverse tcp:8766 tcp:8766`; abra `http://localhost:8766/pwa/` no celular.
- **iPhone + Safari:** exige HTTPS. Use um túnel HTTPS temporário sob a sua responsabilidade (isso envia tráfego por um terceiro: faça só com os dados sintéticos da demonstração).
- Sem HTTPS, o mapa e as rotas funcionam, mas a localização e a instalação como PWA podem ser bloqueadas. Registre isso, não o oculte.

| Verificação | Resultado | Observação |
|---|---|---|
| Instalar / adicionar à tela inicial | | |
| Abrir o PWA em tela cheia | | |
| Layout e áreas seguras (notch, barra inferior) | | |
| Navegar no mapa (arrastar, pinça) | | |
| Cartão, painel inferior e botão de expandir | | |
| Localização com consentimento (negar e permitir) | | |
| Formulários (teclado não cobre campos) | | |
| Rotas e alternativas (carro e a pé) | | |
| Reportar ocorrência | | |
| Rede indisponível (modo avião): aviso honesto | | |
| Orientação retrato e paisagem | | |

Registre também: dispositivo, sistema, navegador e versão, data, quem testou, problemas e capturas de tela.

## Checklist final de aceite

- [ ] `make demo` sobe sem erro e `/api/saude` responde `ok`.
- [ ] Faixa "DEMONSTRAÇÃO" visível no painel e na PWA.
- [ ] Rotas de carro e a pé calculadas, com alternativas e trade-offs.
- [ ] Relato não interdita; confirmação do operador interdita; a rota muda.
- [ ] Meteorologia mostra fonte, atualização, escopo regional e validade; sem dados, a tela diz que não há estimativa (e que isso não é rota sem risco).
- [ ] Assistente responde com texto padrão sem chave e diz a origem da resposta.
- [ ] Mapa 2D funciona sem WebGL (teste `sem_webgl.js`).
- [ ] `pytest` e os testes de navegador passam (ver `qa_relatorio_final.md`).
- [ ] Teste em dispositivo físico executado e registrado, **ou** registrado como pendente por falta de aparelho.
