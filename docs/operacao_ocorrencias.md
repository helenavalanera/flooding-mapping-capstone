# Operação de ocorrências: como confirmar, declarar impacto e corrigir

Este guia define o procedimento humano que o sistema pressupõe. **O sistema impõe o mecanismo (credencial, evidência escrita,
histórico); quem decide, e com que autoridade, é da instituição que operar o produto.** Os campos marcados **[PENDENTE DE APROVAÇÃO]**
dependem dessa definição externa e não foram inventados aqui.

## Princípios

1. Um relato de usuário **nunca** interdita uma via. Ele nasce `reportada`, com confiabilidade `baixa`.
2. Só uma **confirmação do operador, com evidência escrita**, muda a situação. Só `confirmada` com impacto `interdicao` bloqueia o trecho no cálculo de rotas, nos dois modais.
3. Toda decisão fica no histórico do registro (quem, quando, de qual situação para qual, com qual evidência). Nada é apagado: descartar também é uma decisão registrada.
4. Na dúvida, **não confirmar**. Um relato pendente continua visível como "pendente, sem verificação", e a rota apenas o ignora.

## Quem pode agir

| Ação | Quem | Mecanismo |
|---|---|---|
| Relatar | qualquer pessoa | PWA, aba Relatar; 10 por minuto por cliente |
| Ler o texto livre dos relatos | operador | o texto só é entregue com a credencial |
| Confirmar, descartar, declarar impacto | operador | `OPERADOR_TOKEN` + evidência (10 a 280 caracteres) |
| Quem é "operador" na prática | **[PENDENTE DE APROVAÇÃO]** (órgão, função e quantas pessoas) | hoje, quem detém o token |
| Quem guarda e troca o token | **[PENDENTE DE APROVAÇÃO]** | `.env` do servidor; troca exige reiniciar |

O token tem no mínimo 24 caracteres (`python -m flooding_mapping.servidor --gerar-token` gera um). Falhas de credencial são limitadas
a 8 por minuto por cliente.

## Evidências a consultar antes de confirmar

Registre na evidência **o que foi consultado**, não só a conclusão. Fontes possíveis, a critério da instituição **[PENDENTE DE APROVAÇÃO: lista oficial]**:

- vistoria no local ou imagem de câmera com data e hora;
- registro de órgão de trânsito ou de Defesa Civil;
- aviso de bloqueio de via publicado por fonte oficial;
- mais de um relato independente no mesmo ponto (indício, não prova).

Um único relato sem outra fonte não basta para interdição.

## Como confirmar (painel, aba Ocorrências, Porto Alegre)

1. Informe a credencial e entre como operador.
2. Localize o relato (o operador vê o texto livre) e clique em **Revisar**.
3. Escolha a situação: **Confirmar** ou **Descartar**.
4. Defina a **confiabilidade** (alta, média ou baixa) segundo a evidência.
5. Declare o **impacto na circulação**:
   - `interdicao`: a via está intransitável; **o trecho sai do cálculo das rotas**;
   - `parcial`: há restrição, mas a via passa; só eleva o risco estimado do trecho;
   - `nenhum`: sem efeito na circulação;
   - `desconhecido`: ainda não foi possível avaliar (não interdita).
6. Escreva a evidência e registre. A tela mostra a nova situação; as rotas calculadas dali em diante já consideram a decisão.

## Informações conflitantes

- Fontes discordam sobre a via estar fechada: **não declare `interdicao`**. Use `parcial` ou `desconhecido`, confiabilidade `baixa`, e descreva o conflito na evidência.
- Um relato diz "alagado" e outro "liberado": mantenha ambos `reportada`; confirme só quando houver evidência verificável.
- Relato duplicado: confirme um e descarte os demais, citando o registro confirmado na evidência.

## Corrigir uma confirmação incorreta

Não se edita nem se apaga o histórico. Para desfazer:

1. Abra o registro e use **Revisar** com situação **Descartar** (ou nova confirmação com impacto `nenhum`).
2. Na evidência, escreva o motivo da correção e referencie a decisão anterior.
3. As rotas voltam a usar o trecho no próximo cálculo.

## Quando remover uma interdição

- Quando a fonte que a sustentava informar a reabertura, ou uma nova verificação a contradisser: descarte ou marque impacto `nenhum`, com a justificativa.
- **Expiração automática:** o sistema também deixa de considerar interdições após a validade configurada (`validade_ocorrencia_h` em `config/analysis.yaml`), e os registros são removidos após 90 dias. A expiração não substitui a revisão humana: se a interdição ainda vale, **[PENDENTE DE APROVAÇÃO]** quem a renova e com que periodicidade.

## Registro da decisão

A justificativa vai no campo de evidência e no histórico do registro (`historico` de cada ocorrência). Em demonstração, a evidência deve dizer
que o dado é sintético; ocorrências sintéticas **nunca** são evidência de eventos reais.

## Limites deste procedimento

- Não há trilha de auditoria assinada nem separação entre quem propõe e quem aprova; um único token autoriza todas as ações de operador.
- A persistência é um arquivo local (`data/operacional/`), para um processo. Backup e acesso a ele são responsabilidade de quem hospedar.
