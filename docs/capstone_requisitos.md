# Aderência aos requisitos oficiais do Capstone (FTL Brasil, Space Tech Bootcamp 2026)

Referência: o documento "Projeto Final (Capstone Project): Requisitos Mínimos" enviado pela autora em 26/11/2026. Ele **substitui como referência prioritária** a lista de 14 itens usada em `docs/qa_relatorio_final.md` (Matriz A) e na seção 3 de `docs/geoai_fase5.md`, que eram requisitos compartilhados antes e não o texto oficial. Nada foi publicado, commitado ou enviado para produzir esta matriz.

Estados: **Concluído**, **Parcial**, **Pendente**. Cada linha diz o que existe, o que falta e quem decide.

## 1. Requisitos mínimos (7 itens oficiais)

| # | Requisito oficial | Evidência existente | Situação | O que falta |
|---|---|---|---|---|
| 1 | Introdução e contextualização | `docs/proposta.md` §1 e §2 (ODS 11, metas 11.2 e 11.5, e clima); `README.md`; landing `/inicio/` | **Parcial** | A proposta e os `.docx` tratam só da mobilidade; falta realinhar ao escopo atual (escoamento, simulador, GeoAI) |
| 2 | Revisão da literatura, no mínimo 2 artigos | `docs/proposta.md` §3: Coles et al. (2017), Green et al., Pregnolato et al., Latora e Marchiori (2001), r5py | **Parcial** | Cobre o escopo de **mobilidade**. Para escoamento e GeoAI só há referências consultadas (`docs/geoai_fase5.md` §14), sem parágrafos de revisão. Candidatos já lidos em resumo: AlphaEarth (arXiv:2507.22291) e Prithvi-EO-2.0 (arXiv:2412.02732); a tabela 4-10 do manual de hidráulica da TxDOT sustenta os coeficientes. Falta ler os textos completos e escrever de 2 a 5 parágrafos |
| 3 | Metodologia | `docs/ml_gatilho.md` (seções marcadas "template 3.1 a 3.6"), `docs/fase3_motor.md`, `docs/geoai_fase5.md` | **Concluído** | — |
| 4 | Resultados (produto) | WebGIS 3D/2D com PWA, aba Resultados, Simulador, landing `/inicio/`, dashboard | **Concluído** | — |
| 5 | Implementação/deploy | Serviço no Render em `flooding-mapping-capstone.onrender.com` (11/11/2026, validação remota parcial: `docs/render.md`); workflow `publicar-site.yml` desenhado; hospedagem estática planejada em `docs/publicacao_pages_releases.md` | **Parcial** | O que está no ar é o escopo de mobilidade. As Fases 3 a 5 só existem localmente; a publicação (Pages com os dados no artefato) depende de **autorização** e de medir o prazo de 10 min do Pages |
| 6 | Código open source | Licença MIT (`LICENSE`); `origin` aponta para `helenavalanera/flooding-mapping-capstone`; histórico de 104 commits | **Parcial** | **188 entradas locais sem commit** (Fases 3 a 5 e ajustes); visibilidade pública do repositório não verificada; depende de **autorização** para commit e push |
| 7 | Apresentação oral (ou vídeo gravado) | `docs/apresentacao/Flooding_Mapping_Capstone_FTL_v2.pptx` (13 slides), `docs/roteiro_apresentacao_curta.md` | **Parcial** | Os slides cobrem mobilidade e experimentos; **não cobrem** as Fases 3 a 5 nem a GeoAI. Data da apresentação na última semana do programa: não informada; o vídeo é alternativa permitida |

**Resumo:** 2 concluídos e 5 parciais; nenhum pendente. Os parciais são de **material e de publicação**, não de método.

## 2. Conteúdo exigido, seção a seção

| Seção oficial | Onde está | Situação |
|---|---|---|
| 1. Introdução: problema, tarefa, objetivo, ODS | `proposta.md` §1 e §2; `README.md` | Parcial (escopo anterior) |
| 2. Literatura (2 a 5 parágrafos) | `proposta.md` §3 | Parcial (ver acima) |
| 3.1 Dados: formato, finalidade, acesso, restrições, publicação (Hugging Face, Zenodo) | Tabela de fontes do `README.md`; `docs/inventario_fontes_poa.md`; `docs/geoai_fase5.md` §5 | **Parcial**: faltam decidir se algum dado derivado será publicado. A Profill tem licença de reuso **não confirmada**, o que impede publicar derivados dela (inclusive o COG da GeoAI) |
| 3.2 ETL, limpeza, EDA, transformação, features | `docs/qualidade_dados_fase2.md`, `docs/ml_gatilho.md` §2, `docs/geoai_fase5.md` §6 | Concluído |
| 3.3 Seleção do modelo, vantagens, limites, alternativas | `docs/ml_gatilho.md` §3; `docs/geoai_fase5.md` §6 e §7 | Concluído |
| 3.4 Treinamento e tabela de hiperparâmetros | `docs/ml_gatilho.md` §4; `docs/geoai_fase5.md` §6 (tabela adicionada em 26/11/2026) | Concluído |
| 3.5 Validação cruzada | `docs/ml_gatilho.md` §5; `docs/geoai_fase5.md` (blocos espaciais P1 e P2) | Concluído |
| 3.6 Avaliação com métricas e gráficos | `docs/ml_gatilho.md` §6; `docs/geoai_resultados.md` | Concluído |
| 4. Deployment | Seção 1, item 5 | Parcial |
| 5. Código: README com objetivo, estrutura, instalação, execução, reprodução; trechos comentados | `README.md` (seção Escoamento e GeoAI), módulos comentados | **Parcial**: a introdução do README ainda é só mobilidade |
| 6. Produto final (WebGIS, dashboard open source, relatório com página HTML) | WebGIS e PWA em MapLibre, Leaflet e Python (sem ferramenta paga); landing como relatório em HTML | Concluído |

## 3. Divergências em relação à matriz anterior

- A lista anterior (14 itens) tinha critérios que o texto oficial não cita separadamente (limitações, validação, GIS e sensoriamento remoto) e **não** tinha dois dos sete requisitos mínimos como itens próprios: **revisão da literatura com ao menos 2 artigos** e **apresentação oral ou em vídeo** (o último constava como "apresentação"). Ao aplicar a lista oficial, a revisão da literatura passa de "não avaliada" a **parcial**.
- O texto oficial pede **tabela de hiperparâmetros** (3.4) e **perguntas sobre publicação dos dados** (3.1): a primeira foi acrescentada à documentação da GeoAI; a segunda depende de decisão da autora.
- Entre os formatos de produto final, o projeto já cumpre WebGIS e relatório com página HTML. **Dataset** em Hugging Face ou Zenodo seria outro caminho; a regularização documental da Profill é conduzida à parte pela responsável.

## 4. Ações priorizadas (nenhuma foi executada)

1. **Autorização para commit e push** das Fases 3 a 5 (requisito 6 e base do 5). Sem isso o código aberto não reflete o projeto.
2. **Escrever a revisão da literatura** do escopo atual (2 a 5 parágrafos) depois de ler os textos completos; hoje só há resumos consultados.
3. **Realinhar introdução e README** ao escopo de escoamento e GeoAI (requisitos 1 e documentação).
4. **Publicar** o que for possível: decisão da hospedagem (`docs/publicacao_pages_releases.md`), com medição do prazo do Pages.
5. **Atualizar os slides ou gravar o vídeo** com as Fases 3 a 5 e a GeoAI, e confirmar a data da apresentação.
6. Concluir, à parte e pela responsável, a regularização documental da Profill (derivados agregados já publicados com atribuição).
