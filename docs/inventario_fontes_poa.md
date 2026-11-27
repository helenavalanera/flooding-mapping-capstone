# Inventário e matriz de disponibilidade das fontes (25/11/2026)

> Inventário **geral** de fontes, dados derivados, ferramentas (com a classificação de uso) e licenças a confirmar: [`inventario_fontes.md`](inventario_fontes.md). Referências em ABNT: [`referencias_bibliograficas.md`](referencias_bibliograficas.md). Este documento detalha as camadas da Prefeitura.

Um endpoint que responde não é uma fonte disponível: cada linha abaixo diz o que foi **consultado, baixado, inspecionado e validado**. Detalhes e números em [auditoria_fontes_drenagem_poa.md](auditoria_fontes_drenagem_poa.md).

**Estados.** Os seis do pedido, mais um intermediário (coletado e auditado, sem processamento). Na Fase 2, as camadas de inventário de drenagem e o uso do solo passaram a **Integrado, mas com limitações**: foram processados e versionados, **mas nenhum entra ainda na aplicação nem em um modelo**:

- **Integrado e validado** · **Integrado, mas com limitações** · **Disponível para aquisição** · **Acesso confirmado, mas dados ainda não inspecionados** · **Disponibilidade não confirmada** · **Necessita solicitação formal**
- **Coletado e auditado, integração pendente** (estado acrescentado)

## Matriz

| Fonte | Variável | Estado | Resolução ou escala | Cobertura | Qualidade (resumo) | Uso no modelo |
|---|---|---|---|---|---|---|
| Copernicus DEM GLO-30 | Elevação (DSM) | Integrado, mas com limitações | 30 m | Global | Viés +1,26 m e erro médio 2,18 m contra 334 marcos; sem microrrelevo | Base topográfica atual |
| OpenStreetMap | Rede viária (176.836 trechos) | Integrado, mas com limitações | Vetor | Porto Alegre | Não auditada nesta etapa | Unidade espacial |
| Open-Meteo | Chuva horária regional | Integrado, mas com limitações | Grade de ~10 km | Série única para a cidade | Não diferencia ruas | Fator de chuva |
| Mapas da Prefeitura (My Maps) | Bairros, arroios (679), casas de bomba (20), aglomerados | Integrado, mas com limitações | Vetor | Porto Alegre | Arroios divergem do recurso hídrico (18% a até 25 m) | Contexto e camadas do app |
| Marcos RRCM e alagamentos 2013–14 (My Maps) | Altitude ortométrica; 124 trechos alagados | Integrado, mas com limitações | Pontos | Porto Alegre | 124 trechos sem hora nem chuva; marcos podem ter controlado o MDT 2010 | **Validação**, nunca treino |
| **Uso do solo, Profill 2022** | Classe de uso (15) | **Integrado, mas com limitações** (processado em `data/processed/`; ainda fora da aplicação e do modelo): 605.245 polígonos, validados, e áreas por classe na grade de 30 m do DEM | Escala 1:2.500; ortoimagem de 30 cm (2018 a 2021) | 95,1% do município (a lacuna é, em 92,9%, o Guaíba) | 277 inválidos (reparados), 852 duplicatas, 0 sobreposição; **coeficiente fundamentado em 17,3% da área** | Geração de escoamento: áreas por classe; coeficientes só do Método 1 e cenários declarados |
| **Rede pluvial** (57) | Diâmetro, altitudes, tipo | **Integrado, mas com limitações** (processado em `data/processed/`; ainda fora da aplicação e do modelo) | Vetor; 133.060 trechos, 2.878 km | Porto Alegre | Diâmetro 100%; material 7,7%; altitudes 88% com outliers; **sem identificador nem nós** | Grafo parcial (conexão só inferida) |
| Rede pluvial sem acesso (58) e não interligada (59) | Idem | **Integrado, mas com limitações** (processado em `data/processed/`; ainda fora da aplicação e do modelo) (camada de origem preservada) | 2.775 e 21 trechos | Porto Alegre | Diâmetro 45% e altitudes 0,6% (58); todos inativos (59) | **Fora** do grafo funcional |
| Poço de visita (50) | Nós; profundidade; altitude da tampa | **Integrado, mas com limitações** (processado em `data/processed/`; ainda fora da aplicação e do modelo) | 88.899 pontos | Porto Alegre | Altitude da tampa 90%; profundidade 84% | Nós candidatos |
| **Bocas de lobo** (51) | Pontos de captação | **Integrado, mas com limitações** (processado em `data/processed/`; ainda fora da aplicação e do modelo) | 44.868 pontos | Porto Alegre | 99% a até 2 m da rede (geométrico); **sem capacidade nem relação com trecho**; profundidade zero em 82% | Inventário de captação, sem capacidade |
| Grelha (52), coletor de fundo (49) | Pontos | Coletado e auditado, integração pendente | 955 e 1.868 | Porto Alegre | Atributos parciais | Inventário |
| Canal pluvial (53) e conduto forçado (55) | Seção, altitudes | Coletado e auditado, integração pendente | 1.752 (+31 sem acesso) e 108 | Porto Alegre | Altitudes em ~20% dos canais; conduto sem altitudes | Inventário (sem capacidade confiável) |
| **Casas de bomba e EBAP** | Localização | **Integrado, mas com limitações** (processado em `data/processed/`; ainda fora da aplicação e do modelo) | 24 pontos | Porto Alegre | **Só o nome está preenchido; capacidade, local e áreas vazios** | Localização apenas |
| Recurso hídrico (56) | Cursos d'água do cadastro | Coletado e auditado, integração pendente | 5.989 feições, 766 km | Porto Alegre | `LEITO` distingue natural e artificial; tipo vazio em 45% | Hidrografia (natural e artificial separadas) |
| APP, "Hidrografia 2014" | Áreas de preservação | Coletado e auditado, integração pendente | 139 polígonos | Porto Alegre | Base de 1982 | Contexto; não é curso d'água |
| **MDT 2010** (Image Service) | Elevação do terreno | **Acesso confirmado e piloto feito; sem arquivo para baixar. Solicitação, aquisição e adoção ADIADAS por decisão (Copernicus GLO-30 segue como referência)** | Pixel de 1 m | Município | Erro médio 0,77 m nos marcos (**não independente**); precisão e licença não declaradas | Candidato a microtopografia; **licença a confirmar** |
| MDE_tif (Image Service) | Raster de 8 bits | Acesso confirmado, mas dados ainda não inspecionados em detalhe | 29 m | Município | **Não é elevação em metros** | Não usar |
| Curvas de nível e pontos cotados (2010); "Relevo" (2026) | Cotas | Acesso confirmado, mas dados ainda não inspecionados | Vetor | Município | — | A avaliar |
| LiDAR | Nuvem de pontos | **Disponibilidade não confirmada** (nenhum item no portal) | — | — | — | Pedir à Prefeitura, se existir |
| **Risco de inundação, CPRM** | Classes de risco (Alto, Médio, Baixa) | Coletado e auditado, integração pendente | 2.216 polígonos; 250,8 km² | 53% da área dos bairros | 26 geometrias inválidas; **sem "Muito Alto"**; camada editável no servidor | **Só contexto**; nunca rótulo |
| Pedologia (2008) e suscetibilidade à erosão (2022) | Solo | Acesso confirmado, mas dados ainda não inspecionados | Vetor | Município | — | Necessária para coeficientes de vegetação e solo |
| Capacidade de bombeamento e de condutos | Vazão e capacidade | **Necessita solicitação formal** | — | — | Campo vazio no serviço | Sem ela, não há estimativa de saída |
| Eventos de alagamento com data, hora e local | Rótulos temporais | **Necessita solicitação formal** (Defesa Civil, 156, ObservaPOA) | — | — | — | Validação temporal |
| Chuva com distribuição espacial e temporal; previsão arquivada | Precipitação | Disponibilidade não confirmada | — | — | — | Cenário e validação |
| Nível do Guaíba (condição de contorno) | Cota do lago | Disponibilidade não confirmada | — | — | — | Saída por drenagem e remanso |

## Licenças e condições de uso

Nenhum dos serviços consultados declara licença no próprio metadado (`licenseInfo` vazio no MDT e nas curvas de nível; direitos autorais declarados só no uso do solo, "PROFILL, 2023", e na hidrografia, "Projeto DMWeb"). **A licença de reuso dos dados municipais não foi confirmada.** Antes de publicar qualquer derivado, confirmar com a Prefeitura (a página do GeoPOA oferece o contato `smamus.cgiu@portoalegre.rs.gov.br` para problemas nos dados).
