# Entrega 1 — Sistema de Controle de Semáforos

**Fundamentos de Sistemas Embarcados (2026/1)**

Sistema embarcado em Raspberry Pi que controla dois modelos de semáforo independentes e simultâneos via GPIO.

## Modelos

| Modelo | Descrição | Cruzamento | Saída GPIO |
|--------|-----------|------------|------------|
| **1** | Semáforo simples (3 LEDs individuais) | Cruzamento 1 | Verde=17, Amarelo=18, Vermelho=23 |
| **2** | Cruzamento completo (código de 3 bits) | Cruzamento 2 | Bit0=24, Bit1=8, Bit2=7 |

## Estrutura do Projeto

```
src/
├── __init__.py               # Pacote Python
├── config.py                 # Constantes (pinos GPIO, tempos, debounce)
├── gpio_module.py            # Módulo de abstração da GPIO (RPi.GPIO)
├── traffic_light_model1.py   # Máquina de estados — Modelo 1 (3 LEDs)
├── traffic_light_model2.py   # Máquina de estados — Modelo 2 (cruzamento 3-bit)
└── main.py                   # Controlador principal
```

## Instalação

```bash
# Na Raspberry Pi, instale as dependências:
pip3 install -r requirements.txt
```

> **Nota:** `RPi.GPIO` geralmente já vem pré-instalado no Raspberry Pi OS.

## Execução

```bash
# Executar ambos os modelos simultaneamente
python3 -m src.main

# Executar apenas o Modelo 1
python3 -m src.main --modelo 1

# Executar apenas o Modelo 2
python3 -m src.main --modelo 2
```

Para encerrar, pressione `Ctrl+C`. O sistema desligará todos os LEDs e liberará os recursos GPIO de forma segura.

## Saída no Terminal

O programa imprime em tempo real:

```
============================================================
  SISTEMA DE CONTROLE DE SEMÁFOROS — ENTREGA 1
  Fundamentos de Sistemas Embarcados (2026/1)
============================================================
[Sistema] GPIO inicializada (modo BCM).
[Modelo 1] Iniciado no estado VERDE
[Sistema] Modelo 1 (3 LEDs) iniciado.
[Modelo 2] Iniciado no estado Principal VERDE / Cruzamento VERMELHO (código 1)
[Sistema] Modelo 2 (Cruzamento 3-bit) iniciado.
------------------------------------------------------------
[Sistema] Pressione Ctrl+C para encerrar.
------------------------------------------------------------
[Modelo 1] VERDE → AMARELO
[Modelo 2] Botão pedestre cruzamento acionado (GPIO 22)
[Modelo 2] Principal VERDE / Cruzamento VERMELHO (código 1) → Principal AMARELO (código 2)
[Modelo 1] AMARELO → VERMELHO
...
```

## Explicação Técnica

### Concorrência

O sistema utiliza **`threading.Thread`** para executar cada modelo de semáforo em sua própria thread:

- `Model1-Thread` → executa o ciclo do Modelo 1
- `Model2-Thread` → executa o ciclo do Modelo 2
- Thread principal → aguarda `Ctrl+C` e coordena o shutdown

Cada thread possui seu próprio loop com granularidade de **50ms** (`time.sleep(0.05)`), verificando condições de transição a cada iteração. Isso evita busy-waiting (não é um spin-loop) enquanto mantém responsividade adequada para os botões de pedestre.

As flags de pedestre utilizam **`threading.Event`**, que é thread-safe e permite comunicação atômica entre a thread de interrupção do GPIO e a thread da FSM.

### Debounce

O debounce é implementado via o parâmetro `bouncetime` do `RPi.GPIO.add_event_detect()`:

```python
GPIO.add_event_detect(pin, GPIO.RISING, callback=callback, bouncetime=200)
```

Isso delega o debounce ao driver de interrupção, que ignora bordas adicionais dentro da janela de 200ms. Vantagens:
- Sem busy-waiting
- Tratamento por interrupção de hardware (não polling)
- Confiável e eficiente

### Temporização

Os tempos são controlados com **`time.monotonic()`**, que:
- Não é afetado por ajustes de relógio (NTP, fuso horário)
- Tem resolução suficiente (~1μs no Linux)
- É monotonicamente crescente (nunca retrocede)

A cada iteração do loop, o tempo decorrido é calculado:
```python
elapsed = time.monotonic() - self._state_start
```

O erro máximo de temporização é de ~50ms (intervalo do loop), aceitável para os tempos exigidos (2-20 segundos).

### Máquina de Estados

Ambos os modelos utilizam **FSM explícita** com:
- **`Enum`** para definição dos estados
- Transições controladas por **tempo** e **evento** (botão)
- Estados bem definidos sem `if` soltos
- Impressão de cada transição no terminal

O Modelo 2 usa **6 estados internos** (incluindo `S4_ALL_RED_A` e `S4_ALL_RED_B`) para representar o estado "tudo vermelho" que aparece duas vezes no ciclo, evitando lógica condicional de "de onde vim".

## Tabela de Pinos GPIO

### Saídas

| Pino | Modelo | Função |
|------|--------|--------|
| 17 | M1 | LED Verde |
| 18 | M1 | LED Amarelo |
| 23 | M1 | LED Vermelho |
| 24 | M2 | Semáforo Bit 0 |
| 8 | M2 | Semáforo Bit 1 |
| 7 | M2 | Semáforo Bit 2 |

### Entradas (Botões)

| Pino | Modelo | Função |
|------|--------|--------|
| 1 | M1 | Pedestre Principal |
| 12 | M1 | Pedestre Cruzamento |
| 25 | M2 | Pedestre Principal |
| 22 | M2 | Pedestre Cruzamento |

## Sugestões de Melhoria (Preparação para Entrega 2)

1. **Sensores de velocidade**: O `gpio_module.py` pode ser estendido com detecção de borda em dois pinos (A/B) e cálculo de Δt para velocidade.
2. **Servidor distribuído**: O `main.py` evoluirá para um servidor TCP/IP que recebe comandos do Servidor Central (modo noturno, emergência).
3. **Comunicação MODBUS**: Adicionar módulo `modbus_module.py` para comunicação RS485 com as câmeras LPR.
4. **Modo noturno**: Adicionar método `set_night_mode()` nas classes de semáforo que alterna entre códigos 0 e 4 (amarelo intermitente).
5. **Modo emergência**: Adicionar método `set_emergency()` que força estado 1 (via principal verde) até desativação.
6. **Configuração por arquivo**: Migrar constantes de `config.py` para arquivo JSON/YAML configurável por cruzamento.
