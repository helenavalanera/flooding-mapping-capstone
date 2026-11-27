# Landing científica (estudo)

> **Atualização (versão final).** A landing tem hoje cinco áreas: Apresentação, Mapa, Simulador, Resultados e Contato. Método, fontes, hipóteses, validações, limitações e referências saíram da página e ficam na documentação técnica (`docs/metodologia.md`, `docs/inventario_fontes.md`, `docs/referencias_bibliograficas.md`), com links no rodapé. O texto abaixo descreve a estrutura anterior, de nove seções.

`/inicio/` é a porta de entrada do produto: uma apresentação editorial do estudo, que comunica a pergunta, os dados, as descobertas, os testes, as limitações e o caminho até o mapa. O painel é a ferramenta de exploração; a landing não o duplica.

## Estrutura (as nove seções pedidas)

01 Hero (a pergunta, mapa real de contribuição, selo do Space Tech Bootcamp 2026, dois CTAs) · 02 O problema e o território · 03 O que descobrimos (quatro achados e doze números em três grupos: processamento, resultado metodológico, validação exploratória, cada um com unidade, definição, origem, contexto e limitação; histograma da distribuição e barra de cobertura) · 04 Explore o território (quatro camadas reais em abas, recorte com duas camadas independentes, links que abrem o mapa configurado) · 05 Como foi construído (seis passos, três grandezas, hipóteses) · 06 Resultados, testes e validação (conclusão negativa em destaque, critérios de adoção, comparação dos métodos, robustez, baseline de ML, tabela de métodos não adotados) · 07 Simule cenários (10, 30 e 60 mm com os números das três execuções do motor) · 08 Dados, limitações e reprodutibilidade · 09 Síntese.

Referências de organização (princípios, não cópia): mostrar o fracasso com números e declarar as premissas (estudo da Chapada das Mesas); aviso de limite antes do dado, comparação com um baseline simples e separação de código, dados e licença (estudo do Taquari); promessa única e ilustração rotulada (terceiro estudo).

## Como é gerada

`PYTHONPATH=src .venv/bin/python tools/gerar_landing.py` (`--so-graficos` e `--sem-figuras` para refazer menos) lê `reports/qa/*.json`, os Parquets e os `meta.json` derivados, e escreve `static/inicio/{index.html, dados.json, img/estudo/*}` a partir de `tools/landing/estudo.template.html`. **Nenhum número é digitado à mão:** os cartões saem de `numeros()`, cada um com o caminho do JSON de origem; os mapas e gráficos são desenhados dos mesmos dados (as paletas e cores vêm de `fase3-dados.js` e `drenagem.js`, para a landing e o app não divergirem).

`tests/test_landing.py` confere: estrutura, ordem das seções, âncoras e links, imagens com descrição e dimensões, nenhum recurso externo nem script em linha (CSP), termos proibidos, presença do resultado negativo e do caráter exploratório, cada cartão contra o relatório de origem, e que o HTML é exatamente o que o gerador produz. `tests/e2e/landing.js` (navegador) confere âncoras, abas, comparador de cenários contra `dados.json`, o link que abre o mapa já com camada, chuva, pacote e grandeza pedidos (`#poa/mapa?escoamento=1&p=60&pacote=an&modo=l`), e ausência de transbordo de 360 a 1.440 px.

## Peso e acessibilidade

Imagens 1,9 MB no total (mapa do hero 428 KB, o resto carrega só ao rolar); gráficos em SVG com texto real; `h1` único, navegação por teclado nas abas, `prefers-reduced-motion` respeitado, contraste da paleta do app, gráficos com rolagem horizontal no celular para manter o texto legível.

## O que mudou no app

`#poa/mapa?escoamento=1&p=30&pacote=m1&modo=c&drenagem=1` abre o mapa de Porto Alegre com as camadas e a chuva pedidas (só valores conhecidos; `logic.js` `parseHash` devolve `consulta`). A apresentação do aplicativo do cidadão, que era a landing anterior, está em `inicio/aplicativo.html`.

## Limites

Os mapas são imagens estáticas dos resultados (não interativas); o interativo é o mapa da aplicação. Os números e figuras refletem a execução de 25/11/2026: ao regenerar os dados, rodar o gerador de novo (o teste acusa divergência). Dashboard, mapa, simulador e PWA ainda não receberam o redesign de identidade desta sequência.
