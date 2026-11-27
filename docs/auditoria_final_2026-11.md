# Auditoria final, testes e preparação para 01/12/2026

Estado de partida: branch `develop`, último commit `dceb39b`, 81 entradas de alterações locais anteriores (preservadas). Nada foi commitado, enviado nem publicado.

## A. Auditoria

### Experimento de sensibilidade hidrológica

| Item | Resultado |
|---|---|
| Bootstrap pareado | Confirmado: os mesmos positivos reamostrados valem para todos os modelos. Uma cópia idêntica da regra dá ganho 0 com intervalo de largura 0 (teste) |
| Bootstrap por blocos | **Falha encontrada e corrigida.** Só reamostrava blocos com positivos e mantinha os negativos fixos. Agora há a versão por conglomerados (blocos inteiros com seus negativos), conferida contra uma reamostragem por força bruta. O critério exige as três formas (trecho, blocos de positivos, blocos completos) |
| Normalização e vazamento | Sem vazamento encontrado: a padronização do D2 está no pipeline, ajustada só no treino de cada dobra; D1, densidade viária e postos não usam rótulos. Limitação registrada: os escores do D2 vêm de modelos diferentes por dobra e são agrupados |
| Métricas | **Falha encontrada e corrigida:** o ganho era calculado com a precisão média arredondada a 5 casas (erro de até ~0,25%). Agora usa o valor exato. AUC e AP continuam reportadas separadas; nenhuma diferença de AUC é lida como superioridade |
| Amplitude do D1 | Real e estável (não muda com a semente nem com 20.000 réplicas): a AP depende de poucos positivos muito bem posicionados |
| Faixas de C | Conferidas em manuais de agências (TxDOT, San Diego County). O livro de Chow, Maidment & Mays **não foi consultado diretamente** |

### Achados de engenharia

| Gravidade | Achado | Situação |
|---|---|---|
| **Crítico** | `requirements-servidor.txt` não listava `shapely` nem `scikit-learn`, que o servidor importa na inicialização. A imagem Docker não subiria (`ModuleNotFoundError`, reproduzido). O deploy anterior no Render é anterior a esses módulos | **Corrigido**: pacotes fixados nas versões do `requirements.lock.txt`; novo teste simula a imagem e falha sem eles |
| Médio | O arquivo do território e os pontos de interesse não vão na imagem (`data/` está fora do Git e do `.dockerignore`). No deploy, bairros, bolsões e pontos de interesse ficam ausentes e o serviço roda sem essas camadas, sem erro | Pendente (decisão) |
| Médio | Duas amostras de validação em circulação: 105 trechos e AUC 0,675 (ferramenta antiga) contra 124 e 0,666 (experimentos finais). A diferença vem do rótulo: o segmento mais próximo de toda a rede, ou só dos segmentos com os cinco componentes | Documentado; o deck e os relatórios finais usam só 124 e 0,666 |
| Médio | O deck não mencionava os experimentos nem o limite do DSM de ~30 m, e dizia "detectou 4 de 19" sem dizer que só 2 foram detectados na hora do relato | Corrigido no gerador (ver E) |
| Baixo | `h=nan`, `inf` ou valores enormes nos endpoints de previsão não dão erro: são limitados a 0–48 h, e `nan` vira "agora". O corpo informa a hora e a natureza usadas | Aceito; sem mudança |
| Baixo | Arquivo de bloqueio `~$Flooding_Mapping_Capstone_FTL.pptx` na pasta da apresentação (do PowerPoint, de 24/11) | Não alterei o `.pptx` existente |
| Baixo | O teste de navegador do painel levou 426 s com a máquina em carga alta (média 14) | Registrado |

**O que foi lido e não apresentou problema:** corpo limitado a 8 KB; limite de requisições por cliente; falhas de credencial de operador limitadas; token de operador com mínimo de 24 caracteres; política de segurança de conteúdo; sem registro de acesso (comentário no código: carregaria lugares e horários); métricas só por grupo de rota; erros internos sem rastro na resposta; JSON estrito (NaN vira erro 500, não chega ao cliente); download de arquivos com HTTPS, limite de tamanho e SHA-256; contêiner com usuário sem privilégios e health check.

**LGPD, o que verifiquei no código e nos dados:** a base de teste contém só coordenadas públicas (127 pontos), sem nome nem telefone; o apoio da comunidade guarda apenas um hash; os lugares enviados não têm nome. **Não verifiquei:** revisão jurídica formal, licenças de reuso dos dados da Prefeitura e do Open-Meteo, e o comportamento real do serviço publicado (nada está publicado).

## B. Testes

Execução completa, com as variáveis do navegador definidas (`PLAYWRIGHT_CORE`, `CHROME_PATH`):

- **595 aprovados, 1 ignorado, 0 reprovados, 0 erros, 672,75 s.**
- O ignorado é `tests/test_r2.py:120`: falta o pacote `boto3` (envio ao Cloudflare R2, não usado hoje).
- Os 3 testes de `tests/test_requisitos_servidor.py` foram criados **depois** do início dessa execução e, por isso, não entraram nela. Rodaram à parte, com `tests/test_r2.py`: 12 aprovados, 1 ignorado.
- Cobertura da suíte: unitários, integração, geoespaciais, API, segurança, experimentos e frontend (Chrome real).

## C. Robustez espacial

Detalhes em [robustez_espacial.md](robustez_espacial.md). Resumo, com a regra atual como referência:

- **Blocos de 1, 1,5, 2 e 3 km, com 4 origens de grade cada (16 configurações):** 12 cumprem os pontos de estabilidade fixados antes (≥ 20 blocos com positivos, maior bloco ≤ 25%, número efetivo ≥ 15). As 4 de 3 km ficam registradas com a limitação (número efetivo de 12,5 a 14,6).
- **Nenhuma configuração atende o critério de adoção.** Ganho do B: −9,9% em todas (não depende do bloco). D1: +2,2% a +5,7% em todas. D2: de −18,6% a +0,8%, ou seja, depende da grade.
- **Leave-one-block-out (53 blocos):** nenhum atinge a margem de 10% (maior ganho: +9,96%, D1). O sinal do ganho do D1 troca ao retirar 1 ou 2 blocos; o do D2, 1 bloco; o do B nunca troca (sempre negativo).
- **Bloco com 18 positivos:** sem ele, D1 vai de +2,2% a −0,04% (uniforme), e o B piora para −18,7%.
- A ordem de precisão média entre os modelos assume **6 formas distintas** conforme o bloco retirado.
- **Interpretação:** a decisão de não adotar é estável. Qualquer ganho do D1 ou do D2 não é estável e não deve ser lido como evidência. Estabilidade não é superioridade.

## D. Documentação alterada ou criada

| Arquivo | Justificativa |
|---|---|
| `tools/experimento_sensibilidade_hidrologica.py` | Correções da auditoria (bootstrap completo, ganho exato, função `preparar`, distribuição dos positivos) |
| `tools/robustez_espacial_validacao.py`, `tests/test_robustez_espacial.py` | Fase 2 |
| `tests/test_experimento_sensibilidade.py` | Testes novos de pareamento, bootstrap por conglomerados e distribuição dos positivos |
| `tests/test_requisitos_servidor.py`, `requirements-servidor.txt` | Correção do problema crítico de deploy |
| `reports/qa/sensibilidade_hidrologica.json`, `docs/sensibilidade_hidrologica.md`, `reports/qa/robustez_espacial.json`, `docs/robustez_espacial.md` | Relatórios regenerados; a versão anterior está em `reports/qa/sensibilidade_hidrologica_v1_antes_da_auditoria.json` |
| `tools/gerar_apresentacao_ftl.py`, `docs/roteiro_apresentacao_curta.md` | Slides de validação e experimento complementar, com números lidos dos relatórios |
| `docs/proposta_assistente_territorial.md` | Fase 8 |
| `docs/auditoria_final_2026-11.md` | Este relatório |

## E. Revisão da apresentação

- **Gerado:** `docs/apresentacao/Flooding_Mapping_Capstone_FTL_v2.pptx`, 13 slides. O arquivo `Flooding_Mapping_Capstone_FTL.pptx` existente não foi tocado.
- **Inconsistências encontradas e corrigidas:** ausência dos experimentos e da validação; limite do DSM de ~30 m só implícito ("relevo Copernicus"); "4 de 19" sem o detalhe de que 2 foram detectados na hora do relato; nenhuma distinção entre suscetibilidade, exposição, ocorrência e previsão.
- **Conferido:** os números dos dois slides novos vêm dos JSONs (não são digitados); "4 de 19", 1.720 pontos de interesse e 176 mil trechos conferem com os dados. Os números de mobilidade (26,2 mm, 14 dias, 3,5%, 7%, 190 mil, 79%) constam em `docs/proposta.md`; **não os recalculei nesta etapa**.
- **Não foi possível:** a revisão visual por renderização. O LibreOffice não está instalado (o `soffice` é um atalho quebrado). Fiz só uma estimativa de espaço do texto, que não aponta estouro nos slides novos. **Abra o v2 no PowerPoint ou no Keynote antes de enviar.**
- **Duração:** a fala dos slides 3 a 12 passou a cerca de 7,4 min. Se o tempo da FTL for menor, o corte mais fácil é o slide dos ODS ou o de plataforma em uso.

## F. Checklist de deploy

**Pronto:** Dockerfile com usuário sem privilégios e health check em `/api/saude`; `deploy/render.yaml` inerte com `autoDeploy: false`; tabela de ruas e mapa-base por URL com SHA-256; porta dinâmica; token de operador; dependências agora cobertas (com teste).

**Impede ou limita a publicação:**
1. **Decidir como levar `territorio_poa.json` e `pois_poa.parquet` ao deploy** (embutir na imagem, que exige tirá-los do `.dockerignore`, ou servir por URL com SHA-256, o que exige código novo). Sem isso, bairros e pontos de interesse não aparecem.
2. **Memória do plano gratuito (512 MB):** o servidor passou a carregar shapely e scikit-learn (+~65 MB medidos aqui). Não medi o consumo total no contêiner; testar antes de publicar.
3. **Reconstruir a imagem e fazer um teste de inicialização**: a imagem nunca foi construída com as dependências corrigidas (Docker não foi executado nesta sessão).
4. **Persistência:** no plano gratuito, as ocorrências não sobrevivem a reinício. Plano pago com disco ou aceitar a limitação.
5. Definir `PROXIES_CONFIAVEIS`, `OPERADOR_TOKEN` (≥ 24 caracteres), `FM_REDE_URL`/`SHA256` e `FM_MAPA_URL`/`SHA256` no painel.
6. Revisão de LGPD e de licenças antes de abrir ao público.

Nada foi publicado.

## G. Roadmap de evolução

**Direção estratégica discutida:** tornar o motor de análise condicionado à precipitação, estimando a propensão ao acúmulo de água sob cenários de chuva, e tratar o índice atual como baseline. O experimento feito **não testou** essa hipótese: usou chuva uniforme, que só escala o volume sem reordenar as ruas.

Pré-requisitos, nesta ordem de importância:
1. **Eventos datados** (data, hora, local) com chuva associada: pedidos à Defesa Civil, ao 156 (e-SIC) e ao ObservaPOA, e a análise das camadas de inundação de 2024, se baixáveis.
2. **Chuva com distribuição espacial e temporal** (radar, estações, previsão arquivada) em lugar da série única regional de ~10 km. Sem previsão histórica arquivada, só dá para explicar eventos passados, não validar previsão.
3. **DEM de melhor resolução** e atributos hidrológicos (depressões, área contribuinte, conectividade).
4. **Componente urbano real:** impermeabilização, cobertura do solo, drenagem (bueiros, galerias, capacidade). Sem dados, nada de proxy apresentado como medida.
5. **Validação:** coerência espacial e sensibilidade primeiro; comparação com ocorrências quando houver dados temporais.

**Posicionamento para 01/12:** exposição estimada (terreno e chuva prevista regional). O motor condicionado à chuva entra como hipótese central da próxima etapa, não como entregue. **Decisão sua pendente.**

**ML:** só depois de dados temporais e rótulos de ausência verificados. **IA generativa:** conforme [proposta_assistente_territorial.md](proposta_assistente_territorial.md). **Infraestrutura:** resolver o item 1 do checklist, medir a memória e só então escolher a hospedagem.

## H. Resumo executivo

**Concluído:** auditoria do experimento (duas falhas corrigidas); robustez espacial (16 configurações e 53 retiradas de bloco); suíte completa (595 aprovados, 1 ignorado, 0 falhas); correção de um problema crítico de deploy, com teste; deck v2 com os slides de validação; proposta do assistente; checklist de deploy.

**Pendente:** conferência visual do deck v2; levar os dados do território e dos pontos de interesse ao deploy; construir e testar a imagem; revisão de LGPD e licenças; pedidos de dados; commit.

**Crítico:** o das dependências do servidor, já corrigido. Nenhum outro crítico ou alto encontrado.

**Riscos conhecidos:** sinal de terreno modesto (AUC 0,666) com rótulos de 2013–2014, sem chuva; resultados do D1 e D2 instáveis; DSM de ~30 m; chuva regional única; memória no plano gratuito; números de mobilidade do deck não recalculados nesta etapa.

**Precisa de decisão humana:** posicionamento do deck; como levar o território ao deploy; hospedagem e plano; tempo disponível da apresentação (7,4 min de fala); abrir ou não os pedidos de dados.

## Mensagem de commit sugerida (não executada)

```
feat(validacao): experimentos exploratórios, robustez espacial e correção de dependências do servidor

- experimentos de modelos e de sensibilidade hidrológica, com bootstrap pareado por trecho e por blocos
- robustez da validação espacial: tamanho do bloco, origem da grade e leave-one-block-out
- requirements-servidor: shapely e scikit-learn, com teste que simula a imagem
- gerador do deck: slides de validação e experimento complementar, com números lidos dos relatórios
- docs: auditoria final, robustez espacial e proposta do assistente territorial
```
