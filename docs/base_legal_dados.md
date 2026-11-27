# Base legal e origem dos dados da Prefeitura de Porto Alegre

Registro de 27/11/2026. A autora do projeto autorizou o uso, o cruzamento, o processamento e a redistribuição de resultados derivados dos dados da Prefeitura de Porto Alegre, **com atribuição, fontes, metadados e condições legais aplicáveis preservados**, tendo como fundamento a Política de Dados Abertos do município.

## Fundamento invocado

**Decreto Municipal nº 20.315, de 22 de julho de 2019** (republicado em 13/08/2019), que institui a Política de Dados Abertos da Administração Pública Municipal Direta e Indireta de Porto Alegre. A política é conduzida pela Secretaria Municipal de Transparência e Controladoria (SMTC), e o portal de dados abertos é orientado pelo Plano de Dados Abertos (PDA).
Fontes consultadas em 27/11/2026: [notícia da adesão à política](https://prefeitura.poa.br/gp/noticias/porto-alegre-adere-politica-de-dados-abertos-e-lancara-portal), [página de dados abertos da Carta de Serviços](https://prefeitura.poa.br/carta-de-servicos/dados-abertos) e o [Plano de Dados Abertos](https://prefeitura.poa.br/sites/default/files/usu_doc/cartadeservicos/pda%20atualizado%20vers%C3%A3o%20para%20publicar.pdf).

**O que este registro não afirma.** O texto integral do decreto não foi lido nem transcrito aqui, e não se confirmou que cada conjunto abaixo esteja listado no Portal de Dados Abertos. A regularização documental de cada conjunto (licença individual, termos, metadados oficiais) é conduzida separadamente pela autora. Até lá, os conjuntos **não são excluídos** do produto, e cada um aparece com a origem e a atribuição abaixo.

## Origem de cada conjunto da Prefeitura usado nos resultados

| Conjunto | Órgão e canal de obtenção | Dimensão | O que a landing publica |
|---|---|---|---|
| Uso e ocupação do solo, Profill 2022 | Prefeitura de Porto Alegre, serviço de mapas GeoPOA (camada `uso_solo_profill_2022`) | A (geração) e B (concentração) | Imagens e números derivados (volume potencial por trecho de rua), nunca os polígonos originais |
| Cadastro de drenagem pluvial (rede, bocas de lobo, poços, casas de bomba) | Prefeitura de Porto Alegre, GeoPOA (camadas de drenagem) | D (drenagem cadastrada) | Imagem e números derivados (metros de rede cadastrada por célula, bocas por km²) |
| Limites de 94 bairros | Prefeitura de Porto Alegre, mapa compartilhado no Google My Maps (KML) | Agregação por bairro | Linhas dos limites na imagem e estatísticas por bairro |
| Relevo e ruas | Copernicus DEM GLO-30 (ESA e Airbus) e © colaboradores do OpenStreetMap | C (propensão topográfica) | Imagem e números derivados |

Eventos noticiados e a lista de alagamentos da Prefeitura **não** entram nesta versão da landing, por decisão da autora.

## O que continua fora do Git

Os arquivos originais e os derivados volumosos (parquets, tiles, rasters) seguem fora do repositório por tamanho, e não por exclusão: ficam em `data/` e no plano de armazenamento em [`catalogo_dados.md`](catalogo_dados.md). O repositório recebe só as imagens WebP e os números agregados que a landing usa, com atribuição. O mapa interativo continua como está.
