# Fase 4.1: auditoria, desempenho e preparação para demonstração

Estado em 25/11/2026, sem commit, push, deploy nem publicação. Os Parquets da Fase 3 e da Fase 2 não foram alterados e nada foi recalculado. Documento anterior: [fase4_integracao.md](fase4_integracao.md).

## 1. Auditoria do estado

`develop`, HEAD `dceb39b` (inalterado); 132 entradas locais ao iniciar a fase, todas preservadas. Os 692 testes da Fase 4 e os arquivos distribuídos continuavam íntegros (SHA-256 dos Parquets de entrada conferidos contra o `meta.json`).

## 2. Desempenho da troca de pacote

**Método.** Mesmo ambiente antes e depois: Chrome com WebGL por software (sem GPU), mapa 3D com relevo, 1.400×900, camada de contribuição ligada com cerca de 72 mil trechos à vista, seis trocas seguidas pelo seletor real do painel (Método 1 → 2 → limites → 1 → 2 → limites). Métrica principal: **tempo até a nova cor aparecer** (primeiro quadro desenhado depois que os tiles terminam de ser reprocessados).

**Onde estava o custo.** Medido em partes:

| Parte | Custo medido |
|---|---|
| Atualização de dados (fragmentos) | nenhuma: a troca não baixa nada; um clique baixa um fragmento (0,1 a 0,3 s) |
| Código da tela (estado, painel, legenda, estilo) | 2 a 62 ms (painel 22 ms; legenda 0 ms) |
| Recriação de fontes | nenhuma: a fonte nunca é recriada |
| **Reprocessamento dos tiles por mudança de expressão de cor ou de filtro** | **33 a 35 tiles reprocessados a cada troca**; 0,5 a 2,4 s de CPU (0,4 a 0,8 s em 2D) |
| Repintura (quadros) | **cerca de 0,7 a 1 s por quadro no 3D** (163 ms em 2D), com ou sem a camada: é o relevo, o mapa-base e o renderizador por software, não a camada |
| Memória | 154 MB de heap JS com a camada (desktop) |

Mudar a opacidade de uma camada **não** reprocessa tiles (0 eventos medidos); mudar a expressão de cor, sim. Os 6 a 25 s do relatório anterior eram esse reprocessamento mais vários quadros lentos de 3D por software, esperando o mapa "ficar quieto".

**Otimização feita (a menor com ganho medido).** Uma camada por propriedade da grandeza escolhida (6 para contribuição ou geração: 3 pacotes × 2 limites; 3 para cobertura; 1 para o topográfico), todas com a cor definida uma vez, só uma opaca. Trocar de pacote ou de limite passou a mudar apenas a opacidade. Trocar de **grandeza** recria o conjunto (um reprocessamento, raro). Sem dependência, cache, worker nem mudança de dados. Antes disso foi tentada e descartada outra mudança (filtros fixos e transição de cor zero), que não deu ganho mensurável.

| Troca de pacote (mediana de 6) | Antes | Depois |
|---|---|---|
| 3D: nova cor visível | 7,2 s (6,2 a 9,6) | **1,5 s (0,6 a 1,8)** |
| 3D: mapa estável | 24,9 s (11 a 168) | **2,8 s (1,9 a 3,5)** |
| 3D: tiles reprocessados | 33 a 35 | **0** |
| 2D: nova cor visível | 0,43 s | 0,40 s (sem mudança; já era rápido) |
| Celular 390×844, 3D: nova cor visível | não medido | 1,2 s (mapa estável em 2,2 s) |

**Custo da otimização** (execuções únicas, ruidosas): ativar a camada passou de cerca de 12 s para cerca de 15 s no desktop com renderização por software; heap JS de 154 para 193 MB (desktop) e de 103 para 110 MB (celular). Com GPU e hardware real esses números devem ser bem menores; **não foram medidos**. Seleção de trecho, mudança de cenário, mudança de chuva, legendas e a distinção entre zero e ausência seguem cobertas pelos testes (e2e inclusive).

## 3. Visão geral da cidade (abaixo do zoom 13)

Avaliado com os dados reais das células ([figura](figuras/fase41_visao_geral_avaliada.png)):

| Alternativa | Defensável? | Útil? | Decisão |
|---|---|---|---|
| Somar a **contribuição** dos trechos por grade ou H3 | **Não**: bacias de trechos vizinhos se sobrepõem, a mesma água seria contada várias vezes | n/a | rejeitada |
| Somar a **geração** das células por bloco de 300 m | Sim (células disjuntas, cada uma uma vez) | **Não**: com o Método 1 cobrindo 17% da área, o mapa só reproduz a mancha urbana, saturada, e não diz nada sobre acúmulo | não implementada |
| **Máximo** do acumulado das células por bloco | Sim como estatística de ordem (nenhuma soma) | Parece útil, mas **reproduz os eixos de drenagem do modelo de elevação** (uma função da área a montante), com cobertura parcial; leitura provável como "pontos de alagamento", o que o motor não afirma. Além disso troca a unidade de apresentação (célula, não trecho), contra a decisão tomada na Fase 3 | não implementada |
| Tiles de trechos em zoom menor | Sim, mas com perda de trechos (z12: 11 mil trechos curtos somem) e tiles de 2 MB | Pouco | rejeitada |

**Decisão: manter o comportamento atual** (trechos a partir do zoom 13, com a aproximação automática ao ligar a camada) e documentar. Se for desejado um panorama, a opção segura seria o mapa de **cobertura** (qualidade dos dados) agregado, que não soma nada; não foi pedida.

## 4. Inventário de drenagem (camada contextual)

Camadas auditadas (`data/processed/drenagem/`): rede pluvial 135.856 linhas (133.060 cadastro, 2.775 sem acesso, 21 cadastradas como não interligadas, pela camada de origem), poços de visita 88.899, bocas de lobo 44.868, casas de bomba 24. Geometrias todas válidas, dentro do município, em EPSG:31982; 77 + 39 + 107 registros são duplicatas exatas (marcadas, fora do inventário).

**Implementado** (independente do motor; nenhum código do motor importa a drenagem, conferido por teste):
- `tools/preparar_camada_drenagem.py` → `data/processed/drenagem_web/`: tiles por camada (só número do registro e 2 ou 3 classes inteiras), detalhe com **todos os atributos originais** (nulo continua nulo), `meta.json` com contagens, colunas, unidades do dicionário (marcadas como inferidas) e SHA-256.
- Camada "Drenagem cadastrada (inventário, só contexto)", com grupos ligáveis (rede, poços, bocas, casas de bomba), zoom 14 (rede e casas de bomba) e 15 (pontos). Legenda distingue: cadastro existente, registro sem acesso, cadastrado como não interligado, registro duplicado, halo para valor fora da faixa plausível, e **linha** versus **ponto**. O painel do registro mostra categoria, qualidade, evidência geométrica (rotulada "não é conexão hidráulica") e a tabela de todos os atributos; ausência aparece como "não informado".
- Não infere capacidade de vazão, funcionamento, conectividade hidráulica nem eficiência; "ativo no cadastro" é mostrado como campo do cadastro.

**Volume:** tiles 13,0 MB, detalhe 55,6 MB (3.536 arquivos; maior fragmento 275 KB, maior tile 141 KB; 11,8 MB compactados). Proporcional: um clique baixa um fragmento. Distribuição junto com a camada da Fase 3 em [seção 5](#5-preparação-para-publicação).

## 5. Preparação para publicação

Volume real: **Fase 3 mais drenagem = 137 MB em 5.595 arquivos** (maior arquivo 817 KB); **29,4 MB compactados** (17,7 + 11,8). Uso esperado: demonstração com poucas pessoas; cada sessão baixa de 4 a 7 MB de tiles e alguns fragmentos de 50 a 275 KB.

| | Cloudflare R2 | Cloudflare Pages | Render (como está) |
|---|---|---|---|
| Custo | 10 GB-mês e 10 milhões de leituras grátis; saída de dados grátis ([preços](https://developers.cloudflare.com/r2/pricing)). Uso previsto: 0,14 GB, bem abaixo | grátis | o serviço atual é grátis, sem disco, 512 MB, dorme em 15 min ([docs/render.md](render.md)); disco pago a US$ 0,25 por GB ([preços](https://render.com/pricing)) |
| Limites | sem limite de arquivos relevante aqui | 20.000 arquivos e 25 MiB por arquivo no plano gratuito ([limites](https://developers.cloudflare.com/pages/platform/limits)): 5.595 e 817 KB cabem | sem disco, os 137 MB teriam de ser baixados a cada partida a frio |
| Cache e compressão | cache por cabeçalho; objeto pode ser enviado já em gzip com `Content-Encoding` (4,7× menor); compressão automática de protobuf não confirmada | CDN e compressão automáticas | o servidor padrão (biblioteca padrão do Python) **não comprime** e manda `no-cache` |
| Versionamento | prefixo por versão (por exemplo o hash das entradas, que o `meta.json` já guarda) | um deploy por versão | nenhum |
| Disponibilidade | alta, independe do serviço dormir | alta | a camada some quando o serviço dorme ou falha |
| Facilidade | já existe `r2.py` com orçamento de operações e o mapa-base já usa R2 | exige separar o site do servidor (a API roda no Render), com CORS entre os dois | `FM_FASE3` e `FM_DRENAGEM` já funcionam, mas falta o passo que baixa os dados |
| Compatível com o site estático | sim, se o endereço dos dados for configurável | sim, é o caso natural, mas o site não é só estático | sim, mesma origem |

**Verificado:** o servidor real servindo `FM_FASE3` e `FM_DRENAGEM` apontados para pastas fora do repositório responde 200 (`.json`, `.pbf`), 204 para tile sem trechos e 404 para o resto; todos os endereços de dados são relativos à página (`new URL("fase3/", location.href)`), então o site funciona sob um caminho de repositório; `build.py --fase3 ... --drenagem ...` inclui os dados no site estático. **Não verificado:** a publicação em si, a configuração de CORS e a CSP do domínio externo.

**Recomendação: R2** (balde público com CORS, objetos em gzip com `Content-Encoding`, prefixo versionado e cache longo), mantendo o aplicativo no Render. É o que melhor combina com o volume (0,14 GB), o custo (zero) e a disponibilidade, e já existe a ferramenta de envio com orçamento. **Exige uma decisão sua**, porque envolve operação externa e duas mudanças pequenas no código: (1) um endereço-base configurável para `fase3/` e `drenagem/` (hoje relativo à página) e (2) incluir o domínio do R2 no `connect-src` da CSP do servidor. A alternativa de menor mudança, só para uma demonstração curta, é o Render baixar **um único arquivo compactado de 29 MB** na partida, como já faz com o mapa-base; ela repete o download a cada partida a frio e o servidor sem compressão entrega os tiles.

## 6. Auditoria de experiência

Testada em desktop (1.400 px) e celular (390 px), mapa 3D, mapa 2D sem WebGL (camadas aparecem indisponíveis com o motivo), camada indisponível no RS, trecho sem dados, seleção, troca de método, de limite, de grandeza e de chuva; sem transbordo horizontal em 360, 768 e 1.280 px. Captura de tela e leitura do painel como uma pessoa sem conhecimento técnico:

| Pergunta | Resultado |
|---|---|
| O que o mapa mostra? | Compreensível: aviso no topo do painel ("contribuição potencial estimada, condicionada a uma chuva hipotética... não substitui os alertas oficiais"), título da grandeza e da chuva na legenda |
| Significado das cores | Cada grandeza tem família de cor própria, legenda com faixa em m³ e "posição entre os trechos"; trecho sem dados tracejado, "não é valor zero" |
| Geração local versus contribuição acumulada | **Fraco**: a diferença só estava nas explicações recolhidas do painel do trecho. Corrigido (ver abaixo) |
| Indicador topográfico | Compreensível: posto, "não é profundidade, volume nem duração", e a limitação do modelo de 30 m |
| Por que alguns trechos não têm valor | Compreensível no painel do trecho e na legenda |

**Problemas encontrados e corrigidos** (todos de baixo risco e sem alterar textos tecnicamente corretos):
1. A legenda ficava longe dos controles: os blocos de opções foram movidos para logo abaixo da lista de camadas.
2. A paleta do indicador topográfico (amarelo a laranja) se confundia com o vermelho e laranja de "Risco estimado por trecho": passou a tons de terra.
3. A camada de risco, ligada por padrão, se sobrepõe à nova: uma dica no painel diz que são camadas diferentes e que pode desligar a outra.
4. A diferença entre geração local e contribuição acumulada não aparecia ao escolher a grandeza: ganhou uma frase por grandeza.

**Ainda existente:** "posto de 0 a 100" é um termo que exige explicação (a explicação existe no painel do trecho); trechos com valor zero ficam em branco e podem parecer ruas sem desenho; o painel no celular é baixo e exige rolagem; a camada de risco e a de escoamento ligadas juntas ainda se sobrepõem.

## 7. Problemas ainda existentes

- Desempenho com GPU e em celular real não foi medido; os números acima são de renderização por software.
- Os 70 MB de dados da Fase 3 e os 68 MB da drenagem continuam fora do Git e **não publicados**.
- Não há visão da cidade inteira de uma vez (decisão documentada na seção 3).
- Pontos da drenagem só a partir do zoom 15; 76 trechos de rede com menos de 30 cm não aparecem nos tiles (estão no detalhe).
- As limitações do motor da Fase 3 continuam as mesmas ([fase3_motor.md](fase3_motor.md)).
