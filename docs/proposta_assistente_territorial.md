# Proposta técnica: assistente territorial (futuro, não implementado)

> **Frente arquivada.** Proposta de uma frente futura, não implementada e fora do estudo atual.

Estado: **proposta**. Nenhuma IA generativa nova foi implementada nesta etapa.

## Princípio

O modelo generativo **explica, consulta e contextualiza**. Ele **não calcula** suscetibilidade, exposição nem rota, e não substitui o motor geoespacial. Todo número que aparece numa resposta vem de uma consulta ao backend, e a resposta cita de onde veio.

## O que já existe (ponto de partida)

Em `src/flooding_mapping/linguagem/`:

- `assistente.py`: perguntas por contexto (trecho, rota, município, rodovia). Cada pergunta tem **resposta determinística** montada a partir de um resumo estruturado, sem coordenadas, com a lista do que **falta** (`lacunas`). O provedor de linguagem só reescreve; sem ele, o produto funciona.
- `ferramentas.py`: **esquema fechado** de operações que o modelo pode pedir ao backend. Operação, argumento ou tipo desconhecido é recusado; a análise é amarrada à sessão (o modelo não escolhe outra); resultados com no máximo 4 KB, sem coordenadas, sem texto livre de usuários; nada cria, confirma ou altera ocorrência.
- `explicar.py`: instruções que tratam a pergunta e o texto dos relatos como **dado não confiável**, nunca como instrução. Valida a saída: recusa texto vazio, longo demais ou com palavras proibidas ("seguro", "garantido").
- `gemini.py`: adaptador do provedor (chave em cabeçalho, nunca na URL; tempo limite; contagem de uso). Sem chave, há texto padrão.

O que é novo na proposta é só o que falta abaixo.

## Camadas propostas

| Camada | Proposta | Justificativa de necessidade |
|---|---|---|
| Modelo | LLM por API externa, atrás do adaptador atual | Já existe; trocar de provedor é trocar uma classe |
| Consultas ao motor | Estender o esquema fechado com operações **somente leitura**: `exposicao_por_bairro`, `lugares_expostos`, `fontes_e_limites` | O motor já calcula; o modelo só consulta |
| Conhecimento | Busca sobre `docs/` e um índice curto de fontes oficiais, **por palavra-chave (BM25)** primeiro | O corpus tem poucas dezenas de documentos: embeddings e banco vetorial só entram se a busca por palavra-chave falhar numa avaliação |
| SQL parametrizado | **Não necessário agora** | Não há banco relacional: as ocorrências são um arquivo de linhas e os dados são tabelas em memória. Se houver banco, só consultas parametrizadas, com usuário de leitura |
| Agentes | **Não** | O esquema fechado com poucas operações basta |

## Respostas com fonte e rastreabilidade

Cada resposta devolve: o texto, a lista de evidências usadas (operação consultada ou documento e trecho), a hora do dado e o rótulo de natureza (**suscetibilidade do terreno**, **exposição estimada**, **ocorrência observada**; nunca "previsão de alagamento"). O validador atual (`explicar.py`) só recusa texto vazio, longo demais ou com palavras proibidas ("seguro", "garantido" e semelhantes). **Novo nesta proposta:** um validador determinístico que recusa a resposta se contiver número ou nome ausente das evidências.

## Perguntas sem evidência

Se nenhuma operação nem documento sustenta a resposta, o assistente diz que não tem como responder e indica o que falta (a lista de lacunas), em vez de completar com conhecimento geral. Perguntas sobre emergência recebem sempre o encaminhamento ao 199 antes de qualquer outra coisa.

## Proteção contra injeção de prompt

- A pergunta, os textos de relatos e os documentos recuperados entram como **dados**, em campos separados das instruções.
- O modelo só pode pedir operações do esquema fechado; não há ferramenta que escreva, confirme ou envie algo.
- Resultados limitados em tamanho e sem texto livre de usuários; documentos recuperados só do repositório (nunca de URL informada pela pessoa).
- Saída validada antes de ir à tela e renderizada como texto, nunca como HTML.
- Testes adversariais fixos (instruções dentro de relatos, de documentos e da pergunta) fazem parte da suíte.

## Avaliação de groundedness

Conjunto de perguntas fixo, com a evidência esperada para cada uma, incluindo perguntas **sem resposta possível**. Métricas: proporção de afirmações numéricas presentes nas evidências (meta 100%, aplicada pelo validador novo), precisão das citações, taxa de recusa correta nas perguntas sem evidência e taxa de resposta que muda de natureza (por exemplo, tratar exposição estimada como previsão). Roda na suíte com o provedor simulado e, antes de qualquer publicação, uma vez com o provedor real.

## Custo e latência

Resposta determinística primeiro; o modelo só quando a pessoa pede explicação. Limites: tamanho da pergunta (já 200 caracteres), tokens de saída, tempo limite, limite por cliente e orçamento diário com corte. Cache por contexto e hora. Se o provedor falhar ou estourar o orçamento, a resposta determinística continua valendo.

## Fora do escopo

Calcular ou ajustar suscetibilidade pelo modelo; prever alagamento; recomendar rota como segura; falar em nome da Defesa Civil; guardar histórico de conversas com dados pessoais.

## Decisões que cabem a você

1. Provedor e orçamento (o adaptador atual usa o Gemini).
2. Se há valor em abrir documentos oficiais além do repositório (exige curadoria e licença).
3. Se a avaliação de groundedness precisa de revisores humanos antes de qualquer publicação.
