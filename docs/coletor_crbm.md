# Coletor dos bloqueios da CPRv BM

O endpoint público da CPRv BM (`bloqueios.cprvbm.rs.gov.br`) lista apenas os bloqueios rodoviários **ativos agora**; não existe histórico. O coletor cria esse histórico: consulta o endpoint a cada 30 minutos e arquiva no Cloudflare R2 **somente o que mudou**.

Código: `src/flooding_mapping/collector.py` (coleta) e `src/flooding_mapping/r2.py` (acesso ao R2 com orçamento). Agendamento: `.github/workflows/coletor-crbm.yml`.

## O que é gravado

```
bloqueios/_estado.json                        último estado conhecido (sobrescrito)
bloqueios/AAAA/MM/DD/AAAAMMDDTHHMMSSZ.json    um evento de mudança
```

Um evento traz os registros completos dos bloqueios **novos** e **alterados** e apenas os ids dos **removidos**. O armazenamento cresce com o número de mudanças, não com o número de consultas. Para reconstruir a linha do tempo, basta reler os eventos em ordem.

Campos relevantes de cada bloqueio: `id`, `municipio`, `rodovia`, `km`, `km_fim` (ausente em bloqueios pontuais), `tipo`, `data` (início), `informacoes` (texto livre), `climatico`, `lat`, `lng` e a liberação por classe de veículo. O campo `climatico` **não** significa alagamento: inclui erosão e falha estrutural. A separação deve ser feita a partir do texto livre.

Para quem lê os dados:
- Nos registros, `id` é número; em `removidos`, os ids são texto. Converta antes de comparar.
- O evento é gravado antes do estado. Se a gravação do estado falhar, a execução seguinte registra as mesmas mudanças de novo; trate um mesmo (`id`, registro) repetido como um só.

## Proteções

- **Resposta inválida não altera nada:** se o endpoint devolver algo que não seja a lista esperada (por exemplo, uma página de bloqueio do firewall), a execução falha e o estado fica intacto.
- **Orçamento por execução:** no máximo 10 operações de escrita (Classe A) e 5 de leitura (Classe B); o pedido é barrado antes de ser enviado. Uma execução normal usa 1 leitura e, quando há mudança, 2 escritas. Esse limite, somado à cadência do agendamento, já impede estourar a franquia: mesmo agendado a cada 5 minutos (o mínimo do GitHub), o pior caso seria cerca de 52 mil escritas por mês, 5% da franquia.
- **Sem repetições ocultas:** o cliente `boto3` não tenta de novo por conta própria e as tentativas do próprio coletor são limitadas a 3, todas contadas.
- Só `GetObject` e `PutObject`: sem listagem, `HeadObject`, cópia ou envio em partes.
- **Log público e útil:** em caso de erro, o log mostra a classe do erro e o código de erro do R2 (por exemplo `AccessDenied`), ou o nome das variáveis ausentes. Nunca valores.

Com uma consulta a cada 30 minutos são 48 por dia. No pior caso (mudança em todas), isso dá 2.880 escritas por mês, cerca de 0,3% da franquia de Classe A; as leituras somam 1.440 por mês, cerca de 0,014% da Classe B.

## Configuração no GitHub

**Settings → Secrets and variables → Actions**

| Nome | Tipo | Conteúdo |
|---|---|---|
| `R2_ACCOUNT_ID` | Secret | ID da conta Cloudflare |
| `R2_ACCESS_KEY_ID` | Secret | chave de acesso do token do R2 |
| `R2_SECRET_ACCESS_KEY` | Secret | segredo do token do R2 |
| `R2_BUCKET` | Secret ou Variable | nome do bucket |
| `COLETOR_ATIVO` | Variable (opcional) | `false` pausa o coletor sem editar código |

O token do R2 deve ter permissão de leitura e escrita **apenas no bucket do projeto**. O repositório é público: o log da execução mostra só contadores e códigos de erro, nunca valores.

## Backup

O R2 é a única cópia do histórico. Se o pagamento da conta falhar, o acesso ao bucket é bloqueado e os dados podem ser apagados após 30 dias. Uma vez por mês, copie o bucket para o computador, com qualquer cliente S3 e o endpoint `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, por exemplo:

```bash
aws s3 sync s3://<bucket> backup-r2/ --endpoint-url https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

A listagem do `sync` usa poucas operações Classe A por mês. Guarde o backup fora do repositório.

## Pontos de atenção

1. **O agendamento só roda a partir da branch padrão.** O GitHub dispara o `cron` somente com o arquivo de workflow na branch padrão do repositório (hoje `main`).
2. **Repositórios públicos têm o agendamento desativado após 60 dias sem atividade.** Qualquer commit ou push reinicia a contagem.
3. **O `cron` do GitHub pode atrasar ou pular execuções** em horários de pico. Para bloqueios que duram horas isso é aceitável, mas a resolução do histórico é de cerca de 30 minutos, não exata.
4. **O alerta de falha é o e-mail do GitHub.** Confirme em Settings → Notifications → Actions.
5. **Uso automatizado do endpoint:** o coletor se identifica no `User-Agent` e consulta a cada 30 minutos. Convém confirmar com a CPRv BM que o uso é permitido.

## Como testar

```bash
make coletar        # consulta o endpoint e mostra o que seria gravado; não grava nada
make test           # testes (não precisam de rede nem de boto3)
```

Para a primeira execução real, use **Actions → coletor-crbm → Run workflow**. Depois confira o bucket: devem existir `bloqueios/_estado.json` e um evento do dia.
