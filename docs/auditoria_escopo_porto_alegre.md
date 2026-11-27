# Auditoria de escopo: o produto ativo é só Porto Alegre

Auditoria de 26/11/2026 do repositório inteiro. **Regra:** a versão ativa do produto apresenta exclusivamente o município de Porto Alegre (território, dados, resultados, mapas, simulador, documentação e o experimento de GeoAI no recorte do município). Tudo o que pertence ao
Rio Grande do Sul (rodovias estaduais do DAER, bloqueios da CPRv BM, registros do S2iD, gatilho municipal, previsão de 72 h), à mobilidade e ao PWA foi **arquivado sem ser apagado** (ver [`app/arquivo/README.md`](../src/flooding_mapping/app/arquivo/README.md)).

## Método

Busca, em todos os arquivos de texto versionáveis (rastreados e não rastreados, fora dos ignorados), por: DAER, S2iD, CPRv, rodovia(s), bloqueio(s), "Rio Grande do Sul", estadual/estaduais, `RS` e municípios. Cada arquivo foi classificado **pelo conteúdo, pelas dependências e pelo uso**, não pelo nome
(por exemplo, `rs-` em `resultados.js` é o prefixo de "resultados", não o estado). Teste que impede a volta de qualquer item: `tests/test_escopo_porto_alegre.py` e `tests/test_app_build.py`.

## Classificação

| Classe | O que é | Arquivos com ocorrências (aprox.) | Decisão |
|---|---|---|---|
| **1. Utilizada pelo produto atual** | O estado aparece só para situar Porto Alegre ("Porto Alegre, Rio Grande do Sul") e no nome do arquivo do mapa-base (`rs.pmtiles`, um recorte do OpenStreetMap que cobre o estado inteiro, usado só como fundo visual) | `inicio/index.html` (1 rótulo), `mapa-base.js`, `config-dados.js`, `mapa-base` em `docs/mapa_base.md` | Mantida |
| **2. Referência metodológica contextual** | Documentação, inventário de fontes, glossário, metodologia, referências bibliográficas (ABNT) e a seção de referências da landing, com as fontes estaduais **rotuladas "Frente arquivada"**; `logic.js`, biblioteca de funções puras compartilhada com o PWA arquivado | ~15 documentos, `config/referencias.yaml`, a bibliografia da landing, `logic.js` | Mantida: são referências legítimas e explicações históricas, não funcionalidades |
| **3. Material histórico arquivado** | Painel de duas escalas, PWA, montagem do site estadual, dados e saídas do DAER/IBGE/S2iD, módulos Python da frente estadual (servidor, gatilho, previsão, cobertura, coleta), testes, relatórios de modelo, documentos legados (com aviso), scripts da apresentação anterior | `app/arquivo/` (23 arquivos), 24 módulos Python, 17 documentos, 15 testes, 8 relatórios, `reports/ml/`, `data/events/`, `config/territorios.yaml` e a parte estadual de `config/analysis.yaml` | Arquivada (física ou documentada), conforme a tabela abaixo |
| **4. Referência indevida na interface ativa** | O que aparecia na interface atual: território "Rio Grande do Sul", abas Visão geral, Condições e previsão, Mobilidade e Ocorrências, camadas de municípios, rodovias, bloqueios, S2iD, risco por hora, ocorrências, interdições e rotas, seletor Dados reais/Demonstração, fontes DAER/S2iD/CPRv no rodapé e na aba Proveniência | `index.html`, `painel.js`, `mapa.js`, `mapa2d.js`, `territorio.js`, dados estáticos | **Corrigida**: removida da interface e arquivada |

## O que foi feito

| Item | Antes | Depois |
|---|---|---|
| Painel | Dois territórios, oito abas | Um território (Porto Alegre) e quatro áreas: Resultados, Mapa, Simulador e Proveniência. Cópia fiel da versão anterior em `app/arquivo/painel-estadual/` |
| Mapa | Camadas estaduais, risco por hora, ocorrências, interdições e rotas | Relevo, escoamento potencial (Fase 3) e drenagem cadastrada; o motor 2D (sem WebGL) mostra só o mapa-base e diz que as camadas exigem WebGL |
| Proveniência | Fontes estaduais e matriz por região | Fontes do estudo, com a condição de uso e o que cada dimensão é e não é |
| Dados estáticos | `rodovias.geojson`, `municipios.geojson`, `cobertura_rs.json`, `impacto_rs.json`, `ocorrencias.json`, `territorios.json` | Só `resultados_poa.json` e `territorio_poa.json`. Os cinco primeiros foram **retirados do Git e guardados** em `data/raw/arquivo_estadual/` (licença de DAER, IBGE e S2iD não confirmada); `territorios.json` foi para o arquivo |
| Saídas da criticidade e índice de segmentos | `outputs/web/*`, `app/data/*.parquet` (versionados) | Guardados em `data/raw/arquivo_estadual/` |
| Montagem do site | `app/build.py` com modelo, previsão e bloqueios | `app/build.py` só copia a interface de Porto Alegre; a versão anterior é `app/arquivo/site_estadual.py` |
| Workflow de publicação | Agendado, com modelo e R2 | Só manual e sem modelo nem segredos |
| Landing | Mapas de trechos e de drenagem (7 imagens) | Quadro e texto das quatro dimensões; os mapas ficam só no disco local |

## O que fica de fora da árvore versionada, por licença

Ver `docs/inventario_fontes.md` e `app/arquivo/README.md`: derivados da Profill (tiles, raster e figuras da GeoAI, mapas de trechos), drenagem cadastrada, malha do DAER e derivados, lista de alagamentos da Prefeitura (127 coordenadas, substituída nos testes por pontos sintéticos).

## Pendências e limites desta auditoria

- **Continuam no histórico do Git** (commits já publicados) os arquivos que saíram da árvore atual: retirá-los do histórico exigiria reescrever a história publicada, o que não foi feito.
- **Capturas de tela antigas em `docs/figuras/`** (`painel_rio_grande_do_sul_mapa.png` e outras do painel estadual) ainda estão rastreadas desde antes desta auditoria; a mais sensível mostra a malha do DAER. Recomenda-se retirá-las da árvore em um commit à parte.
- **Módulos Python da frente estadual** ficam nos lugares originais (o servidor histórico e os testes os importam); o produto atual não os carrega. Mover para um pacote de arquivo é uma refatoração ampla, deixada para depois.
- **Coleta agendada dos bloqueios** (`coletor-crbm.yml`): continua habilitada; desligar é decisão operacional (`COLETOR_ATIVO = false`).
- **A API do servidor histórico** (`/api/previsao`, ocorrências, rotas) continua no código, sem interface.
- O produto atual não opera em tempo real, não prevê alagamentos e não mostra rodovias, bloqueios nem indicadores estaduais como funcionalidade.
