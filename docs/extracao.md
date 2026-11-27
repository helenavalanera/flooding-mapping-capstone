# Extração de eventos a partir de texto (Fase 1)

Objetivo: ampliar a base de rótulos do modelo de suscetibilidade e do gatilho municipal, hoje limitada (19 pontos da EPTC, sem negativos,
com viés de notificação). Um modelo de linguagem **lê** boletins, notícias e relatos e propõe eventos; uma pessoa revisa; só o que foi revisado
vira rótulo. O modelo nunca estima risco e nunca grava nada sozinho.

## Fluxo

```
documentos (JSON) ──► extrair ──► validador ──► fila de revisão ──► revisão humana ──► rótulos (peso) ──► retreino (Fase 2)
   só fontes            LLM        citação         pendente          aceitar /            fora do                comparação
   autorizadas      (esquema       literal,                          corrigir /           armazenamento           com o modelo
                     fechado)      data, local                       rejeitar             de ocorrências          atual
```

| Peça | Arquivo |
|---|---|
| Esquema, instruções ao modelo e validador | `src/flooding_mapping/extracao/esquema.py` |
| Extração de um documento (fonte autorizada, orçamento de chamadas) | `extracao/extrator.py` |
| Geocodificação por nome de via (só Porto Alegre hoje) | `extracao/geocodificador.py` |
| Fila de revisão e exportação de rótulos | `extracao/fila.py` |
| Precisão contra anotação manual | `extracao/precisao.py` |
| Linha de comando | `python -m flooding_mapping.extracao.cli` |
| Fontes e permissões | `config/fontes_extracao.json` (**vazio**: nenhuma fonte autorizada ainda) |

## Garantias, e como cada uma é testada (`tests/test_extracao.py`)

- **Evento inventado não passa.** Cada candidato traz `trecho_fonte`, a citação do texto que o sustenta; se ela não aparece literalmente no
  texto (ignorando maiúsculas, acentos e espaços), o candidato é rejeitado antes de chegar ao revisor. Quem revisa confere a citação em segundos.
- **Previsão não é ocorrência.** A instrução exclui avisos e previsões; data futura ou posterior ao texto é rejeitada.
- **Texto é dado, não instrução.** Vai no turno do usuário, nunca nas instruções; a saída é forçada a um esquema com vocabulário fechado.
- **Fonte sem autorização não é lida.** `permitida` é decisão da autora sobre licença e termos de uso; sem ela, nenhuma chamada é feita.
- **Revisão tem nome.** Sem revisor identificado não há revisão; uma correção é validada de novo; o que foi rejeitado nunca vira rótulo.
- **Rótulos ficam separados das ocorrências ao vivo.** São histórico para treino e validação; não elevam o risco de nenhuma rua hoje.
- **Custo controlado.** Teto de chamadas por rodada; documento já enviado ao modelo (mesmo sem eventos) não é reenviado; falha do modelo deixa
  o documento para a próxima rodada, nunca vira "zero eventos".
- **Peso por fonte.** Boletim oficial 1,0; notícia 0,5; relato 0,3; correção humana pesa mais que aceite direto.

## Precisão

`python -m flooding_mapping.extracao.cli precisao anotacoes.jsonl` roda o extrator numa amostra anotada à mão e grava
`reports/qa/extracao_precisao.{json,md}`: precisão, cobertura, acerto por campo (data, tipo, severidade, impacto) e por fonte.
Uma fonte só entra no treino com precisão acima do limiar (**provisório: 85%**, a combinar) e ao menos 20 eventos anotados.
O número vale para a versão do prompt registrada no relatório.

## Limites que precisam constar nos textos do projeto

- A precisão mede a **extração** contra a anotação manual, não a verdade sobre o alagamento.
- Notícias cobrem mais o centro e os grandes eventos: o viés de notificação continua, e pode piorar.
- Só Porto Alegre tem tabela de ruas; eventos de outros municípios ficam com município e data, úteis ao gatilho municipal, sem coordenada.
- Nome de via não é ponto: via muito longa (mais de 6 km) ou ambígua fica sem coordenada.
- Nada disto foi executado contra um provedor real nem contra anotações reais: **faltam as fontes autorizadas e a amostra anotada**.

## Privacidade

Os textos são públicos ou institucionais. Relatos de cidadãos só entram com o consentimento já previsto no app e sem identificadores; o modelo
não recebe localização nem dados pessoais (ver `docs/seguranca_lgpd.md`).
