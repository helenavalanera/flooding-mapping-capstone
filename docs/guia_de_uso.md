# Guia de uso: painel (desktop) e PWA (celular)

Os dois usam a mesma API e as mesmas regras; nada é calculado no navegador. Em ambos, o que é **observado**, **previsto**, **simulado** ou
**confirmado** tem selo, cor e traço próprios, e o que falta é dito ("Dados indisponíveis"), nunca mostrado como zero ou como risco baixo.

## Painel (desktop)

Endereço: `/` do servidor (`make servir` ou `make demo`).

- **Território:** seletor no topo, **Rio Grande do Sul** (monitoramento regional) ou **Porto Alegre** (mobilidade preventiva). Cada território mostra só o que oferece; o que não existe diz por quê.
- **Visão geral:** as cinco perguntas (o que acontece, onde estão os pontos de atenção, como pode evoluir, que deslocamentos podem ser afetados, que informações sustentam).
- **Mapa:** o mapa ocupa a tela, com painéis translúcidos por cima. Com WebGL há relevo 3D (só visual, com exagero vertical escolhido por você; não entra em nenhum cálculo). **Sem WebGL, o mapa 2D mantém as mesmas camadas e a mesma seleção**: ocorrências, interdições, trechos de atenção, rotas. Clique em um município, rodovia ou trecho para ver o painel de contexto. O painel pode ser recolhido.
- **Assistente:** na seleção, a seção **Assistente** oferece perguntas sugeridas e uma pergunta livre. A resposta diz se é texto padrão ou reformulada por provedor externo. Sem contexto suficiente, diz que não há dado.
- **Condições e previsão:** chuva (fonte, atualização, escopo regional), horas passadas como **análise do modelo** (não pluviômetro) e horas à frente como previsão. Sem dados de chuva, a tela diz que não há estimativa de risco.
- **Mobilidade (Porto Alegre):** marque origem e destino no mapa, escolha carro ou a pé e a hora de saída; compare tempo, exposição estimada e trechos de atenção.
- **Ocorrências:** lista de relatos (pendentes), confirmações e interdições. O operador entra com a credencial para revisar (ver `operacao_ocorrencias.md`).
- **Proveniência:** fontes, atualização, cobertura de dados, metodologia do risco, **o que se pode e o que não se pode afirmar** e o confronto do baseline com os eventos documentados.

## PWA (celular)

Endereço: `/pwa/`. Pode ser adicionada à tela inicial. Funciona sem localização (escolha os pontos no mapa).

1. **Abrir.** O mapa é a tela. No alto, o cartão de orientação; embaixo, o painel; à direita, os controles flutuantes.
2. **Origem e destino.** Em **Planejar**, escolha um lugar salvo, **Minha localização** (pede permissão, uma leitura, só com o app aberto) ou **Escolher no mapa** (o painel recolhe para você tocar). Escolha **Carro** ou **A pé** e a hora de saída.
3. **Analisar deslocamento.** O resultado traz:
   - **cartão de orientação:** a rota selecionada, a distância até o primeiro trecho de atenção e as interdições consideradas. É uma **orientação simplificada**: o sistema não gera instruções de manobra, porque o backend não as fornece;
   - **barra lateral:** a rota de cima (início) a baixo (fim), com os trechos de exposição estimada marcados onde estão;
   - **painel inferior compacto:** tempo, distância, chegada prevista, indicador de exposição e situação dos dados, mais as rotas como cartões deslizantes;
   - **Ver detalhes** (botão, sem precisar arrastar): condições da chuva com fonte e validade, trade-offs entre rotas, trechos de atenção, ocorrências no trajeto, perguntas sugeridas e explicação contextualizada sob pedido.
4. **Escolher a rota.** Toque num cartão para vê-la no mapa. A escolha é sua; o sistema nunca diz que uma rota é segura.
5. **Controles flutuantes.** **Eu** centraliza na sua posição (com consentimento), **Rota** reenquadra, **Mapa** abre camadas e legenda, **Relatar** abre o relato de ocorrência.
6. **Relatar.** Marque o ponto e descreva. O relato entra como **pendente** e **não interdita** nada.
7. **Lugares e trajetos habituais** ficam só no aparelho. **Privacidade** revoga o consentimento e apaga tudo.

### Estados que você pode ver

Carregando; localização negada ou indisponível (escolha no mapa); ponto fora da cobertura de Porto Alegre; nenhuma rota; sem conexão com o servidor (os lugares continuam salvos e a análise precisa de conexão); chuva indisponível ou defasada (só tempo e distância, sem estimativa de risco); relato pendente; ocorrência confirmada; interdição confirmada; explicação sem provedor de linguagem (texto padrão); mapa sem WebGL; app offline (abre a casca do app, sem fingir dados atuais).

### Origem e destino por endereço

A PWA **não** busca endereços digitados: isso exigiria enviar o texto a um serviço de geocodificação de terceiros, com impacto de privacidade e de licença que não foi avaliado. Origem e destino vêm de lugares salvos, da localização ou do mapa. Por isso o estado "origem não encontrada" aparece como **ponto fora da cobertura** ou **sem via próxima**.
