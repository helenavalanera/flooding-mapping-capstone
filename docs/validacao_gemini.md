# Validação do provedor de linguagem (Gemini)

Este documento registra o que foi verificado em **chamadas reais** ao provedor e o que não foi. A chave nunca aparece aqui, em
código ou em log: ela fica em `.env` (`GEMINI_API_KEY`), fora do Git, e segue ao provedor no cabeçalho `x-goog-api-key`.

## Papel do provedor

O provedor **só reformula**. Toda pergunta sugerida tem uma resposta determinística montada a partir de um resumo estruturado
(sem coordenadas, com a lista do que está faltando). Sem chave, ou se o provedor falhar, a pessoa recebe esse texto padrão e a tela
diz isso. O provedor não calcula rota, não classifica trecho, não confirma ocorrência e não altera risco.

O texto devolvido passa por validação antes de chegar à tela: vazio ou acima de 900 caracteres é recusado, e também qualquer texto com
"seguro", "segura", "sem risco", "livre de risco", "garantido" ou "sem perigo" (o filtro é estrito e rejeita até a negação). Recusado,
vale o texto padrão. Resposta cortada (`MAX_TOKENS`) conta como falha. A validação **não** confere números nem fatos: ela garante
formato, tamanho e as palavras proibidas, e o que o provedor pode dizer é limitado pelo resumo que recebe.

## Configuração testada

| Item | Valor |
|---|---|
| Modelo | `gemini-3.6-flash` (variável `GEMINI_MODELO`) |
| Interface | REST `generateContent`, `functionDeclarations`, `responseSchema` |
| Raciocínio | `thinkingLevel: minimal` (variável `GEMINI_PENSAMENTO`) |
| Cache de respostas | 15 min, por contexto e pergunta |
| Limite local | 20 chamadas por minuto |
| Dados enviados | resumos agregados (tempos, classes, horas, lacunas), sem origem, destino ou coordenadas |

## O que foi observado em chamadas reais

Todas as chamadas abaixo usaram a rede de ruas real de Porto Alegre com uma **chuva sintética de demonstração** (servidor de
demonstração: uma tempestade inventada, em memória, que se declara sintética na fonte). Os valores de chuva e de risco que aparecem
nas respostas são, portanto, do cenário de teste, **não** dados do mundo.

1. **Chamada de configuração:** respondeu; o servidor registra apenas "provedor configurado: sim".
2. **Explicação de uma análise de rotas:** resposta do provedor aceita pela validação; 1,9 s com `thinkingLevel: minimal`.
3. **Efeito do raciocínio:** sem controle, o modelo gastou 724–984 tokens de "pensamento" e a resposta chegou a 7,4 s; com
   `minimal`, o gasto de raciocínio foi zero e o tempo ficou entre 1,7 e 2,7 s. Uma resposta cortada no meio da frase, vista antes
   do ajuste, é o motivo de `MAX_TOKENS` ser tratado como falha.
4. **Assistente, perguntas sugeridas** (trecho, região, rota): respostas do provedor aceitas em 1,7–2,7 s, com 429–1.754 tokens de
   entrada e 100–213 de saída. Uma resposta foi **recusada pela validação** e o texto padrão foi entregue (`resposta_invalida`):
   o mecanismo funciona, e a pessoa vê a origem "texto padrão".
5. **Pergunta que exige dado novo** ("chuva por hora nas próximas 6 horas"): o modelo chamou a ferramenta `get_weather_forecast`
   (2 chamadas, 3,2–4,6 s) e respondeu com a série devolvida pelo serviço, dizendo que a chuva é regional (grade de cerca de
   10 km). Antes de o prompt pedir explicitamente o uso das operações, o modelo respondia sem chamar a ferramenta.
6. **Instrução embutida na pergunta livre:** a pergunta foi tratada como dado não confiável. O provedor respondeu dentro do escopo
   e **nenhuma interdição foi criada** (0 interdições ao fim do teste). O provedor só pode chamar operações de leitura, ligadas
   àquela análise; não existe operação de escrita ao seu alcance.
7. **Consumo no teste (4 chamadas):** 5.237 tokens de entrada, 492 de saída, 0 de raciocínio.

## O que não foi validado

- **Volume e custo reais:** não há medição de uso sustentado, nem de cota diária, nem de custo mensal.
- **Qualidade linguística ampla:** a amostra é pequena (as perguntas sugeridas e duas perguntas livres). Não há avaliação
  por pessoas, e a validação automática garante formato, tamanho e palavras proibidas, não clareza nem exatidão dos números.
- **Falha do provedor em produção:** o caminho de erro é coberto por testes automatizados (`tests/test_linguagem.py`), mas
  indisponibilidade prolongada do serviço não foi observada.
- **Chuva real:** as chamadas reais usaram chuva sintética; o comportamento com a previsão ao vivo é o mesmo código, mas não foi
  conferido com o provedor nessa condição.

## Como repetir

```bash
# .env: GEMINI_API_KEY=... (nunca no Git)
python -m flooding_mapping.servidor        # /api/saude mostra "provedor configurado"
pytest tests/test_linguagem.py tests/test_servico.py
```

O servidor de demonstração (`tests/e2e/servidor_demo.py`) só usa o provedor se `DEMO_GEMINI=1`, para que os testes automáticos
não dependam de rede nem gastem cota.
