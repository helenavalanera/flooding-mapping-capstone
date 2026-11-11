# Relatório final de QA e matrizes de aceite

Data da execução: 11/11/2026, na branch `develop`. Tudo foi executado localmente; nada foi publicado.

## 1. Testes executados

| Categoria | Comando | Resultado |
|---|---|---|
| Suíte completa (unitários, contrato, serviço, HTTP, auditorias, navegador) | `pytest` com `PLAYWRIGHT_CORE` e `CHROME_PATH` | **500 aprovados, 1 ignorado**, 0 falhas (720 s) |
| Ignorado | `tests/test_r2.py:120` | falta o pacote `boto3` (publicação em armazenamento externo, fora do escopo da demonstração) |
| Painel em navegador (RS e POA, 3D e 2D, seleção, assistente, estado sem chuva, proveniência, 5 larguras) | `tests/e2e/dashboard.js` | aprovado |
| PWA em navegador (consentimento, lugares, trajetos, análise, ordem do resultado, perguntas, controles, privacidade, offline, **7 larguras: 320, 360, 390, 430, 768, 1024, 1400**) | `tests/e2e/pwa.js` | aprovado |
| Mapa **sem WebGL** nos dois territórios (5 larguras) | `tests/e2e/sem_webgl.js` | aprovado |
| Atualização do service worker | `tests/e2e/pwa_sw.js` | aprovado |
| **Jornada integrada** (desktop → PWA → relato → operador confirma → rota recalculada) | `tests/e2e/jornada.js` | aprovado; o traçado da rota muda e as interdições consideradas aumentam |
| Contêiner (Docker): build, saúde, rotas com **chuva real**, relato + confirmação, 403 sem credencial, reinício com persistência | manual, 11/11/2026 | aprovado: saúde `healthy`, 410 MiB, ocorrência confirmada persistiu ao reiniciar |

Comparação com a linha de base anterior (498 aprovados, 1 ignorado): +2 testes automatizados (sinalização de fonte sintética e a jornada integrada), sem regressão. Nenhum teste foi removido ou enfraquecido; os testes de navegador foram **adaptados ao novo layout do PWA** (a hierarquia mudou de propósito, e o novo desenho é verificado por eles).

**Dados reais e sintéticos.** Os testes de navegador e a jornada usam a rede de ruas real de Porto Alegre com **chuva e ocorrências sintéticas declaradas** (`tests/e2e/servidor_demo.py`). A verificação do contêiner usou a **previsão real** (Open-Meteo) e um relato e uma confirmação de teste, descartados ao final. As chamadas reais ao Gemini estão em `validacao_gemini.md` e **não** foram repetidas nesta rodada.

**Falhas encontradas e corrigidas durante a execução:**
- O aviso de dados sintéticos da PWA era apagado pela primeira análise; passou a ficar fixo no cartão superior.
- O painel e a PWA diziam "Fonte: Open-Meteo" mesmo com a série sintética; agora mostram a fonte real da série.
- Processos de navegador órfãos de execuções interrompidas travaram a máquina e fizeram a suíte expirar; foram encerrados e a suíte passou limpa.
- Um relato feito sobre a rota não alterava a rota no primeiro teste da jornada, por escolher o ponto errado na tela; o teste passou a clicar num ponto da própria rota e a exigir que o **traçado mude**. O comportamento do servidor foi conferido à parte: o traçado muda a cada interdição no ponto.

## 2. Evidências visuais do novo PWA

`docs/figuras/pwa_navegacao_compacta_390.png`, `pwa_navegacao_detalhes_390.png`, `pwa_navegacao_compacta_320.png`, `pwa_planejar_390.png` (capturas do navegador em emulação de celular; **não** são capturas de aparelho físico).

## 3. O que não foi verificado

- **Aparelho físico:** nenhum teste em iPhone ou Android. Há checklist em `demonstracao.md`. Os testes emulam tela e toque no Chromium; **Safari e Firefox não foram usados**.
- **Orientação paisagem:** só conferida em captura manual (844×390), sem teste automatizado.
- **Acessibilidade:** não foi rodada auditoria automática (por exemplo axe) nem leitor de tela. Foram aplicados: áreas de toque de 44–48 px, risco com texto e símbolo além da cor, `aria-label`s, foco movido ao resultado e `prefers-reduced-motion`. A referência WCAG 2.2 AA **não foi comprovada**.
- **Carga e segurança ofensiva:** sem teste de carga nem de penetração (ver `seguranca_lgpd.md`).
- **Qualidade do provedor de linguagem em escala** (ver `validacao_gemini.md`).
- **Busca por endereço:** não implementada, por decisão de privacidade (ver `guia_de_uso.md`).
- **Instruções de manobra:** não existem, porque o backend não as produz; o produto declara isso.

## 4. Matriz A: capstone

Estados: **V** = concluído e validado; **L** = concluído com limitação documentada; **P** = parcial.

| Requisito | Estado | Evidência | Pendência |
|---|---|---|---|
| Problema e objetivos | L | `README.md`, `proposta.md`, `sintese_academica.md` | a proposta original inclui ônibus; o produto não (GTFS vencido, sem JDK) |
| Arquitetura | V | `produto_preventivo.md`, `hospedagem.md` | — |
| Dados e proveniência | L | README, tela de Proveniência | licença dos dados do DAER a confirmar; eventos poucos e enviesados |
| Metodologia espacial | L | `produto_preventivo.md` (cobertura, risco) | qualidade da malha OSM não validada |
| Metodologia meteorológica | L | seção Meteorologia | chuva regional (≈10 km), passado é análise do modelo |
| Metodologia de risco | L | `auditoria_risco`, `sintese_academica.md` | **sem validação em vias**: 4 de 19 eventos detectados; delimitada, não validada |
| Roteamento | V | auditoria contra networkx: 0 diferenças em 200 pares | valida o algoritmo, não a malha nem o tempo real |
| Ocorrências e interdições | L | fluxo HTTP e `jornada.js` | procedimento humano **pendente de aprovação** (`operacao_ocorrencias.md`) |
| Desktop e PWA | L | testes de navegador, 5 e 7 larguras | sem aparelho físico |
| Gemini | L | `validacao_gemini.md`, testes de falha | amostra pequena; sem custo e volume |
| Testes e resultados | V | seção 1 | — |
| Limitações | V | `produto_preventivo.md`, `seguranca_lgpd.md`, `sintese_academica.md` | — |
| Documentação acadêmica | P | `sintese_academica.md` e demais | `proposta.md` e os `.docx` descrevem o escopo anterior e **não foram reescritos** (preservados); slides não criados |
| Apresentação | P | roteiro (`demonstracao.md`) e síntese | não há apresentação de slides |

**Denominador: 14 requisitos. V = 4 (29%), L = 8 (57%), P = 2 (14%), pendentes = 0.** Concluídos (V ou L): **12 de 14 (86%)**. Os dois parciais são de **material**
(alinhar os documentos de proposta ao escopo final e montar os slides); **o capstone não está 100% concluído** até isso ser feito.

## 5. Matriz B: MVP demonstrável

**B** = bloqueado externamente.

| Requisito | Estado | Evidência | Pendência |
|---|---|---|---|
| Inicialização | V | `make demo`, contêiner testado | — |
| Desktop | V | `dashboard.js` | — |
| PWA | L | `pwa.js`, capturas | Safari e aparelho físico |
| Design system | L | CSS compartilhado, componentes padronizados | auditoria WCAG automática não executada |
| Rotas de carro | V | auditoria, `jornada.js` | — |
| Rotas de caminhada | V | auditoria, testes de rotas | — |
| Alternativas | V | `pwa.js` (trade-offs e cartões) | — |
| Meteorologia | L | testes de validade, UI com fonte e idade | regional; sem pluviômetro |
| Ocorrências | L | fluxo do operador | procedimento humano pendente de aprovação |
| Interdições | V | `jornada.js`: o traçado muda | — |
| Risco contextual | L | UI com limitações, Proveniência | experimental, sem validação em vias |
| Gemini | L | texto padrão sem chave; reformulação com chave | amostra pequena |
| Fallback 2D | V | `sem_webgl.js` | só Chromium |
| Persistência | V | reinício no contêiner, testes de arquivo | um processo apenas |
| Segurança | L | `seguranca_lgpd.md`, testes de servidor | sem teste de penetração; pendências listadas |
| Testes | V | seção 1 | — |
| Cenário de demonstração | V | `jornada.js`, `demonstracao.md` | — |
| Teste físico | B | checklist em `demonstracao.md` | exige um aparelho e HTTPS (ou `adb reverse`) |
| Documentação de execução | V | `demonstracao.md`, `hospedagem.md`, `guia_de_uso.md` | — |

**Denominador: 19 requisitos. V = 11 (58%), L = 7 (37%), B = 1 (5%), parciais e pendentes = 0.** Atendidos: **18 de 19 (95%)**.

Pelos critérios de aceite do MVP fixados para esta rodada, todos estão atendidos, incluindo o último ("teste físico executado ou explicitamente
registrado como bloqueio externo"): ele está **registrado como bloqueio externo**, não como realizado. **O MVP não está 100% validado em aparelho.**

## 6. Ação para remover o bloqueio do teste físico

Ter um celular, rodar `make demo`, acessá-lo por `adb reverse tcp:8766 tcp:8766` (Android + Chrome) ou por um túnel HTTPS temporário (iPhone + Safari),
executar o roteiro e preencher a tabela de `docs/demonstracao.md`, anexando capturas de tela.
