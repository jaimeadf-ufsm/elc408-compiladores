

# **Trabalho Final: Compiladores (2026)**

## 

## **1\. Construir uma Linguagem e um Tradutor para automações no Home Assistant**

Os alunos deverão projetar e implementar um compilador (tradutor) para a sua linguagem. A linguagem deve abstrair a complexidade das automações procedurais, transformando scripts lógicos em arquivos de configuração **YAML** compatíveis com o padrão do **Home Assistant**.

**Prazo de Entrega:** até dia 06/06/2026 (via Classroom \- link GitHub)

**Apresentação Presencial:** De acordo com o cronograma da disciplina (presencial e explanativa). Serão 7 apresentações por dia letivo, de acordo com a ordem de entrega .

## **2\. Requisitos Técnicos Obrigatórios**

O projeto deve ser construído seguindo rigorosamente as fases do front-end e o início do back-end de um compilador:

### **A. Definição da Linguagem** 

* A linguagem definida pela GLC deve ser focada em pessoas leigas, que não possuem domínio de computação ou automação residencial.  
* A(s) Gramática(s) Livre de Contexto desta linguagem deve(m) estar completamente especificada(s) na documentação.  
* Em anexo a este documento, está uma série de automações em YAML que servirão de base.

### **B. Análise Léxica (Scanner)**

* Especificação e implementação de um **DFA (Autômato Finito Determinístico)** manual ou gerado (ex: Flex) para o reconhecimento dos tokens da GLC.  
* Suporte a tokens complexos: entity\_id (ex: sensor.temperature\_living\_room), unidades de tempo (ex: 10s, 5min), strings e operadores lógicos.  
* Tratamento de comentários e contagem de linhas para reporte de erros.

### **C. Análise Sintática (Parser Top-Down)**

* Representação da **GLC (Gramática Livre de Contexto)** na forma **Top Down LL(1)** ou na forma **Bottom Up LR(k)**.  
* Implementação obrigatoriamente baseada em **Tabela Preditiva LL(1) ou LR(k)**.  
* **Recuperação de Erros:** O parser não deve abortar no primeiro erro. Implementar a técnica de **Modo Pânico** (sincronização por tokens como ; ou }).

### **D. Análise Semântica**

* **Tabela de Símbolos:** Armazenar tipos de entidades (luz, sensor, interruptor) e escopo de variáveis.  
* **Verificação de Tipos:** Impedir operações inválidas (ex: atribuir "25°C" a uma lâmpada ON/OFF).  
* **Consistência Externa:** Validar se os serviços chamados (ex: light.turn\_on) são compatíveis com o domínio da entidade.

### **D. Geração de Código Intermediário (YAML)**

* Tradução da árvore sintática/AST para a estrutura declarativa do Home Assistant.  
* Tratamento de indentação rígida do YAML e mapeamento de gatilhos (*triggers*), condições e ações.

## **3\. Entregáveis**

1. **Código Fonte:** Repositório organizado com instruções de compilação (Makefile/CMake).  
2. **Relatório Técnico:**  
   1. Descrição da GLC (identificando terminais e não-terminais).  
   2. Descrição da especificação do Analisador Léxico.  
   3. Descrição da especificação do Analisador Sintático.  
   4. Descrição da especificação do Analisador Semântico.  
   5. Exemplos de scripts da sua linguagem e os YAMLs resultantes.  
3. **Apresentação:** Defesa presencial de 15 minutos contendo:  
   1. Explicação da gramática, especificação e implementação de cada etapa do compilador e decisões de projeto.  
   2. Demonstração do compilador detectando e reportando erros sintáticos/semânticos  
   3. Demonstração do compilador processando um exemplo válido fornecido pelo docente durante a apresentação.

## **5\. Critérios de Avaliação**

**Pontos que serão avaliado e seus respectivos pesos:**

1. Especificação da GLC \- 10%  
   2. Analisador Léxico \- 10%  
   3. Analisador Sintático \- 10%  
   4. Analisador Semântico \- 10%  
   5. Detecção de Erros \- 10%  
   6. Apresentação e Testes \- 50%

