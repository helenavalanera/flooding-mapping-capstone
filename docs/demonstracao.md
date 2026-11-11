# Demonstração controlada: do preparo ao encerramento

Este roteiro pode ser seguido por quem não conhece o código. A demonstração roda **localmente**, sem publicar nada, e **a jornada principal não depende de API externa**.
Ela usa a rede de ruas real de Porto Alegre com **dados sintéticos declarados**: uma tempestade inventada e ocorrências de demonstração, tudo em memória.
Esses dados **não são evidência meteorológica nem de eventos reais**, e as telas dizem isso (faixa "DEMONSTRAÇÃO" no painel e "DEMONSTRAÇÃO · dados sintéticos" na PWA).

Única dependência de rede: os **mapas-base** (tiles do OpenStreetMap). Sem internet, o mapa fica sem fundo, mas dados, rotas, ocorrências e interdições continuam funcionando.
O assistente com provedor de linguagem é **opcional**: sem chave, ele responde com o texto padrão e diz isso na tela.

## 1. Preparação (uma vez)

1. Ter Python 3.12 e instalar as dependências do servidor: `python -m venv .venv && .venv/bin/pip install -r requirements-servidor.txt` (ou `requirements.lock.txt` para o ambiente completo).
2. Ter a tabela de ruas `data/processed/rede_poa.parquet` (17 MB). Se faltar, `make rede` a gera (exige o ambiente completo e o recorte do OpenStreetMap; veja o README).
3. Opcional, só para ver o assistente reformular com o provedor real: definir `GEMINI_API_KEY` e `GEMINI_MODEL` no arquivo `.env` (que o Git ignora) e iniciar com `DEMO_GEMINI=1 make demo`. **Nunca coloque a chave em arquivo versionado.**

## 2. Inicialização

```bash
make demo              # usa .venv/bin/python; com outro Python: make demo PY=python
```

Aguarde a mensagem `pronto`. O comando imprime os endereços e a **credencial do operador desta demonstração** (um valor fixo e público, válido só neste servidor de demonstração):

```
painel (desktop): http://127.0.0.1:8766/
PWA (celular):     http://127.0.0.1:8766/pwa/
credencial do operador: demo-operador-com-mais-de-24-caracteres
```

Verificação rápida: `curl http://127.0.0.1:8766/api/saude` deve responder `"status": "ok"` e `"sintetica": true`.

## 3. Acesso ao desktop

Abra `http://127.0.0.1:8766/` no navegador do computador. A faixa amarela "DEMONSTRAÇÃO" deve estar visível.

## 4. Acesso ao PWA

Abra `http://127.0.0.1:8766/pwa/` em uma janela estreita (largura de celular) ou, num aparelho real, siga `docs/qa_mobile_fisico.md`. O cartão escuro do topo deve dizer "DEMONSTRAÇÃO · dados sintéticos".

## 5. Consulta territorial (desktop)

1. No canto superior direito, escolha **Porto Alegre**.
2. Aba **Condições e previsão**: mostre a chuva, a fonte e a ressalva de que é uma série regional (e, na demonstração, sintética).
3. Aba **Ocorrências**: mostre a lista, com **um relato pendente** e **uma interdição confirmada**, ambos de demonstração.
4. Aba **Mapa**: deixe as camadas ligadas, mova o controle "Hora do risco estimado" para **+5 h** e clique em um trecho colorido. No painel **Assistente**, toque em "Por que este trecho está em atenção?".
5. Aba **Proveniência**: mostre "O que se pode e o que não se pode afirmar" e o confronto com os eventos documentados (4 de 19 detectados).

**O que dizer:** o risco por trecho é um baseline experimental, sem validação em vias; a chuva é regional; nada aqui prevê alagamento por rua.

## 6. Planejamento de rota (PWA)

1. Em **Planejar**, escolha **Origem → "Escolher no mapa…"**; o painel recolhe; toque no mapa **perto de uma via** (por exemplo, no bairro Floresta). Repita para o **Destino** (por exemplo, perto do bairro Humaitá, a nordeste).
2. Deixe **Carro** e toque em **Analisar deslocamento**. Se aparecer "fora da cobertura" ou "nenhuma via", toque de novo mais perto de uma rua.
3. Observe o **cartão do topo** (rota e distância até o primeiro trecho de atenção, ou a interdição considerada), o **painel inferior** (tempo, distância, chegada, exposição estimada) e os **cartões de rota** deslizantes.
4. Toque em **Ver detalhes** para ver as condições, os trade-offs entre rotas e as perguntas sugeridas. Depois repita a análise escolhendo **A pé**.

Na demonstração, o cartão pode já mostrar "Interdição confirmada considerada: o cálculo evita N trecho(s)": é a interdição de demonstração que já existia (o número N depende de onde você tocou).

## 7. Registro de ocorrência

1. No PWA, toque em **Relatar** (botão flutuante).
2. Toque no mapa **sobre a linha da rota** (a rota fica visível por baixo do painel recolhido).
3. Toque em **Ver detalhes** para abrir o formulário, escreva por exemplo "Rua alagada (demonstração, sintético)" e toque em **Enviar relato**.
4. A mensagem diz que o relato foi recebido **como reportado** e que ele **não interdita** vias. Volte para **Planejar**: a rota **não mudou**.

## 8. Confirmação pelo operador

1. No painel do computador, aba **Ocorrências**.
2. Em **Credencial do operador**, cole `demo-operador-com-mais-de-24-caracteres` e toque em **Entrar como operador**. Agora o texto livre dos relatos fica visível.
3. Na linha do seu relato (situação **reportada**), toque em **Revisar**.
4. Escolha **Confirmar**, impacto **interdição**, e escreva a evidência (mínimo de 10 caracteres), por exemplo "Confirmado em vistoria de demonstração, sintético". Toque em **Registrar**.
5. A linha passa a **confirmada**. Sem a credencial, qualquer tentativa de confirmar recebe erro 403.

## 9. Recálculo da rota

1. No PWA, toque em **Editar trajeto** e em **Analisar deslocamento** de novo.
2. O cartão do topo agora informa **mais trechos evitados**, e o **traçado da rota muda** no mapa. Em **Ver detalhes → Ocorrências no trajeto** aparece a decisão.
3. Explique o trade-off: o desvio pode custar tempo e distância; a escolha da rota é da pessoa, e o sistema nunca a chama de segura.

O teste automatizado `tests/e2e/jornada.js` executa essa sequência (relato, confirmação e recálculo) e verifica que o traçado da rota muda.

## 10. Encerramento e limpeza

- Pare o servidor com **Ctrl+C**. Todo o estado vive em memória; **nada foi escrito em `data/operacional/`**.
- Para voltar ao cenário inicial (um relato pendente e uma interdição confirmada), rode `make demo` de novo.
- Feche as janelas do navegador. Se usou `DEMO_HOST=0.0.0.0`, confirme que o servidor foi parado (ele aceitava a rede local).
- Se foi usado `adb reverse` ou um túnel, desfaça-os (veja `docs/qa_mobile_fisico.md`, seção 7).

## Se algo falhar ao vivo

Pare e reinicie (`make demo`): o estado volta ao início. Falhas comuns: porta 8766 ocupada (`lsof -i :8766`); tabela de ruas ausente (seção 1); mapa sem fundo (sem internet; as rotas continuam funcionando).

## Dados sintéticos: o que é o quê

| Elemento | Origem na demonstração |
|---|---|
| Rede de ruas | **real** (OpenStreetMap, 24/10/2026) |
| Chuva horária | **sintética**: uma série inventada, declarada na fonte e na tela |
| Relato pendente e interdição iniciais | **sintéticos**, marcados como de demonstração |
| Relato e confirmação feitos por você | **sintéticos** (escreva isso na evidência) |
| Credencial do operador | fixa e pública, só deste servidor de demonstração |

Ocorrências sintéticas **nunca** são evidência de eventos reais, e a chuva sintética **nunca** é evidência meteorológica.

## Teste em dispositivo físico

Veja `docs/qa_mobile_fisico.md` (roteiro, método de acesso e tabela de registro). **Estado: não executado.**

## Checklist final de aceite

- [ ] `make demo` sobe sem erro e `/api/saude` responde `ok`.
- [ ] Faixa de demonstração visível no painel e no PWA.
- [ ] Rotas de carro e a pé calculadas, com alternativas e trade-offs.
- [ ] O relato não interdita; a confirmação do operador interdita; a rota muda.
- [ ] A meteorologia mostra fonte, atualização, escopo regional e validade; sem dados, a tela diz que não há estimativa (e que isso não é rota sem risco).
- [ ] O assistente responde com texto padrão sem chave e diz a origem da resposta.
- [ ] O mapa 2D funciona sem WebGL (teste `sem_webgl.js`).
- [ ] `pytest` e os testes de navegador passam (ver `qa_relatorio_final.md`).
- [ ] Teste em dispositivo físico executado e registrado, **ou** registrado como pendente (hoje: pendente).
