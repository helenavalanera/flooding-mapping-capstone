# Segurança e proteção de dados: controles, riscos e pendências

Este documento descreve o que o código faz hoje e o que não faz. **Ele não declara conformidade com a LGPD**: ter controles técnicos não
substitui base legal, avaliação jurídica, encarregado, política de privacidade publicada e resposta a titulares, que dependem de quem
operar o produto em escala pública. O escopo aqui é a demonstração controlada.

## Dados tratados

| Dado | Onde fica | Por quanto tempo | Quem acessa |
|---|---|---|---|
| Lugares e trajetos habituais (PWA) | só no aparelho (`localStorage`) | até a pessoa apagar (Privacidade → Apagar tudo) | a própria pessoa |
| Consentimento de localização | só no aparelho | idem | idem |
| Posição do aparelho | lida **uma vez**, em primeiro plano, após consentimento | usada para marcar um ponto; não é gravada no servidor | ninguém |
| Origem, destino, modal e hora de uma análise | memória do servidor | até 30 min, ou até iniciar outra análise ou fechar o app; apagada por `DELETE /api/analises/{id}` | o servidor, para calcular |
| Relato de ocorrência (texto livre e ponto) | arquivo local do servidor | 90 dias, depois removido | texto livre: só o operador autenticado |
| Decisões do operador (situação, evidência, impacto) | histórico do registro | 90 dias | operador |
| Logs | **não há log de acesso** nem de corpos de requisição | — | — |

Não há contas de usuário, cookies de rastreamento, analytics nem identificador persistente do usuário.

## Controles implementados

- **Minimização:** o servidor recebe coordenadas só para calcular uma rota; nomes de lugares nunca vão à rede (testado no navegador). Não há rastreamento contínuo nem em segundo plano.
- **Consentimento de localização:** diálogo explícito com a finalidade antes do primeiro pedido; revogável; todo o app funciona escolhendo pontos no mapa.
- **Provedor de linguagem (Gemini), explicação e assistente:** recebe apenas resumos agregados (tempos, classes de risco, nomes das vias mais expostas, horários, lacunas), **nunca** origem, destino, coordenadas ou identificadores internos. A pergunta livre do usuário é tratada como dado não confiável. Só há chamada quando a pessoa pede.
- **Provedor de linguagem, relatos (exceção):** se o provedor estiver configurado, o **texto do relato** é enviado a ele para ser organizado em campos (tipo, severidade). A tela de relato avisa isso e pede para não incluir dados pessoais. Sem provedor configurado, o texto fica só no servidor do projeto. Falha do provedor não impede o registro do relato.
- **O modelo não age:** não cria interdições, não altera situação de ocorrências, não calcula rotas nem altera parâmetros de risco; suas únicas operações são de leitura, ligadas à análise em curso, com contrato fechado. O texto que ele devolve é validado (tamanho e expressões proibidas como "seguro").
- **Chave e credenciais:** `GEMINI_API_KEY` e `OPERADOR_TOKEN` só em variável de ambiente ou `.env` (ignorado pelo Git); a chave segue em cabeçalho, nunca em URL ou log. Token do operador com no mínimo 24 caracteres, falhas limitadas a 8 por minuto.
- **Rate limiting** por cliente: 20 rotas, 10 explicações, 10 assistente e 10 relatos por minuto; 240 leituras por minuto. Atrás de proxy, `PROXIES_CONFIAVEIS` define de quem se lê o cabeçalho `X-Forwarded-For`.
- **Cabeçalhos:** `Content-Security-Policy` restritiva, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` na API. CORS só para `CORS_ORIGEM` (vazio = mesma origem). Corpo máximo de 8 KB.
- **Saída escapada:** todo texto vindo de dados ou da API é escapado antes de entrar na página; teste automatizado confere.
- **Service worker:** nunca guarda respostas da API.
- **Erros:** respostas 500 sem detalhes internos.

## Riscos e pendências (nada disto está resolvido)

1. **Relato com dado pessoal:** o texto é livre. A tela pede para não incluir dados pessoais, mas não os detecta. O texto fica no arquivo do servidor por 90 dias.
2. **Sem hospedagem pública validada:** não houve teste de carga, de penetração, nem revisão de TLS/proxy em ambiente real. A CSP e os limites foram testados localmente.
3. **Token único de operador:** sem separação de papéis, sem rotação automática, sem trilha de auditoria assinada.
4. **Persistência em arquivo:** um processo apenas; backup, permissão de arquivo e criptografia em repouso são responsabilidade de quem hospedar.
5. **Provedor externo:** os resumos agregados vão a um serviço de terceiros quando a pessoa pede a explicação contextualizada. Contrato, localização do tratamento e retenção do provedor não foram avaliados.
6. **Geolocalização aproximada:** a posição lida é exata para o aparelho, e o servidor recebe as coordenadas do ponto escolhido (origem) na análise, durante até 30 min.
7. **Direitos dos titulares:** não há canal nem processo para acesso, correção ou eliminação de relatos além do prazo de 90 dias. **[PENDENTE DE APROVAÇÃO]** quem responde.
8. **Segurança de dependências:** os fixos são `requirements.lock.txt`; não foi executada varredura de vulnerabilidades.

## O que foi verificado automaticamente

`tests/test_servidor.py` (proxy, token, limites, cabeçalhos, 503, fluxo do operador), `tests/test_ocorrencias.py` (persistência, arquivo truncado, retenção, texto livre), `tests/test_linguagem.py` (chave em cabeçalho, privacidade do que o provedor vê, falhas, respostas inválidas) e os testes de navegador (nomes de lugares fora da rede, sem rastreamento contínuo, apagar tudo, offline).
