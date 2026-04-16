# Avaliação 1
Integrantes: Jaime Antonio Daniel Filho e Luís Gustavo Werle Tozevich

## Enunciado

Para a seguinte gramática livre do contexto, faça a especificação de um analisador Preditivo Recursivo:

- O -> { L }
- L -> P R | vazio
- P -> string : V
- R -> , P R | vazio
- V -> string | number | O

Para o analisador preditivo tabular, deve ser entregue a tabela e o reconhecimento da seguinte palavra:

- {string: {string: number, string: string}, string: number}
- {string: {string: string, string: }, string: number}

O trabalho pode ser feito em dupla, entretanto ambos os membros devem fazer o envio individualmente. Descrevam, no comentário particular da atividade, o nome do outro membro da dupla (se existir). O envio deve ser em arquivo PDF, escaneado do caderno feito pessoalmente.

## Resolução

### Conjuntos FIRST e FOLLOW

```
FIRST(V) = < string, number, '{' >
FIRST(R) = < ',', vazio >
FIRST(P) = < string >
FIRST(L) = < string, vazio >
FIRST(O) = < '{' >
```

<!-- ```
FOLLOW(O) = < $, FOLLOW(V) >
FOLLOW(L) = < '}' >
FOLLOW(P) = < FIRST(L), FIRST(R) >
FOLLOW(R) = < FOLLOW(L), FOLLOW(R) >
FOLLOW(V) = < FOLLOW(P) >
``` -->

```
FOLLOW(O) = < $, '}', ',' >
FOLLOW(L) = < '}' >
FOLLOW(P) = < '}', ',' >
FOLLOW(R) = < '}' >
FOLLOW(V) = < '}', ',' >
```

<br>
<br>
<br>
<br>
<br>

### Construção da tabela

|     | '{'        | '}'        | :   | ','        | string          | number      | $   |
| --- | ---------- | ---------- | --- | ---------- | --------------- | ----------- | --- |
| O   | O -> { L } |            |     |            |                 |             |     |
| L   |            | L -> vazio |     |            | L -> P R        |             |     |
| P   |            |            |     |            | P -> string : V |             |     |
| R   |            | R -> vazio |     | R -> , P R |                 |             |     |
| V   | V -> O     |            |     |            | V -> string     | V -> number |     |

### Reconhecimento das palavras

- {string: {string: number, string: string}, string: number}

|     | Pilha -------------- | ---------------------------------------------------- Entrada | Ação ----------- |
| --- | -------------------- | -----------------------------------------------------------: | ---------------- |
| 1   | $ O                  | {string: {string: number, string: string}, string: number} $ | O -> { L }       |
| 2   | $ } L {              | {string: {string: number, string: string}, string: number} $ | consome {        |
| 3   | $ } L                |  string: {string: number, string: string}, string: number} $ | L -> P R         |
| 4   | $ } R P              |  string: {string: number, string: string}, string: number} $ | P -> string : V  |
| 5   | $ } R V : string     |  string: {string: number, string: string}, string: number} $ | consome string   |
| 6   | $ } R V :            |        : {string: number, string: string}, string: number} $ | consome :        |
| 7   | $ } R V              |          {string: number, string: string}, string: number} $ | V -> O           |
| 8   | $ } R O              |          {string: number, string: string}, string: number} $ | O -> { L }       |
| 9   | $ } R } L {          |          {string: number, string: string}, string: number} $ | consome {        |
| 10  | $ } R } L            |           string: number, string: string}, string: number} $ | L -> P R         |
| 11  | $ } R } R P          |           string: number, string: string}, string: number} $ | P -> string : V  |
| 12  | $ } R } R V : string |           string: number, string: string}, string: number} $ | consome string   |
| 13  | $ } R } R V :        |                 : number, string: string}, string: number} $ | consome :        |
| 14  | $ } R } R V          |                   number, string: string}, string: number} $ | V -> number      |
| 15  | $ } R } R number     |                   number, string: string}, string: number} $ | consome number   |
| 16  | $ } R } R            |                         , string: string}, string: number} $ | R -> , P R       |
| 17  | $ } R } R P ,        |                         , string: string}, string: number} $ | consome ,        |
| 18  | $ } R } R P          |                           string: string}, string: number} $ | P -> string : V  |
| 19  | $ } R } R V : string |                           string: string}, string: number} $ | consome string   |
| 20  | $ } R } R V :        |                                 : string}, string: number} $ | consome :        |
| 21  | $ } R } R V          |                                   string}, string: number} $ | V -> string      |
| 22  | $ } R } R string     |                                   string}, string: number} $ | consome string   |
| 23  | $ } R } R            |                                         }, string: number} $ | R -> vazio       |
| 24  | $ } R }              |                                         }, string: number} $ | consome }        |
| 25  | $ } R                |                                          , string: number} $ | R -> , P R       |
| 26  | $ } R P ,            |                                          , string: number} $ | consome ,        |
| 27  | $ } R P              |                                            string: number} $ | P ->  string : V |
| 28  | $ } R V : string     |                                            string: number} $ | consome string   |
| 29  | $ } R V :            |                                                  : number} $ | consome :        |
| 30  | $ } R V              |                                                    number} $ | V -> number      |
| 31  | $ } R number         |                                                    number} $ | consome number   |
| 32  | $ } R                |                                                          } $ | R -> vazio       |
| 33  | $ }                  |                                                          } $ | consome }        |
| 34  | $                    |                                                            $ | Aceito           |

- {string: {string: string, string: }, string: number}

|     | Pilha -------------- | ---------------------------------------------------- Entrada | Ação ----------- |
| --- | -------------------- | -----------------------------------------------------------: | ---------------- |
| 1   | $ O                  |       {string: {string: string, string: }, string: number} $ | O -> { L }       |
| 2   | $ } L {              |       {string: {string: string, string: }, string: number} $ | consome {        |
| 3   | $ } L                |        string: {string: string, string: }, string: number} $ | L -> P R         |
| 4   | $ } R P              |        string: {string: string, string: }, string: number} $ | P -> string : V  |
| 5   | $ } R V : string     |        string: {string: string, string: }, string: number} $ | consome string   |
| 6   | $ } R V :            |              : {string: string, string: }, string: number} $ | consome :        |
| 7   | $ } R V              |                {string: string, string: }, string: number} $ | V -> O           |
| 8   | $ } R O              |                {string: string, string: }, string: number} $ | O -> { L }       |
| 9   | $ } R } L {          |                {string: string, string: }, string: number} $ | consome {        |
| 10  | $ } R } L            |                 string: string, string: }, string: number} $ | L -> P R         |
| 11  | $ } R } R P          |                 string: string, string: }, string: number} $ | P -> string : V  |
| 12  | $ } R } R V : string |                 string: string, string: }, string: number} $ | consome string   |
| 13  | $ } R } R V :        |                       : string, string: }, string: number} $ | consome :        |
| 14  | $ } R } R V          |                         string, string: }, string: number} $ | V -> string      |
| 15  | $ } R } R string     |                         string, string: }, string: number} $ | consome string   |
| 16  | $ } R } R            |                               , string: }, string: number} $ | R -> , P R       |
| 17  | $ } R } R P ,        |                               , string: }, string: number} $ | consome ,        |
| 18  | $ } R } R P          |                                 string: }, string: number} $ | P -> string : V  |
| 19  | $ } R } R V : string |                                 string: }, string: number} $ | consome string   |
| 20  | $ } R } R V :        |                                       : }, string: number} $ | consome :        |
| 21  | $ } R } R V          |                                         }, string: number} $ | Erro             |