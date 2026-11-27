# Dados de teste

- `alagamentos_sinteticos.csv`: **pontos SINTÉTICOS**, gerados por `tests/sinteticos.py` (semente fixa, sinal plantado, região fora do Brasil). Têm o mesmo formato do arquivo real
  (`camada`, `lon`, `lat`), mas **não são observações e não reproduzem nenhuma coordenada da Prefeitura**. Servem para os testes rodarem em um clone limpo.
- As coordenadas reais dos alagamentos registrados pela Prefeitura de Porto Alegre **não ficam no Git** (licença e redistribuição não confirmadas). O arquivo
  `data/raw/prefeitura_poa/alagamentos_pmpa_coordenadas.csv` (ou o caminho em `FM_ALAGAMENTOS_CSV`) só existe no disco de quem o tem; sem ele, os testes com dados
  reais são ignorados com uma mensagem, e os sintéticos continuam rodando.
