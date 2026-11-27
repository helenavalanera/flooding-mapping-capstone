# Índice da documentação

Nome, finalidade e localização de cada documento do Flooding Mapping. Os documentos de **Histórico** descrevem frentes anteriores (escopo estadual, mobilidade, PWA, gatilho municipal) que foram arquivadas e não fazem parte do produto atual. Os números vigentes estão em `reports/qa/` e em `src/flooding_mapping/app/static/data/` (copiados para `numeros-e-relatorios/` na pasta de upload).

## Produto, método e resultados

| Documento | Finalidade | Localização |
|---|---|---|
| [Fase 3: entradas e saídas (proposta original e o que foi implementado)](fase3_entradas_e_saidas.md) | Entradas e saídas da Fase 3: proposta original e o que foi implementado. | `docs/fase3_entradas_e_saidas.md` |
| [Fase 3: o motor de contribuição potencial e o indicador topográfico](fase3_motor.md) | O motor de contribuição potencial e o indicador topográfico (dimensões A, B e C). | `docs/fase3_motor.md` |
| [Fase 3: resultados da execução](fase3_resultados.md) | Resultados da execução da Fase 3 (gerado). | `docs/fase3_resultados.md` |
| [Fase 4: a camada de escoamento potencial na aplicação](fase4_integracao.md) | A camada de escoamento potencial na aplicação: formato de distribuição e regras da tela. | `docs/fase4_integracao.md` |
| [Glossário oficial de nomenclaturas](glossario.md) | Glossário oficial de nomenclaturas e termos proibidos. | `docs/glossario.md` |
| [Landing científica (estudo)](landing_estudo.md) | A landing: oito seções, mapas de manchas, geração a partir dos relatórios e regras de redação. | `docs/landing_estudo.md` |
| [Mapa-base (Protomaps)](mapa_base.md) | Mapa-base (Protomaps): arquivo, estilos, fontes e licenças. | `docs/mapa_base.md` |
| [Mapa de análise, simulador, PWA e auditoria final (26/11/2026)](mapa_simulador_pwa.md) | Mapa de análise, simulador e auditoria final (26/11/2026). | `docs/mapa_simulador_pwa.md` |
| [Metodologia consolidada](metodologia.md) | Metodologia consolidada: fórmula, métodos 1 e 2, limites físicos, hipóteses e validações. | `docs/metodologia.md` |
| [Viabilidade do modelo de acúmulo superficial: o que os dados sustentam](modelo_retencao_viabilidade.md) | Viabilidade do modelo de acúmulo superficial: o que os dados sustentam. | `docs/modelo_retencao_viabilidade.md` |
| [Recorte municipal dos resultados por trecho](recorte_municipal.md) | Recorte municipal: só as ruas dentro de Porto Alegre (143.149 trechos), efeito nos números e como reproduzir. | `docs/recorte_municipal.md` |
| [Resultados executivos (aba Resultados)](resultados_executivos.md) | Resultados executivos da aba Resultados. | `docs/resultados_executivos.md` |
| [Robustez da validação espacial](robustez_espacial.md) | Robustez da validação espacial por blocos. | `docs/robustez_espacial.md` |
| [Sensibilidade hidrológica: a física simplificada acrescenta informação ao índice atual?](sensibilidade_hidrologica.md) | Sensibilidade hidrológica: pergunta se a física simplificada acrescenta informação ao índice atual. | `docs/sensibilidade_hidrologica.md` |

## Dados, fontes e base legal

| Documento | Finalidade | Localização |
|---|---|---|
| [Auditoria das fontes municipais de drenagem, uso do solo, relevo e risco (Porto Alegre)](auditoria_fontes_drenagem_poa.md) | Auditoria das fontes municipais de drenagem, uso do solo, relevo e risco. | `docs/auditoria_fontes_drenagem_poa.md` |
| [Base legal e origem dos dados da Prefeitura de Porto Alegre](base_legal_dados.md) | Decreto Municipal 20.315/2019 invocado, origem de cada conjunto da Prefeitura e atribuição. | `docs/base_legal_dados.md` |
| [Catálogo do acervo de dados do projeto](catalogo_dados.md) | Catálogo do acervo: origem, derivados, layout no R2 e condição de acesso. | `docs/catalogo_dados.md` |
| [Inventário de fontes, dados derivados e ferramentas](inventario_fontes.md) | Inventário de fontes, dados derivados e ferramentas. | `docs/inventario_fontes.md` |
| [Inventário e matriz de disponibilidade das fontes (25/11/2026)](inventario_fontes_poa.md) | Matriz de disponibilidade das fontes de Porto Alegre (25/11/2026). | `docs/inventario_fontes_poa.md` |
| [Fase 2: qualidade dos dados integrados e cobertura territorial](qualidade_dados_fase2.md) | Qualidade dos dados integrados e cobertura territorial (Fase 2). | `docs/qualidade_dados_fase2.md` |
| [Referências bibliográficas](referencias_bibliograficas.md) | Referências bibliográficas do estudo (ABNT). | `docs/referencias_bibliograficas.md` |

## GeoAI (camada E)

| Documento | Finalidade | Localização |
|---|---|---|
| [Camada E: fração construída estimada (GeoAI, experimental)](geoai_camada_e.md) | A camada E no produto: o que é, o que não é, resultados, limites, arquivos e como gerar. | `docs/geoai_camada_e.md` |
| [Fase 5: GeoAI para a fração construída por célula de 30 m](geoai_fase5.md) | Fase 5: o experimento GeoAI (decisão, aderência, fontes, limites e pendências). | `docs/geoai_fase5.md` |
| [Resultados do experimento GeoAI (Fase 5)](geoai_resultados.md) | Resultados do experimento GeoAI (gerado a partir de reports/qa/geoai_resultados.json). | `docs/geoai_resultados.md` |

## Publicação, infraestrutura e cache

| Documento | Finalidade | Localização |
|---|---|---|
| [Publicação: Cloudflare Pages (aplicação) e R2 (dados)](deploy_cloudflare.md) | Publicação no Cloudflare Pages (aplicação) e R2 (dados): passo a passo. | `docs/deploy_cloudflare.md` |
| [Arquitetura de publicação: GitHub Pages, Releases e distribuição de dados](publicacao_pages_releases.md) | Arquitetura de publicação: Pages, Releases e distribuição de dados. | `docs/publicacao_pages_releases.md` |
| [R2, cache HTTP e CDN: preparação dos dados para a publicação](r2_cache.md) | R2, cache HTTP e CDN: preparação dos objetos, cabeçalhos, validação e medições. | `docs/r2_cache.md` |

## Qualidade, auditorias e requisitos

| Documento | Finalidade | Localização |
|---|---|---|
| [Auditoria de escopo: o produto ativo é só Porto Alegre](auditoria_escopo_porto_alegre.md) | Auditoria de escopo: o produto ativo é só Porto Alegre. | `docs/auditoria_escopo_porto_alegre.md` |
| [Auditoria final, testes e preparação para 01/12/2026](auditoria_final_2026-11.md) | Auditoria final, testes e preparação para 01/12/2026. | `docs/auditoria_final_2026-11.md` |
| [Aderência aos requisitos oficiais do Capstone (FTL Brasil, Space Tech Bootcamp 2026)](capstone_requisitos.md) | Aderência aos requisitos oficiais do Capstone (FTL Brasil). | `docs/capstone_requisitos.md` |
| [Fase 4.1: auditoria, desempenho e preparação para demonstração](fase41_auditoria.md) | Fase 4.1: auditoria, desempenho e preparação para a demonstração. | `docs/fase41_auditoria.md` |
| [Relatório final de QA e matrizes de aceite](qa_relatorio_final.md) | Relatório final de QA e matrizes de aceite. | `docs/qa_relatorio_final.md` |

## Apresentação e proposta

| Documento | Finalidade | Localização |
|---|---|---|
| [Demonstração controlada: do preparo ao encerramento](demonstracao.md) | Demonstração controlada: do preparo ao encerramento. | `docs/demonstracao.md` |
| [Proposta de Projeto Final — Future Tech Leaders Brasil · Space Tech Bootcamp 2026 (estudo preliminar)](proposta.md) | Proposta do projeto final (FTL Brasil, Space Tech Bootcamp 2026). | `docs/proposta.md` |
| [Roteiro de apresentação do capstone](roteiro_apresentacao.md) | Roteiro de apresentação do capstone. | `docs/roteiro_apresentacao.md` |
| [Roteiro da apresentação curta (template FTL)](roteiro_apresentacao_curta.md) | Roteiro da apresentação curta (template FTL). | `docs/roteiro_apresentacao_curta.md` |
| [Síntese para a apresentação acadêmica: resultados, limites e conclusão](sintese_academica.md) | Síntese acadêmica: resultados, limites e conclusão. | `docs/sintese_academica.md` |

## Histórico: frentes arquivadas

| Documento | Finalidade | Localização |
|---|---|---|
| [Avisos para o cidadão, áreas em exposição e o laço da comunidade](avisos_comunidade.md) | Avisos ao cidadão e laço da comunidade (frente de mobilidade arquivada). | `docs/avisos_comunidade.md` |
| [Coletor dos bloqueios da CPRv BM](coletor_crbm.md) | Coletor dos bloqueios da CPRv BM (frente estadual arquivada). | `docs/coletor_crbm.md` |
| [Contrato de dados: eventos e cenários](events_contract.md) | Contrato de dados de eventos e cenários (frente anterior). | `docs/events_contract.md` |
| [Extração de eventos a partir de texto (Fase 1)](extracao.md) | Extração de eventos a partir de texto (Fase 1, arquivada). | `docs/extracao.md` |
| [Guia de uso: painel (desktop) e PWA (celular)](guia_de_uso.md) | Guia de uso do painel e do PWA (PWA arquivado). | `docs/guia_de_uso.md` |
| [Hospedagem do servidor](hospedagem.md) | Hospedagem do servidor (frente anterior). | `docs/hospedagem.md` |
| [Gatilho municipal de risco hídrico: dados, método e resultados (estrito)](ml_gatilho.md) | Gatilho municipal de risco hídrico (frente estadual arquivada). | `docs/ml_gatilho.md` |
| [Operação de ocorrências: como confirmar, declarar impacto e corrigir](operacao_ocorrencias.md) | Operação de ocorrências (frente de monitoramento arquivada). | `docs/operacao_ocorrencias.md` |
| [Flooding Mapping: inteligência territorial e mobilidade preventiva](produto_preventivo.md) | Inteligência territorial e mobilidade preventiva (frente arquivada). | `docs/produto_preventivo.md` |
| [Proposta técnica: assistente territorial (futuro, não implementado)](proposta_assistente_territorial.md) | Proposta de assistente territorial (futuro, não implementado). | `docs/proposta_assistente_territorial.md` |
| [Publicação da interface estadual (GitHub Pages)](publicacao.md) | Publicação da interface estadual no GitHub Pages (arquivada). | `docs/publicacao.md` |
| [QA em dispositivo físico (celular)](qa_mobile_fisico.md) | QA em dispositivo físico (PWA arquivado). | `docs/qa_mobile_fisico.md` |
| [Hospedagem no Render: preparação, custos e checklist](render.md) | Hospedagem no Render: preparação, custos e checklist (frente anterior). | `docs/render.md` |
| [Roadmap — Flooding Mapping (escopo estadual, RS)](ROADMAP.md) | Roadmap histórico (escopo estadual). | `docs/ROADMAP.md` |
| [Segurança e proteção de dados: controles, riscos e pendências](seguranca_lgpd.md) | Segurança e proteção de dados da frente de rotas e relatos (arquivada). | `docs/seguranca_lgpd.md` |
| [Validação do provedor de linguagem (Gemini)](validacao_gemini.md) | Validação do provedor de linguagem (frente de extração arquivada). | `docs/validacao_gemini.md` |

## Raiz do repositório

| Arquivo | Finalidade | Localização |
|---|---|---|
| `README.md` | Visão geral do projeto, como rodar e a tabela de fontes. | `README.md` |
| `LICENSE` | Licença do código (MIT). | `LICENSE` |

