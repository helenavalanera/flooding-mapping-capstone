# Hospedagem do servidor

Estado: **preparada e testada localmente; nada foi publicado.** Publicar exige autorização, conta e cobrança que não foram feitas.

## O que foi auditado

| Item | Resultado |
|---|---|
| Python | 3.12 |
| Dependências | `requirements-servidor.txt`: numpy, pandas, scipy, pyarrow, pyyaml, requests. Sem geopandas, shapely, pyproj ou GDAL (o servidor deixou de importá-los) |
| Servidor | `ThreadingHTTPServer` da biblioteca padrão, um processo. Adequado ao MVP: rota com mediana de 0,7 s e p95 de 1,5 s (uma por vez), 329 MB ao subir e **pico de 482 MB** em 24 rotas e 10 mapas. Não foi introduzido framework: nada o exigiu |
| Concorrência | O motor de rotas é Python puro e usa uma CPU: poucas análises simultâneas. Acima disso, mais processos exigem repensar a persistência (ver abaixo) |
| Arquivos estáticos | dashboard e PWA saem do mesmo processo; a previsão estadual (`previsao_72h.json`, `bloqueios.json`) vem do site gerado, em `FM_SITE` |
| Persistência | arquivo JSON Lines das ocorrências, com `fsync`, linhas truncadas ignoradas na leitura e retenção de 90 dias por troca atômica |
| Rede externa | Open-Meteo (chuva), tiles do OpenStreetMap e AWS Terrain Tiles (no navegador), API do Gemini (opcional) |
| Segredos | só por variável de ambiente; `.env` é ignorado pelo Git e pelo Docker |

## Escolha: uma instância, um contêiner, um volume

O arquivo de ocorrências só é seguro com **um processo escrevendo**. Isso descarta, para este MVP, qualquer plataforma que escale por réplicas ou
que use disco efêmero. O desenho mínimo é **uma máquina sempre ligada com um volume persistente e HTTPS terminado pela plataforma**.

| Opção | Custo (páginas oficiais, consultadas em 11/11/2026) | Persistência | Observações |
|---|---|---|---|
| **Fly.io** (recomendada) | máquina `shared-cpu-1x` com 512 MB: US$ 3,69/mês; com **1 GB: US$ 6,70/mês**. Preço do volume: não extraído da página; confirmar | volume ligado à máquina | HTTPS e segredos nativos, health check, uma só máquina com volume |
| Railway | plano Hobby com mínimo de US$ 5 de uso; cobrança por uso (memória ≈ US$ 0,0000039 por GB·s, o que dá cerca de US$ 10 por GB·mês ligado, mais CPU; volume ≈ US$ 0,00000006 por GB·s) | volumes disponíveis | mais caro ligado 24 h com 1 GB |
| Render | não extraído da página (conteúdo dinâmico) | disco persistente exige instância paga | verificar preço antes |
| VPS (ex.: Hetzner) | a página mostra planos a partir de € 5,49–5,99 por mês; o plano exato não foi identificado | disco da máquina | controle total, mas exige cuidar de TLS (por exemplo Caddy), atualizações e reinício |

**512 MB não serve**: o pico medido foi 482 MB. O mínimo é **1 GB**. Estimativa de custo mensal na opção recomendada: cerca de US$ 7 pela máquina,
mais o volume (poucos GB). Não há custo do Gemini sem chave; com chave, ver `docs/validacao_gemini.md`.

O `Dockerfile` é independente de provedor (qualquer host de contêiner com volume). `deploy/fly.toml` é um **modelo inerte** para Fly.io.

## Variáveis de ambiente

| Variável | Obrigatória | Para quê |
|---|---|---|
| `OPERADOR_TOKEN` | para confirmar ocorrências | mínimo de 24 caracteres; gere com `python -m flooding_mapping.servidor --gerar-token`. Sem ela a confirmação fica **desativada** (a tela informa) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | não | contextualização; sem elas, textos calculados pelo sistema |
| `GEMINI_PENSAMENTO` | não | nível de raciocínio (padrão `minimal`; esvazie se o modelo recusar) |
| `CORS_ORIGEM` | só com front-end em outro domínio | uma única origem permitida |
| `PROXIES_CONFIAVEIS` | atrás de proxy | endereços ou redes (separados por vírgula) cujos cabeçalhos `X-Forwarded-For` valem |
| `FM_REDE`, `FM_OCORRENCIAS`, `FM_SITE` | no contêiner | caminhos no volume (`/dados/...`) |
| `HOST`, `PORT` | no contêiner | `0.0.0.0` e a porta da plataforma |

### Proxy confiável (rate limit)

`X-Forwarded-For` só é considerado quando a conexão direta vem de um endereço listado em `PROXIES_CONFIAVEIS`; a cadeia é lida da direita e o
primeiro endereço que não é proxy é o cliente. Sem a lista, o cabeçalho é ignorado (qualquer cliente pode escrevê-lo). Para descobrir o
endereço do proxy sem adivinhar, chame `/api/saude` com `Authorization: Bearer <OPERADOR_TOKEN>`: o campo `diagnostico_de_origem` mostra a
`conexao_direta`. No teste com Docker ela foi `192.168.65.1`. O endereço do proxy da hospedagem escolhida **precisa ser conferido na implantação autorizada**.

## Preparação do volume e implantação

```
make rede                                   # gera data/processed/rede_poa.parquet (17 MB)
make estado-site                            # gera site/ (previsão estadual); opcional
# copie rede_poa.parquet (e a pasta site/, se quiser o mapa estadual completo) para o volume em /dados
docker build -t flooding-mapping .
docker run -p 8080:8080 -v fm-dados:/dados -e OPERADOR_TOKEN=... flooding-mapping
```

Sem `site/` no volume, o dashboard funciona, mas o mapa estadual não mostra a previsão municipal (404 nos dois arquivos).

**Health check:** `GET /api/saude` (200 mesmo degradado; o corpo diz `status`, a idade da chuva e contadores). **Encerramento:** SIGTERM e SIGINT são parada limpa (testado: 0,4 s, código 0).

## Operação

* **Logs:** só erros e chamadas lentas (mais de 5 s), com o grupo da rota e o tipo do erro. Não há log de acesso, de corpos, de coordenadas, de relatos, de tokens ou de chaves (conferido no contêiner).
* **Métricas:** `/api/saude` traz requisições, erros 5xx e latência p95 das últimas 500, por grupo de rota.
* **Atualização:** gerar nova imagem, parar (SIGTERM), subir a nova com o mesmo volume. Ocorrências e a tabela de ruas ficam no volume; a análise em andamento (memória) é descartada.
* **Backup:** copiar `/dados/ocorrencias.jsonl` (arquivo só de acréscimo; uma cópia a quente é segura). **Recuperação:** colocar a cópia no volume e reiniciar. Linhas truncadas por queda de energia são ignoradas e contadas no log de inicialização.
* **Falhas:** sem chuva, rotas continuam só com tempo e distância e as demais telas mostram a última atualização; sem Gemini, respostas calculadas; arquivo de ocorrências ilegível em parte, o servidor sobe com o que for válido.

## O que continua pendente

Autorização e conta no provedor; confirmar o preço do volume; endereço do proxy da hospedagem; domínio e `CORS_ORIGEM` se o front-end ficar fora; um segundo processo ou mais de uma instância exigiria banco transacional (não implementado por antecipação).
