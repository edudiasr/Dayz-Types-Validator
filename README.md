# dayz-types-validator

Validador de `types.xml` pra servidor de DayZ.

Fiz isso porque cansei de reiniciar meu servidor (DIA-Z HARDCORE) e descobrir depois que um item parou de nascer por causa de um erro bobo no types: `min` maior que o `nominal`, item duplicado, `usage` escrita errada. O jogo não reclama, o item só some do mapa. A ideia é rodar isso antes de cada restart.

```
examples\types_com_erros.xml
  linha     7  ERRO  E008 [AKM] min (6) maior que nominal (4)
  linha    13  ERRO  E013 [AKM] <usage name="Militar"> não existe no cfglimitsdefinition.xml
  linha    16  ERRO  E004 [akm] tipo duplicado (primeira declaração na linha 3); o jogo usa só uma delas
  linha    28  ERRO  E005 [WaterBottle] <nominal> declarado 2 vezes
  linha    31  ERRO  E006 [WaterBottle] <lifetime> deve ser um número inteiro, encontrado 'dez'
  linha    35  ERRO  E009 [WaterBottle] <quantmax> deve ser -1 ou ficar entre 0 e 100 (150)
  linha    37  ERRO  E011 [WaterBottle] count_in_map deve ser 0 ou 1, encontrado 'sim'
  linha    37  AVISO W007 [WaterBottle] <flags> sem: deloot
  linha    40  AVISO W005 [WaterBottle] <usage name="Town"> repetido
  linha    42  AVISO W003 [Apple] nominal > 0 sem <usage>, <value> ou <category>: o item pode não ter onde nascer
  linha    47  AVISO W004 [Apple] só um entre quantmin e quantmax é -1; use -1 nos dois ou em nenhum
  linha    51  AVISO W001 [Apple] tag desconhecida <spawn>

  4 tipos, 4 com nominal > 0 · 7 erro(s), 5 aviso(s)

  Nominal total por categoria:
    tools                30
    (sem categoria)      10
    weapons               6
```

## Rodando

Só precisa de Python 3.10+, sem instalar nada.

```bash
python -m types_validator caminho/do/types.xml
```

Se passar o `cfglimitsdefinition.xml` (e o `...user.xml`, se usar), ele também confere se as usage/value/tag/category existem:

```bash
python -m types_validator types.xml -l cfglimitsdefinition.xml -l cfglimitsdefinitionuser.xml
```

Dá pra passar vários arquivos de uma vez, tipo os types de cada mod. Outras opções:

- `-f json` → saída em JSON, pra usar em outro script ou bot
- `--strict` → aviso também conta como falha
- `--no-color` → sem cor

Sai com código 0 se tá tudo certo, 1 se achou erro e 2 se não conseguiu ler o arquivo. Então dá pra colocar no script de restart e cancelar o restart se o types estiver quebrado.

## O que ele pega

Erros:

- E001 XML quebrado (mostra linha e coluna)
- E002 raiz não é `<types>`
- E003 `<type>` sem name
- E004 item duplicado (ignora maiúscula/minúscula, igual o jogo)
- E005 tag repetida dentro do mesmo item (dois `<nominal>`, por exemplo)
- E006 número que não é número
- E007 valor negativo em nominal, lifetime, restock, min ou cost
- E008 min maior que nominal
- E009 quantmin/quantmax fora de -1 ou 0 a 100
- E010 quantmin maior que quantmax
- E011 flag diferente de 0 ou 1
- E012 usage/value/tag/category sem name
- E013 nome que não existe no cfglimitsdefinition (só com `-l`)

Avisos:

- W001 tag desconhecida
- W002 falta alguma tag padrão (nominal, lifetime, restock, min, quantmin, quantmax, cost, flags)
- W003 item com nominal > 0 sem lugar pra nascer
- W004 só um entre quantmin e quantmax é -1
- W005 usage/value/tag repetida no mesmo item
- W006 atributo estranho no `<flags>`
- W007 `<flags>` faltando algum atributo
- W008 coisa fora de `<type>`

No final ainda soma o nominal por categoria, que ajuda bastante na hora de balancear arma vs comida vs ferramenta.

## Estrutura

- `xmltree.py`: lê o XML usando o expat. Usei ele em vez do ElementTree porque o ElementTree não guarda o número da linha, e sem linha o relatório não serve pra nada num types de 20 mil linhas.
- `validator.py`: as regras.
- `limits.py`: carrega os nomes válidos do cfglimitsdefinition.
- `output.py`: texto colorido ou JSON.
- `cli.py`: argumentos e códigos de saída.

## Testes

```bash
python -m unittest discover -s tests -t .
```

Os testes também rodam no GitHub Actions a cada push.

Mais projetos meus no [portfólio](https://edudiasr.github.io/portfolio-web/).
