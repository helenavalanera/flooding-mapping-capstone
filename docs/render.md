# Hospedagem no Render: preparação, custos e checklist

## Estado (quatro coisas diferentes)

| Dimensão | Estado | O que isso quer dizer |
|---|---|---|
| **Preparado para deploy** | **Sim** | Imagem Docker, porta dinâmica, health check, variáveis, download verificado da tabela de ruas e modelo `deploy/render.yaml`; tudo testado **localmente** em contêiner |
| **Deploy realizado** | **Não** | Nada foi enviado ao GitHub nem ao Render; nenhum serviço existe |
| **Deploy validado (HTTPS, remoto)** | **Não** | Depende de o serviço existir |
| **Experiência validada em dispositivo físico** | **Não** | Ver `docs/qa_mobile_fisico.md` |

Os testes abaixo valem para o **contêiner local**, que reproduz o que o Render faz com a imagem. Eles **não** provam o comportamento do Render (rede, proxy, limites do plano).

## Arquitetura escolhida

**Um único Web Service Docker** serve a API, o painel (desktop) e o PWA, na **mesma origem**. O backend Python já entrega os arquivos estáticos; o PWA chama a API pelo caminho relativo (`../api/`).
Por isso: sem CORS, sem URL de API para configurar, sem segundo serviço, e desktop e PWA usam a mesma API por construção.

**Hospedagem separada (descartada para esta fase):** exigiria um serviço estático, CORS (`CORS_ORIGEM`), `<meta name="api-base">` no PWA e dois deploys. Não traz ganho para uma demonstração; fica como opção se o front-end um dia precisar de CDN.

## Antes de publicar: o que depende de você (nada disso foi feito)

1. **Enviar o código ao GitHub** (`git push`): não autorizado nesta rodada. O Render constrói a partir do repositório.
2. **Hospedar a tabela de ruas** `rede_poa.parquet` (17 MB). Ela não está no Git (`data/` é ignorado) nem na imagem. O servidor a baixa na inicialização, se faltar, de um endereço **https** que você controla, e **só a aceita se o SHA-256 conferir**:
   ```bash
   shasum -a 256 data/processed/rede_poa.parquet      # valor de FM_REDE_SHA256
   ```
   Onde hospedar o arquivo (por exemplo, um anexo de release do GitHub ou um armazenamento de objetos com URL de leitura) é uma escolha sua. A tabela deriva do OpenStreetMap (ODbL): mantenha a atribuição.
3. **Escolher o plano** (seção de custos). Isso envolve cobrança.
4. **Criar o serviço no painel do Render** (Blueprint a partir de `deploy/render.yaml` copiado para a raiz como `render.yaml`, ou "New Web Service" com Docker) e **preencher os segredos à mão**.
5. **Definir `PROXIES_CONFIAVEIS`** depois do primeiro deploy (abaixo).

## Variáveis de ambiente

| Variável | Obrigatória | Observação |
|---|---|---|
| `PORT` | automática | o Render a define; o servidor lê `PORT` (testado com `PORT=10000`) |
| `OPERADOR_TOKEN` | para confirmar ocorrências | mínimo de 24 caracteres; **só no painel do Render** |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | não | **só no painel do Render**; sem elas, texto padrão |
| `FM_REDE_URL`, `FM_REDE_SHA256` | sim, no Render | tabela de ruas (https + hash) |
| `PROXIES_CONFIAVEIS` | recomendada | ver a próxima seção |
| `FM_OCORRENCIAS`, `FM_SITE` | já definidas no Dockerfile | apontam para `/dados` |

Nenhuma credencial está no código, no Dockerfile, em `render.yaml` ou nesta documentação.

## Proxy e limite de uso

O Render coloca um proxy na frente. Sem `PROXIES_CONFIAVEIS`, o servidor vê **um único endereço** e todos os visitantes dividem os mesmos limites (240 leituras e 20 rotas por minuto). Para configurar sem adivinhar:

1. Faça o primeiro deploy sem `PROXIES_CONFIAVEIS`.
2. Chame `https://<seu-serviço>/api/saude` com o cabeçalho `Authorization: Bearer <OPERADOR_TOKEN>`; o campo `diagnostico_de_origem` mostra a `conexao_direta` (o endereço do proxy).
3. Coloque esse endereço (ou a rede) em `PROXIES_CONFIAVEIS` e reinicie.

O endereço do proxy do Render **não foi verificado** (não houve deploy).

## Planos e custos (consultados em 11/11/2026; confirme em render.com/pricing)

| Plano | Preço | Memória | Disco persistente | Observações |
|---|---|---|---|---|
| Gratuito | US$ 0 | 512 MB | **não** | dorme após 15 min sem tráfego (cerca de 1 min para acordar); 750 horas de instância gratuitas por mês |
| Pago de entrada | US$ 7/mês | 512 MB | sim | fica ligado |
| Standard | US$ 25/mês | 2 GB | sim | |
| Disco | US$ 0,25 por GB por mês | | | só em serviços pagos |

**Fontes:** [Render, preços](https://render.com/pricing), [Render, Deploy for Free](https://render.com/docs/free), [Render, compute plans](https://render.com/docs/compute-plans). Os nomes dos planos mudaram em 2026; confira no painel.

**O que o nosso serviço consome (medido em contêiner local):** cerca de 390 a 410 MiB em repouso e **pico de 482 MB** em 24 rotas e 10 mapas (`docs/hospedagem.md`). Em **512 MB a margem é mínima**: há risco real de o serviço ser encerrado por falta de memória sob uso.

**Consequências:**

- **Plano gratuito:** serve para uma demonstração curta. **Não há persistência**: o arquivo de ocorrências é perdido a cada reinício, redeploy ou suspensão por inatividade. Pode também ser encerrado por memória.
- **Persistir ocorrências exige plano pago com disco** (de US$ 7,25 por mês com 1 GB, ou US$ 25,25 com 2 GB de memória). Com 512 MB, o risco de falta de memória continua.
- **Não recomendo trocar de plano sem a sua decisão de custo.** A decisão de menor risco para uma demonstração com persistência é o plano de 2 GB; para uma demonstração só de leitura, o gratuito.
- O armazenamento atual é um arquivo de um processo: **não** use mais de uma instância.

## Segurança e produção (revisão específica)

| Item | Situação |
|---|---|
| Segredos | só por variável de ambiente; `.env` é ignorado pelo Git e pela imagem; não aparecem nos logs (conferido no contêiner) |
| CORS | mesma origem: nenhum cabeçalho CORS; `CORS_ORIGEM` só se o front-end for separado |
| Operações administrativas | confirmar, descartar e ver o texto livre exigem `OPERADOR_TOKEN` (403 sem ele, testado); falhas de credencial limitadas a 8 por minuto por cliente |
| Rate limiting | por cliente; depende de `PROXIES_CONFIAVEIS` atrás do Render |
| Endpoints internos | `/api/saude` é público, mas o diagnóstico de origem só aparece com a credencial do operador |
| Logs | sem log de acesso, de corpos, coordenadas, relatos, tokens ou chaves |
| HTTPS | terminado pelo Render; o servidor fala HTTP dentro da plataforma. **Não verificado** (sem deploy) |
| Retenção | relatos e decisões por 90 dias, com remoção; análises em memória por até 30 min |
| Download da tabela de ruas | só https, hash obrigatório, limite de 300 MB, gravação atômica (testado) |
| Domínio e DNS | **não alterados**; usar o endereço `onrender.com` |

Não há declaração de conformidade com a LGPD (ver `docs/seguranca_lgpd.md`).

## Checklist de validação

Legenda: **Local** = executado em contêiner local em 11/11/2026; **Não executado** = depende de deploy ou aparelho. Nada abaixo está validado **no Render**.

| # | Verificação | Local | No Render |
|---|---|---|---|
| 1 | Build Docker | OK (imagem construída) | Não executado |
| 2 | Inicialização do serviço (com `PORT=10000`) | OK; responde em 7 s com a tabela em disco | Não executado |
| 3 | Health check (`/api/saude`; `HEALTHCHECK` do Docker usa `PORT`) | OK, estado `healthy` | Não executado |
| 4 | Interface desktop | OK (`/` responde 200; testes de navegador) | Não executado |
| 5 | Interface PWA | OK (`/pwa/` e `sw.js` respondem 200; testes de navegador) | Não executado |
| 6 | Rotas de carro e a pé | OK (as duas, com alternativa) | Não executado |
| 7 | Consulta meteorológica | OK, com a previsão real da Open-Meteo | Não executado |
| 8 | Registro e confirmação de ocorrência | OK (relato; 403 sem credencial; 200 com ela) | Não executado |
| 9 | Interdição e recálculo | OK (interdições 0 → 7; o traçado muda) | Não executado |
| 10 | Persistência após reinício | OK (volume local; ocorrência confirmada preservada) | Não executado; **impossível no plano gratuito** |
| 11 | Gemini com chamada real | OK: chave injetada por `--env-file` no contêiner; a resposta veio do provedor, sem a palavra proibida e sem chave nos logs | Não executado |
| 12 | Fallback sem o provedor | OK: com chave inválida, o assistente respondeu com texto padrão (`autenticacao`) | Não executado |
| 13 | Dispositivo físico | Não executado | Não executado |
| 14 | Download verificado da tabela de ruas | OK (5 testes automatizados e um teste real local: baixou 17 MB, hash conferido; hash errado descartou o arquivo) | Não executado |

Para o item 11 no Render, repita a chamada depois de preencher `GEMINI_API_KEY` no painel.

## Falhas e reinicialização

Sem chuva, as rotas seguem só com tempo e distância e as telas dizem isso. Sem o provedor, o texto padrão cobre o assistente. Se a tabela de ruas não puder ser baixada ou o hash não conferir, o servidor **não sobe** e diz o motivo no log (o serviço não chega a ficar saudável). Ao acordar do repouso (plano gratuito), o PWA mostra "Sem conexão com o servidor de análise" até o serviço responder.

O service worker usa a rede primeiro para os arquivos do app e nunca guarda a API; a versão do cache (`VERSAO` em `pwa/sw.js`) é alterada à mão a cada versão do app (precisa lembrar disso ao publicar), e o aviso "Há uma nova versão" aparece ao atualizar (testado em `tests/e2e/pwa_sw.js`).
